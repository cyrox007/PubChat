import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy.engine import URL

load_dotenv()


def _env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, "true" if default else "false").strip().lower() in {"1", "true", "yes", "on"}


def _optional_positive_int(name: str) -> int | None:
    raw = os.getenv(name, "").strip()
    if not raw:
        return None
    return max(1, int(raw))


class Config:
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"

    # Frontend
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173").split(",")

    # Server
    SERVER_HTTP_PROTOCOL = os.getenv("SERVER_HTTP_PROTOCOL", "http://")
    SERVER_ADDR = os.getenv("SERVER_ADDR", "localhost")
    SERVER_PORT = os.getenv("SERVER_PORT", "9000")

    @property
    def BASE_URL(self):
        protocol = self.SERVER_HTTP_PROTOCOL
        address = self.SERVER_ADDR
        port = self.SERVER_PORT
        if port in ["80", "443"]:
            return f"{protocol}{address}"
        return f"{protocol}{address}:{port}"

    # Database
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_NAME = os.getenv("DB_NAME", "chat")
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
    # Each web/worker process has its own pool; rolling reloads overlap processes.
    DB_POOL_SIZE = max(1, min(200, int(os.getenv("DB_POOL_SIZE", "5"))))
    DB_POOL_MAX_OVERFLOW = max(0, min(200, int(os.getenv("DB_POOL_MAX_OVERFLOW", "0"))))
    DB_POOL_TIMEOUT_SECONDS = max(1, min(120, int(os.getenv("DB_POOL_TIMEOUT_SECONDS", "30"))))
    DB_POOL_ALERT_UTILIZATION_PERCENT = max(
        50,
        min(100, int(os.getenv("DB_POOL_ALERT_UTILIZATION_PERCENT", "85"))),
    )
    DB_POOL_MIN_HEADROOM_CONNECTIONS = max(
        1,
        min(
            max(1, (DB_POOL_SIZE + DB_POOL_MAX_OVERFLOW) // 4),
            int(os.getenv("DB_POOL_MIN_HEADROOM_CONNECTIONS", "3")),
        ),
    )

    # Redis / realtime
    # Direct topology remains the default/backward-compatible mode. When both
    # Sentinel fields below are configured, Sentinel takes precedence and
    # REDIS_URL is ignored by the realtime client factory.
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0" if DEBUG else "")
    REDIS_MAX_CONNECTIONS = max(4, int(os.getenv("REDIS_MAX_CONNECTIONS", "100")))
    REDIS_POOL_ALERT_UTILIZATION_PERCENT = max(
        50,
        min(100, int(os.getenv("REDIS_POOL_ALERT_UTILIZATION_PERCENT", "85"))),
    )
    REDIS_POOL_MIN_HEADROOM_CONNECTIONS = max(
        1,
        min(
            max(1, REDIS_MAX_CONNECTIONS // 4),
            int(os.getenv("REDIS_POOL_MIN_HEADROOM_CONNECTIONS", "5")),
        ),
    )
    REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS = float(
        os.getenv("REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS", "5")
    )
    REDIS_SOCKET_TIMEOUT_SECONDS = float(os.getenv("REDIS_SOCKET_TIMEOUT_SECONDS", "5"))
    REDIS_SENTINEL_NODES = os.getenv("REDIS_SENTINEL_NODES", "")
    REDIS_SENTINEL_MASTER = os.getenv("REDIS_SENTINEL_MASTER", "")
    REDIS_SENTINEL_MIN_OTHER_SENTINELS = max(
        0, int(os.getenv("REDIS_SENTINEL_MIN_OTHER_SENTINELS", "0"))
    )
    REDIS_SENTINEL_USERNAME = os.getenv("REDIS_SENTINEL_USERNAME", "")
    REDIS_SENTINEL_PASSWORD = os.getenv("REDIS_SENTINEL_PASSWORD", "")
    REDIS_USERNAME = os.getenv("REDIS_USERNAME", "")
    REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")
    REDIS_DB = max(0, int(os.getenv("REDIS_DB", "0")))

    REALTIME_TICKET_TTL_SECONDS = int(os.getenv("REALTIME_TICKET_TTL_SECONDS", "30"))
    REALTIME_AUTH_TIMEOUT_SECONDS = int(os.getenv("REALTIME_AUTH_TIMEOUT_SECONDS", "8"))
    REALTIME_PRESENCE_TTL_SECONDS = int(os.getenv("REALTIME_PRESENCE_TTL_SECONDS", "90"))
    REALTIME_HEARTBEAT_SECONDS = int(os.getenv("REALTIME_HEARTBEAT_SECONDS", "25"))
    REALTIME_SEND_TIMEOUT_SECONDS = float(os.getenv("REALTIME_SEND_TIMEOUT_SECONDS", "5"))
    REALTIME_OUTBOUND_QUEUE_SIZE = max(1, int(os.getenv("REALTIME_OUTBOUND_QUEUE_SIZE", "64")))
    REALTIME_MESSAGE_RATE_LIMIT = int(os.getenv("REALTIME_MESSAGE_RATE_LIMIT", "25"))
    REALTIME_MESSAGE_RATE_WINDOW_SECONDS = int(os.getenv("REALTIME_MESSAGE_RATE_WINDOW_SECONDS", "10"))
    REALTIME_IDEMPOTENCY_TTL_SECONDS = int(os.getenv("REALTIME_IDEMPOTENCY_TTL_SECONDS", "600"))

    # Message external delivery. External channels remain opt-in at the Account
    # preference layer. Safe minimums prevent accidental high-frequency nudges.
    MESSAGE_EMAIL_NUDGE_INACTIVITY_MINUTES = max(
        60, int(os.getenv("MESSAGE_EMAIL_NUDGE_INACTIVITY_MINUTES", "720"))
    )
    MESSAGE_EMAIL_NUDGE_COOLDOWN_MINUTES = max(
        60, int(os.getenv("MESSAGE_EMAIL_NUDGE_COOLDOWN_MINUTES", "1440"))
    )
    MESSAGE_EMAIL_DELIVERY_MAX_ATTEMPTS = max(
        1, int(os.getenv("MESSAGE_EMAIL_DELIVERY_MAX_ATTEMPTS", "5"))
    )
    MESSAGE_EMAIL_DELIVERY_RETRY_BASE_SECONDS = max(
        60, int(os.getenv("MESSAGE_EMAIL_DELIVERY_RETRY_BASE_SECONDS", "300"))
    )
    MESSAGE_EMAIL_DELIVERY_RETRY_MAX_SECONDS = max(
        MESSAGE_EMAIL_DELIVERY_RETRY_BASE_SECONDS,
        int(os.getenv("MESSAGE_EMAIL_DELIVERY_RETRY_MAX_SECONDS", "21600")),
    )
    MESSAGE_EMAIL_DELIVERY_LEASE_SECONDS = max(
        60, int(os.getenv("MESSAGE_EMAIL_DELIVERY_LEASE_SECONDS", "300"))
    )
    MESSAGE_EMAIL_DELIVERY_BATCH_SIZE = max(
        1, min(250, int(os.getenv("MESSAGE_EMAIL_DELIVERY_BATCH_SIZE", "50")))
    )
    MESSAGE_EMAIL_ONLINE_RECHECK_SECONDS = max(
        60, int(os.getenv("MESSAGE_EMAIL_ONLINE_RECHECK_SECONDS", "900"))
    )

    # SMTP transport. It is intentionally disabled until HOST and FROM_EMAIL are
    # explicitly configured. Username/password may be omitted for a trusted relay.
    MESSAGE_EMAIL_SMTP_HOST = os.getenv("MESSAGE_EMAIL_SMTP_HOST", "").strip()
    MESSAGE_EMAIL_SMTP_PORT = int(os.getenv("MESSAGE_EMAIL_SMTP_PORT", "587"))
    MESSAGE_EMAIL_SMTP_USERNAME = os.getenv("MESSAGE_EMAIL_SMTP_USERNAME", "").strip()
    MESSAGE_EMAIL_SMTP_PASSWORD = os.getenv("MESSAGE_EMAIL_SMTP_PASSWORD", "")
    MESSAGE_EMAIL_SMTP_STARTTLS = _env_bool("MESSAGE_EMAIL_SMTP_STARTTLS", True)
    MESSAGE_EMAIL_SMTP_USE_SSL = _env_bool("MESSAGE_EMAIL_SMTP_USE_SSL", False)
    MESSAGE_EMAIL_SMTP_TIMEOUT_SECONDS = max(
        1.0, float(os.getenv("MESSAGE_EMAIL_SMTP_TIMEOUT_SECONDS", "10"))
    )
    MESSAGE_EMAIL_FROM_EMAIL = os.getenv("MESSAGE_EMAIL_FROM_EMAIL", "").strip()
    MESSAGE_EMAIL_FROM_NAME = os.getenv("MESSAGE_EMAIL_FROM_NAME", "PubChat").strip() or "PubChat"

    # Standards-based Web Push. VAPID keys are optional at application startup;
    # the standalone push worker refuses to start until the full key pair and
    # contact subject are configured. Payloads remain generic/privacy-minimal.
    WEB_PUSH_VAPID_PUBLIC_KEY = os.getenv("WEB_PUSH_VAPID_PUBLIC_KEY", "").strip()
    WEB_PUSH_VAPID_PRIVATE_KEY = os.getenv("WEB_PUSH_VAPID_PRIVATE_KEY", "").strip()
    WEB_PUSH_VAPID_SUBJECT = os.getenv("WEB_PUSH_VAPID_SUBJECT", "").strip()
    WEB_PUSH_TTL_SECONDS = max(60, int(os.getenv("WEB_PUSH_TTL_SECONDS", "300")))
    WEB_PUSH_DELIVERY_MAX_ATTEMPTS = max(1, int(os.getenv("WEB_PUSH_DELIVERY_MAX_ATTEMPTS", "5")))
    WEB_PUSH_DELIVERY_RETRY_BASE_SECONDS = max(
        30, int(os.getenv("WEB_PUSH_DELIVERY_RETRY_BASE_SECONDS", "60"))
    )
    WEB_PUSH_DELIVERY_RETRY_MAX_SECONDS = max(
        WEB_PUSH_DELIVERY_RETRY_BASE_SECONDS,
        int(os.getenv("WEB_PUSH_DELIVERY_RETRY_MAX_SECONDS", "1800")),
    )
    WEB_PUSH_DELIVERY_LEASE_SECONDS = max(
        60, int(os.getenv("WEB_PUSH_DELIVERY_LEASE_SECONDS", "180"))
    )
    WEB_PUSH_DELIVERY_BATCH_SIZE = max(
        1, min(250, int(os.getenv("WEB_PUSH_DELIVERY_BATCH_SIZE", "50")))
    )
    WEB_PUSH_CONVERSATION_COOLDOWN_SECONDS = max(
        30, int(os.getenv("WEB_PUSH_CONVERSATION_COOLDOWN_SECONDS", "90"))
    )

    # Privacy-safe external delivery observability. These thresholds do not
    # change delivery behavior; they only mark operational backlog as unhealthy.
    EXTERNAL_DELIVERY_EMAIL_BACKLOG_ALERT_SECONDS = max(
        300,
        min(
            86400,
            int(os.getenv("EXTERNAL_DELIVERY_EMAIL_BACKLOG_ALERT_SECONDS", "3600")),
        ),
    )
    EXTERNAL_DELIVERY_WEB_PUSH_BACKLOG_ALERT_SECONDS = max(
        60,
        min(
            3600,
            int(os.getenv("EXTERNAL_DELIVERY_WEB_PUSH_BACKLOG_ALERT_SECONDS", "300")),
        ),
    )

    # Security. There are intentionally no production-capable default secrets.
    JWT_ACCESS_SECRET_KEY = os.getenv("JWT_ACCESS_SECRET_KEY", "")
    JWT_REFRESH_SECRET_KEY = os.getenv("JWT_REFRESH_SECRET_KEY", "")
    CSRF_SECRET_KEY = os.getenv("CSRF_SECRET_KEY", "")
    JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
    REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30"))
    CSRF_TOKEN_EXPIRE_MINUTES = int(os.getenv("CSRF_TOKEN_EXPIRE_MINUTES", "30"))

    # Paths
    STATICS_DIRNAME = os.getenv("STATICS_DIRNAME", "static")

    def ensure_security_settings(self):
        secrets = {
            "JWT_ACCESS_SECRET_KEY": self.JWT_ACCESS_SECRET_KEY,
            "JWT_REFRESH_SECRET_KEY": self.JWT_REFRESH_SECRET_KEY,
            "CSRF_SECRET_KEY": self.CSRF_SECRET_KEY,
        }
        missing = [name for name, value in secrets.items() if len(value) < 32]
        if missing:
            raise RuntimeError(
                f"{', '.join(missing)} must be configured with at least 32 characters"
            )
        if len(set(secrets.values())) != len(secrets):
            raise RuntimeError("JWT access, refresh and CSRF secrets must be different")

    def redis_configured(self) -> bool:
        sentinel_nodes = self.REDIS_SENTINEL_NODES.strip()
        sentinel_master = self.REDIS_SENTINEL_MASTER.strip()
        return bool(self.REDIS_URL or (sentinel_nodes and sentinel_master))

    def ensure_realtime_settings(self) -> None:
        sentinel_nodes = self.REDIS_SENTINEL_NODES.strip()
        sentinel_master = self.REDIS_SENTINEL_MASTER.strip()
        if bool(sentinel_nodes) != bool(sentinel_master):
            raise RuntimeError(
                "REDIS_SENTINEL_NODES and REDIS_SENTINEL_MASTER must be configured together"
            )
        if not self.DEBUG and not self.redis_configured():
            raise RuntimeError(
                "Production realtime requires REDIS_URL or Redis Sentinel configuration"
            )

    def message_email_delivery_configured(self) -> bool:
        auth_pair_valid = bool(self.MESSAGE_EMAIL_SMTP_USERNAME) == bool(self.MESSAGE_EMAIL_SMTP_PASSWORD)
        tls_valid = not (self.MESSAGE_EMAIL_SMTP_STARTTLS and self.MESSAGE_EMAIL_SMTP_USE_SSL)
        return bool(
            self.MESSAGE_EMAIL_SMTP_HOST
            and self.MESSAGE_EMAIL_FROM_EMAIL
            and auth_pair_valid
            and tls_valid
        )

    def ensure_message_email_delivery_settings(self) -> None:
        if self.MESSAGE_EMAIL_SMTP_STARTTLS and self.MESSAGE_EMAIL_SMTP_USE_SSL:
            raise RuntimeError("MESSAGE_EMAIL_SMTP_STARTTLS and MESSAGE_EMAIL_SMTP_USE_SSL are mutually exclusive")
        if bool(self.MESSAGE_EMAIL_SMTP_USERNAME) != bool(self.MESSAGE_EMAIL_SMTP_PASSWORD):
            raise RuntimeError("MESSAGE_EMAIL_SMTP_USERNAME and MESSAGE_EMAIL_SMTP_PASSWORD must be configured together")
        if not self.MESSAGE_EMAIL_SMTP_HOST:
            raise RuntimeError("MESSAGE_EMAIL_SMTP_HOST must be configured before enabling the email worker")
        if not self.MESSAGE_EMAIL_FROM_EMAIL:
            raise RuntimeError("MESSAGE_EMAIL_FROM_EMAIL must be configured before enabling the email worker")

    def web_push_configured(self) -> bool:
        return bool(
            self.WEB_PUSH_VAPID_PUBLIC_KEY
            and self.WEB_PUSH_VAPID_PRIVATE_KEY
            and self.WEB_PUSH_VAPID_SUBJECT
        )

    def ensure_web_push_settings(self) -> None:
        if not self.WEB_PUSH_VAPID_PUBLIC_KEY:
            raise RuntimeError("WEB_PUSH_VAPID_PUBLIC_KEY must be configured before enabling Web Push")
        if not self.WEB_PUSH_VAPID_PRIVATE_KEY:
            raise RuntimeError("WEB_PUSH_VAPID_PRIVATE_KEY must be configured before enabling Web Push")
        if not self.WEB_PUSH_VAPID_SUBJECT:
            raise RuntimeError("WEB_PUSH_VAPID_SUBJECT must be configured before enabling Web Push")
        if not (
            self.WEB_PUSH_VAPID_SUBJECT.startswith("mailto:")
            or self.WEB_PUSH_VAPID_SUBJECT.startswith("https://")
        ):
            raise RuntimeError("WEB_PUSH_VAPID_SUBJECT must be a mailto: or https:// contact URI")

    def database_url(self, async_mode=False):
        driver = "postgresql+asyncpg" if async_mode else "postgresql"
        return URL.create(
            drivername=driver,
            username=self.DB_USER,
            password=self.DB_PASSWORD,
            host=self.DB_HOST,
            port=int(self.DB_PORT),
            database=self.DB_NAME,
        ).render_as_string(hide_password=False)

    def alembic_database_url(self):
        """Return a ConfigParser-safe SQLAlchemy URL for Alembic.

        Alembic stores sqlalchemy.url through Python ConfigParser. Percent-encoded
        credentials (for example a backslash rendered as %5C) must therefore
        escape literal percent signs as %% before set_main_option().
        ConfigParser resolves %% back to % when the value is read.
        """
        return self.database_url().replace("%", "%%")

    # Moderation private evidence. This directory must be a dedicated sibling
    # (or otherwise disjoint path) from the public uploads tree.
    MODERATION_MEDIA_ROOT = os.getenv("MODERATION_MEDIA_ROOT", "moderation_media").strip() or "moderation_media"
    MODERATION_MEDIA_REMOVED_RETENTION_DAYS = max(
        7, min(365, int(os.getenv("MODERATION_MEDIA_REMOVED_RETENTION_DAYS", "90")))
    )
    MODERATION_MEDIA_RETENTION_BATCH_SIZE = max(
        1, min(500, int(os.getenv("MODERATION_MEDIA_RETENTION_BATCH_SIZE", "100")))
    )
    MODERATION_MEDIA_BACKUP_RETENTION_DAYS = _optional_positive_int(
        "MODERATION_MEDIA_BACKUP_RETENTION_DAYS"
    )
    MODERATION_MEDIA_SNAPSHOT_RETENTION_DAYS = _optional_positive_int(
        "MODERATION_MEDIA_SNAPSHOT_RETENTION_DAYS"
    )

    def moderation_media_storage_lifecycle_status(self) -> dict:
        app_days = self.MODERATION_MEDIA_REMOVED_RETENTION_DAYS
        backup_days = self.MODERATION_MEDIA_BACKUP_RETENTION_DAYS
        snapshot_days = self.MODERATION_MEDIA_SNAPSHOT_RETENTION_DAYS
        declared = backup_days is not None and snapshot_days is not None
        aligned = bool(
            declared
            and backup_days <= app_days
            and snapshot_days <= app_days
        )
        return {
            "application_retention_days": app_days,
            "backup_retention_days": backup_days,
            "snapshot_retention_days": snapshot_days,
            "declared": declared,
            "aligned": aligned,
        }

    def ensure_moderation_media_retention_settings(
        self, *, require_storage_lifecycle: bool = False
    ) -> None:
        public_root = Path("uploads").resolve()
        private_root = Path(self.MODERATION_MEDIA_ROOT).resolve()
        if (
            private_root == public_root
            or private_root in public_root.parents
            or public_root in private_root.parents
        ):
            raise RuntimeError(
                "MODERATION_MEDIA_ROOT must be a dedicated path disjoint from public uploads"
            )

        lifecycle = self.moderation_media_storage_lifecycle_status()
        if require_storage_lifecycle and not lifecycle["declared"]:
            raise RuntimeError(
                "MODERATION_MEDIA_BACKUP_RETENTION_DAYS and "
                "MODERATION_MEDIA_SNAPSHOT_RETENTION_DAYS must be declared"
            )
        if lifecycle["backup_retention_days"] is not None and (
            lifecycle["backup_retention_days"]
            > lifecycle["application_retention_days"]
        ):
            raise RuntimeError(
                "Moderation media backup retention may not exceed application retention"
            )
        if lifecycle["snapshot_retention_days"] is not None and (
            lifecycle["snapshot_retention_days"]
            > lifecycle["application_retention_days"]
        ):
            raise RuntimeError(
                "Moderation media snapshot retention may not exceed application retention"
            )

    # File storage
    UPLOADS_BASE_URL = f"{SERVER_HTTP_PROTOCOL}{SERVER_ADDR}/uploads/"
    MAX_FILE_SIZE = max(
        64 * 1024,
        min(50 * 1024 * 1024, int(os.getenv("MAX_FILE_SIZE", 10 * 1024 * 1024))),
    )
    MAX_FILES_LIMIT = max(1, min(10, int(os.getenv("MAX_FILES_LIMIT", "10"))))
    MAX_MESSAGE_MEDIA_TOTAL_SIZE = max(
        MAX_FILE_SIZE,
        min(
            100 * 1024 * 1024,
            int(os.getenv("MAX_MESSAGE_MEDIA_TOTAL_SIZE", 25 * 1024 * 1024)),
        ),
    )
    MEDIA_UPLOAD_RATE_LIMIT_BYTES = max(
        MAX_MESSAGE_MEDIA_TOTAL_SIZE,
        min(
            1024 * 1024 * 1024,
            int(os.getenv("MEDIA_UPLOAD_RATE_LIMIT_BYTES", 50 * 1024 * 1024)),
        ),
    )
    MEDIA_UPLOAD_RATE_WINDOW_SECONDS = max(
        10,
        min(3600, int(os.getenv("MEDIA_UPLOAD_RATE_WINDOW_SECONDS", "60"))),
    )


config = Config()
