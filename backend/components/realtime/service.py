from __future__ import annotations

import asyncio
import hashlib
import json
import secrets
import time
from typing import Awaitable, Callable, Optional
from uuid import UUID

from redis.asyncio import Redis

from components.realtime.redis_client import RedisClientHandle, create_redis_client
from settings import config
from utils.logger import setup_logger

logger = setup_logger(__name__)

RealtimeCallback = Callable[[dict], Awaitable[None]]


class RealtimeUnavailable(RuntimeError):
    """Raised when realtime infrastructure required by an operation is unavailable."""


class RealtimeService:
    """
    Shared realtime infrastructure for PubChat.

    Redis is authoritative in production for one-time socket tickets, cross-worker
    pub/sub, presence, rate limits and idempotency. DEBUG mode has a process-local
    fallback so developers can exercise the protocol without a Redis service.

    Redis transport is topology-agnostic: direct REDIS_URL remains supported,
    while Sentinel mode discovers the current master and reconnects after failover.
    """

    CHANNEL = "pubchat:realtime:v2"

    def __init__(self) -> None:
        self._redis: Optional[Redis] = None
        self._redis_handle: Optional[RedisClientHandle] = None
        self._listener_task: Optional[asyncio.Task] = None
        self._pubsub = None
        self._callbacks: list[RealtimeCallback] = []
        self._fallback_tickets: dict[str, dict] = {}
        self._fallback_connections: dict[str, dict] = {}
        self._fallback_rate_limits: dict[str, tuple[int, float]] = {}
        self._fallback_idempotency: dict[str, float] = {}
        self._lock = asyncio.Lock()

    @property
    def redis(self) -> Optional[Redis]:
        return self._redis

    @property
    def distributed(self) -> bool:
        return self._redis is not None

    @property
    def redis_mode(self) -> str | None:
        return self._redis_handle.mode if self._redis_handle else None

    def register_callback(self, callback: RealtimeCallback) -> None:
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    async def start(self) -> None:
        if self._redis is not None or self._listener_task is not None:
            return

        try:
            config.ensure_realtime_settings()
        except RuntimeError as exc:
            if config.DEBUG and not config.redis_configured():
                logger.warning(
                    "Redis не настроен: realtime v2 работает в process-local DEBUG fallback"
                )
                return
            logger.error("Некорректная Redis/realtime конфигурация: %s", exc)
            return

        if not config.redis_configured():
            if config.DEBUG:
                logger.warning(
                    "Redis не настроен: realtime v2 работает в process-local DEBUG fallback"
                )
                return
            logger.error("Redis обязателен для production realtime v2")
            return

        handle: RedisClientHandle | None = None
        try:
            handle = create_redis_client()
            await handle.client.ping()
            self._redis_handle = handle
            self._redis = handle.client
            await self._subscribe()
            logger.info("Realtime v2 подключен к Redis (topology=%s)", handle.mode)
        except Exception as exc:
            if handle is not None and self._redis_handle is None:
                try:
                    await handle.aclose()
                except Exception:
                    pass
            await self._reset_redis()
            logger.exception("Не удалось подключить realtime v2 к Redis: %s", exc)
            if not config.DEBUG:
                logger.error("Production realtime операции будут отклоняться до восстановления Redis")

    async def _subscribe(self) -> None:
        if not self._redis:
            return
        self._pubsub = self._redis.pubsub(ignore_subscribe_messages=True)
        await self._pubsub.subscribe(self.CHANNEL)
        self._listener_task = asyncio.create_task(self._listen(), name="pubchat-realtime-listener")

    async def stop(self) -> None:
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
            self._listener_task = None

        if self._pubsub:
            try:
                await self._pubsub.unsubscribe(self.CHANNEL)
                await self._pubsub.aclose()
            finally:
                self._pubsub = None

        await self._close_redis()

    async def _close_redis(self) -> None:
        handle = self._redis_handle
        client = self._redis
        self._redis_handle = None
        self._redis = None

        if handle is not None:
            await handle.aclose()
            return
        if client is not None:
            await client.aclose()

    async def _reset_redis(self) -> None:
        if self._pubsub:
            try:
                await self._pubsub.aclose()
            except Exception:
                pass
            self._pubsub = None
        try:
            await self._close_redis()
        except Exception:
            pass
        self._listener_task = None

    async def _recreate_pubsub(self) -> bool:
        if not self._redis:
            return False
        if self._pubsub:
            try:
                await self._pubsub.aclose()
            except Exception:
                pass
        try:
            self._pubsub = self._redis.pubsub(ignore_subscribe_messages=True)
            await self._pubsub.subscribe(self.CHANNEL)
            return True
        except Exception:
            logger.exception("Не удалось восстановить Redis PubSub subscription")
            self._pubsub = None
            return False

    async def _listen(self) -> None:
        retry_delay = 1.0
        while True:
            try:
                if not self._pubsub:
                    restored = await self._recreate_pubsub()
                    if not restored:
                        await asyncio.sleep(retry_delay)
                        retry_delay = min(retry_delay * 2, 30.0)
                        continue

                async for message in self._pubsub.listen():
                    retry_delay = 1.0
                    if message.get("type") != "message":
                        continue
                    try:
                        event = json.loads(message["data"])
                        await self._dispatch(event)
                    except Exception:
                        logger.exception("Ошибка обработки Redis realtime event")

                logger.warning("Redis realtime PubSub iterator завершился; восстанавливаем подписку")
                if self._pubsub:
                    try:
                        await self._pubsub.aclose()
                    except Exception:
                        pass
                    self._pubsub = None
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Redis realtime listener потерял соединение; восстанавливаем подписку")
                if self._pubsub:
                    try:
                        await self._pubsub.aclose()
                    except Exception:
                        pass
                    self._pubsub = None

            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 30.0)

    async def _dispatch(self, event: dict) -> None:
        if not self._callbacks:
            return
        results = await asyncio.gather(
            *(callback(event) for callback in tuple(self._callbacks)),
            return_exceptions=True,
        )
        for result in results:
            if isinstance(result, Exception):
                logger.error("Realtime callback завершился ошибкой: %s", result)

    async def publish(self, event: dict) -> None:
        event.setdefault("protocol", 2)
        if self._redis:
            try:
                await self._redis.publish(self.CHANNEL, json.dumps(event, default=str))
                return
            except Exception as exc:
                logger.exception("Redis publish failed: %s", exc)
                if not config.DEBUG:
                    raise RealtimeUnavailable("Redis realtime delivery is unavailable") from exc
        if not config.DEBUG:
            raise RealtimeUnavailable("Redis is required for distributed realtime delivery")
        await self._dispatch(event)

    async def publish_room(self, room_uid: UUID | str, payload: dict) -> None:
        await self.publish({"kind": "room", "room_uid": str(room_uid), "payload": payload})

    async def publish_user(self, user_uid: UUID | str, payload: dict) -> None:
        await self.publish({"kind": "user", "user_uid": str(user_uid), "payload": payload})

    async def publish_status(self, user_uid: UUID | str, is_online: bool) -> None:
        await self.publish(
            {
                "kind": "status",
                "user_uid": str(user_uid),
                "is_online": bool(is_online),
            }
        )

    @staticmethod
    def _ticket_key(raw_ticket: str) -> str:
        digest = hashlib.sha256(raw_ticket.encode("utf-8")).hexdigest()
        return f"pubchat:rt:ticket:{digest}"

    async def issue_ticket(
        self,
        account_uid: UUID | str,
        target: str,
        resource_uid: UUID | str | None = None,
        session_uid: UUID | str | None = None,
        device_uid: UUID | str | None = None,
    ) -> tuple[str, int]:
        if not self._redis and not config.DEBUG and config.redis_configured():
            await self.start()
        if not self._redis and not config.DEBUG:
            raise RealtimeUnavailable("Redis is required to issue production realtime tickets")

        raw_ticket = secrets.token_urlsafe(32)
        ttl = config.REALTIME_TICKET_TTL_SECONDS
        payload = {
            "account_uid": str(account_uid),
            "target": target,
            "resource_uid": str(resource_uid) if resource_uid else None,
            "session_uid": str(session_uid) if session_uid else None,
            "device_uid": str(device_uid) if device_uid else None,
            "expires_at": time.time() + ttl,
        }
        key = self._ticket_key(raw_ticket)

        if self._redis:
            created = await self._redis.set(key, json.dumps(payload), ex=ttl, nx=True)
            if not created:
                raise RealtimeUnavailable("Could not create realtime ticket")
        else:
            async with self._lock:
                self._purge_fallback_tickets()
                self._fallback_tickets[key] = payload

        return raw_ticket, ttl

    async def consume_ticket(
        self,
        raw_ticket: str,
        target: str,
        resource_uid: UUID | str | None = None,
    ) -> Optional[dict]:
        key = self._ticket_key(raw_ticket)
        payload = None

        if self._redis:
            raw_payload = await self._redis.getdel(key)
            if raw_payload:
                payload = json.loads(raw_payload)
        else:
            async with self._lock:
                self._purge_fallback_tickets()
                payload = self._fallback_tickets.pop(key, None)

        if not payload or payload.get("expires_at", 0) <= time.time():
            return None
        if payload.get("target") != target:
            return None

        expected_resource = str(resource_uid) if resource_uid else None
        if payload.get("resource_uid") != expected_resource:
            return None
        return payload

    def _purge_fallback_tickets(self) -> None:
        now = time.time()
        expired = [key for key, value in self._fallback_tickets.items() if value.get("expires_at", 0) <= now]
        for key in expired:
            self._fallback_tickets.pop(key, None)

    @staticmethod
    def _presence_user_key(user_uid: UUID | str) -> str:
        return f"pubchat:rt:presence:user:{user_uid}"

    @staticmethod
    def _presence_room_key(room_uid: UUID | str) -> str:
        return f"pubchat:rt:presence:room:{room_uid}"

    @staticmethod
    def _presence_connection_key(connection_id: str) -> str:
        return f"pubchat:rt:presence:connection:{connection_id}"

    async def register_connection(
        self,
        connection_id: str,
        user_uid: UUID | str,
        target: str,
        room_uid: UUID | str | None = None,
    ) -> None:
        expires_at = time.time() + config.REALTIME_PRESENCE_TTL_SECONDS
        record = {
            "connection_id": connection_id,
            "user_uid": str(user_uid),
            "target": target,
            "room_uid": str(room_uid) if room_uid else None,
            "expires_at": expires_at,
        }

        if self._redis:
            pipe = self._redis.pipeline(transaction=False)
            pipe.set(
                self._presence_connection_key(connection_id),
                json.dumps(record),
                ex=config.REALTIME_PRESENCE_TTL_SECONDS,
            )
            pipe.zadd(self._presence_user_key(user_uid), {connection_id: expires_at})
            pipe.expire(self._presence_user_key(user_uid), config.REALTIME_PRESENCE_TTL_SECONDS * 2)
            if room_uid:
                member = f"{connection_id}|{user_uid}"
                pipe.zadd(self._presence_room_key(room_uid), {member: expires_at})
                pipe.expire(self._presence_room_key(room_uid), config.REALTIME_PRESENCE_TTL_SECONDS * 2)
            await pipe.execute()
        else:
            async with self._lock:
                self._fallback_connections[connection_id] = record

    async def touch_connection(self, connection_id: str) -> None:
        now = time.time()
        expires_at = now + config.REALTIME_PRESENCE_TTL_SECONDS

        if self._redis:
            raw_record = await self._redis.get(self._presence_connection_key(connection_id))
            if not raw_record:
                return
            record = json.loads(raw_record)
            record["expires_at"] = expires_at
            presence_index_ttl = config.REALTIME_PRESENCE_TTL_SECONDS * 2
            user_presence_key = self._presence_user_key(record["user_uid"])

            pipe = self._redis.pipeline(transaction=False)
            pipe.set(
                self._presence_connection_key(connection_id),
                json.dumps(record),
                ex=config.REALTIME_PRESENCE_TTL_SECONDS,
            )
            pipe.zadd(user_presence_key, {connection_id: expires_at})
            pipe.expire(user_presence_key, presence_index_ttl)
            if record.get("room_uid"):
                member = f"{connection_id}|{record['user_uid']}"
                room_presence_key = self._presence_room_key(record["room_uid"])
                pipe.zadd(room_presence_key, {member: expires_at})
                pipe.expire(room_presence_key, presence_index_ttl)
            await pipe.execute()
            return

        async with self._lock:
            record = self._fallback_connections.get(connection_id)
            if record:
                record["expires_at"] = expires_at

    async def unregister_connection(self, connection_id: str) -> Optional[dict]:
        if self._redis:
            key = self._presence_connection_key(connection_id)
            raw_record = await self._redis.get(key)
            if not raw_record:
                return None
            record = json.loads(raw_record)
            pipe = self._redis.pipeline(transaction=False)
            pipe.delete(key)
            pipe.zrem(self._presence_user_key(record["user_uid"]), connection_id)
            if record.get("room_uid"):
                pipe.zrem(
                    self._presence_room_key(record["room_uid"]),
                    f"{connection_id}|{record['user_uid']}",
                )
            await pipe.execute()
            return record

        async with self._lock:
            return self._fallback_connections.pop(connection_id, None)

    async def room_users(self, room_uid: UUID | str) -> list[str]:
        now = time.time()
        if self._redis:
            key = self._presence_room_key(room_uid)
            await self._redis.zremrangebyscore(key, "-inf", now)
            members = await self._redis.zrangebyscore(key, now, "+inf")
            return sorted({member.split("|", 1)[1] for member in members if "|" in member})

        async with self._lock:
            self._purge_fallback_connections(now)
            return sorted(
                {
                    record["user_uid"]
                    for record in self._fallback_connections.values()
                    if record.get("room_uid") == str(room_uid)
                }
            )

    async def is_online(self, user_uid: UUID | str) -> bool:
        now = time.time()
        if self._redis:
            key = self._presence_user_key(user_uid)
            await self._redis.zremrangebyscore(key, "-inf", now)
            return bool(await self._redis.zcount(key, now, "+inf"))

        async with self._lock:
            self._purge_fallback_connections(now)
            return any(record["user_uid"] == str(user_uid) for record in self._fallback_connections.values())

    def _purge_fallback_connections(self, now: Optional[float] = None) -> None:
        now = now or time.time()
        expired = [
            connection_id
            for connection_id, record in self._fallback_connections.items()
            if record.get("expires_at", 0) <= now
        ]
        for connection_id in expired:
            self._fallback_connections.pop(connection_id, None)

    async def allow_action(
        self,
        user_uid: UUID | str,
        bucket: str,
        limit: int,
        window_seconds: int,
    ) -> bool:
        key = f"pubchat:rt:rate:{bucket}:{user_uid}"
        if self._redis:
            count = await self._redis.incr(key)
            if count == 1:
                await self._redis.expire(key, window_seconds)
            return count <= limit

        now = time.time()
        async with self._lock:
            count, reset_at = self._fallback_rate_limits.get(key, (0, now + window_seconds))
            if reset_at <= now:
                count, reset_at = 0, now + window_seconds
            count += 1
            self._fallback_rate_limits[key] = (count, reset_at)
            return count <= limit

    async def allow_cost(
        self,
        user_uid: UUID | str,
        bucket: str,
        cost: int,
        limit: int,
        window_seconds: int,
    ) -> bool:
        """Apply a distributed weighted rate limit without logging identifiers/payloads."""
        normalized_cost = max(0, int(cost))
        normalized_limit = max(1, int(limit))
        if normalized_cost > normalized_limit:
            return False
        if normalized_cost == 0:
            return True

        key = f"pubchat:rt:rate:{bucket}:{user_uid}"
        if self._redis:
            pipe = self._redis.pipeline(transaction=True)
            pipe.incrby(key, normalized_cost)
            pipe.ttl(key)
            count, ttl = await pipe.execute()
            if int(ttl) < 0:
                await self._redis.expire(key, max(1, int(window_seconds)))
            return int(count) <= normalized_limit

        now = time.time()
        async with self._lock:
            count, reset_at = self._fallback_rate_limits.get(
                key,
                (0, now + window_seconds),
            )
            if reset_at <= now:
                count, reset_at = 0, now + window_seconds
            count += normalized_cost
            self._fallback_rate_limits[key] = (count, reset_at)
            return count <= normalized_limit

    @staticmethod
    def _idempotency_key(user_uid: UUID | str, scope: str, event_id: str) -> str:
        digest = hashlib.sha256(event_id.encode("utf-8")).hexdigest()
        return f"pubchat:rt:idempotency:{scope}:{user_uid}:{digest}"

    async def claim_event(
        self,
        user_uid: UUID | str,
        scope: str,
        event_id: str | None,
        ttl_seconds: Optional[int] = None,
    ) -> bool:
        """
        Claim a client event before persistence.

        Returns False when the same account/scope/event id has already been seen.
        Call release_event if persistence fails so a safe retry remains possible.
        """
        if not event_id:
            return True
        normalized_event_id = str(event_id).strip()
        if not normalized_event_id or len(normalized_event_id) > 128:
            return False

        ttl = ttl_seconds or config.REALTIME_IDEMPOTENCY_TTL_SECONDS
        key = self._idempotency_key(user_uid, scope, normalized_event_id)
        if self._redis:
            return bool(await self._redis.set(key, "1", ex=ttl, nx=True))

        now = time.time()
        async with self._lock:
            expired = [item for item, expires_at in self._fallback_idempotency.items() if expires_at <= now]
            for item in expired:
                self._fallback_idempotency.pop(item, None)
            if key in self._fallback_idempotency:
                return False
            self._fallback_idempotency[key] = now + ttl
            return True

    async def release_event(
        self,
        user_uid: UUID | str,
        scope: str,
        event_id: str | None,
    ) -> None:
        if not event_id:
            return
        key = self._idempotency_key(user_uid, scope, str(event_id).strip())
        if self._redis:
            await self._redis.delete(key)
            return

        async with self._lock:
            self._fallback_idempotency.pop(key, None)


realtime_service = RealtimeService()
