import asyncio
import unittest
from unittest.mock import AsyncMock, Mock, patch

from fastapi import HTTPException, Response
from pydantic import ValidationError
from starlette.requests import Request

from app import app
from views.identity.routers import EmailAvailabilityRequest, check_email_budget


def request_from(ip="192.0.2.40"):
    return Request({
        "type": "http",
        "method": "POST",
        "path": "/identity/v2/email-availability",
        "headers": [],
        "client": (ip, 34567),
        "server": ("pubchat.local", 80),
        "scheme": "http",
    })


class EmailAvailabilityContractTests(unittest.TestCase):
    def test_route_and_strict_email_validation(self):
        self.assertTrue(any(
            route.path == "/identity/v2/email-availability" and
            "POST" in route.methods for route in app.routes
        ))
        for email in ("not-an-email", "name@", "test@invalid..com"):
            with self.assertRaises(ValidationError):
                EmailAvailabilityRequest(email=email)

    def test_rate_limit_uses_hashed_ip_and_fails_closed(self):
        async def case():
            redis = Mock()
            redis.client.eval = AsyncMock(return_value=1)
            redis.aclose = AsyncMock()
            with patch("views.identity.routers.create_redis_client", return_value=redis):
                await check_email_budget(request_from())
            self.assertEqual(redis.client.eval.await_count, 2)
            for args, _ in redis.client.eval.call_args_list:
                key = args[2]
                self.assertIn("pubchat:identity:email_preflight:", key)
                self.assertNotIn("192.0.2.40", key)
            redis.aclose.assert_awaited_once()

            redis.client.eval = AsyncMock(side_effect=[31])
            with patch("views.identity.routers.create_redis_client", return_value=redis):
                with self.assertRaises(HTTPException) as raised:
                    await check_email_budget(request_from())
                self.assertEqual(raised.exception.status_code, 429)

            redis.client.eval = AsyncMock(side_effect=ConnectionError("offline"))
            with patch("views.identity.routers.create_redis_client", return_value=redis):
                with self.assertRaises(HTTPException) as raised:
                    await check_email_budget(request_from())
                self.assertEqual(raised.exception.status_code, 503)
        asyncio.run(case())

    def test_email_lookup_uses_identity_credential_table(self):
        route = next(
            item for item in app.routes if item.path == "/identity/v2/email-availability"
        )

        async def case(exists):
            db = Mock()
            query_result = Mock()
            query_result.scalar_one_or_none.return_value = "existing" if exists else None
            db.execute = AsyncMock(return_value=query_result)
            response = Response()
            with patch("views.identity.routers.check_email_budget", new_callable=AsyncMock) as budget:
                answer = await route.endpoint(
                    EmailAvailabilityRequest(email="User@Example.org"),
                    request_from(), response, db,
                )
                budget.assert_awaited_once()
            self.assertEqual(answer, {"available": not exists})
            self.assertEqual(response.headers["cache-control"], "no-store")
            sql = db.execute.await_args.args[0]
            self.assertIn("credentials", str(sql))
        asyncio.run(case(False))
        asyncio.run(case(True))


if __name__ == "__main__":
    unittest.main()
