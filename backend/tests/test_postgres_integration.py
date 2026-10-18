import asyncio
import os
import unittest
from tests.test_realtime_database_lifetime import RealtimeDatabasePoolIntegrationTests  # noqa: F401

from sqlalchemy import text

from components.model_registry import ensure_models_registered
from components.notification.model import NotificationWorkerState
from components.notification.worker_service import WORKER_NAME_ACTIVITY_REMINDERS, lock_worker_state
from database import Database
from tests.test_account_access_postgres_integration import AccountAccessPostgresIntegrationTests  # noqa: F401
from tests.test_external_delivery_observability_postgres_integration import (  # noqa: F401
    ExternalDeliveryObservabilityPostgresIntegrationTests,
)
from tests.test_discovery_candidates_postgres_integration import (  # noqa: F401
    DiscoveryCandidatesPostgresIntegrationTests,
)
from tests.test_discovery_performance_postgres_integration import (  # noqa: F401
    DiscoveryPerformancePostgresIntegrationTests,
)
from tests.test_discovery_privacy_large_pool_postgres_integration import (  # noqa: F401
    DiscoveryPrivacyLargePoolPostgresIntegrationTests,
)
from tests.test_abuse_signal_postgres_integration import AbuseSignalPostgresIntegrationTests  # noqa: F401
from tests.test_moderation_ai_postgres_integration import ModerationAIPostgresIntegrationTests  # noqa: F401
from tests.test_moderation_media_postgres_integration import ModerationMediaPostgresIntegrationTests  # noqa: F401
from tests.test_moderation_media_retention_postgres_integration import (  # noqa: F401
    ModerationMediaRetentionPostgresIntegrationTests,
)
from tests.test_platform_restriction_appeals_postgres_integration import (  # noqa: F401
    PlatformRestrictionAppealPostgresIntegrationTests,
)
from tests.test_platform_restrictions_postgres_integration import (  # noqa: F401
    PlatformRestrictionPostgresIntegrationTests,
)
from tests.test_trust_safety_postgres_integration import TrustSafetyPostgresIntegrationTests  # noqa: F401
from tests.test_trust_safety_operations_postgres_integration import (  # noqa: F401
    TrustSafetyOperationsPostgresIntegrationTests,
)
from tests.test_protective_hold_calibration_postgres_integration import (  # noqa: F401
    ProtectiveHoldCalibrationPostgresIntegrationTests,
)
from tests.test_space_capacity_postgres_integration import (  # noqa: F401
    SpaceCapacityPostgresIntegrationTests,
)


@unittest.skipUnless(
    os.getenv("PUBCHAT_POSTGRES_INTEGRATION") == "1",
    "PostgreSQL integration environment is not enabled",
)
class PostgreSQLIntegrationTests(unittest.TestCase):
    def test_migrated_schema_and_async_session(self):
        async def run_case():
            ensure_models_registered()
            session = await Database.get_session()
            try:
                database_name = (await session.execute(text("SELECT current_database()"))).scalar_one()
                self.assertEqual(database_name, os.getenv("DB_NAME", "chat"))

                tables = {
                    name: (await session.execute(text("SELECT to_regclass(:name)"), {"name": f"public.{name}"})).scalar_one()
                    for name in (
                        "users",
                        "accounts",
                        "rooms",
                        "user_notifications",
                        "notification_worker_state",
                        "external_delivery_ledger",
                        "web_push_subscriptions",
                        "trust_safety_reports",
                        "trust_safety_audit_events",
                        "platform_restrictions",
                        "platform_restriction_audit_events",
                        "platform_restriction_appeals",
                        "moderation_ai_recommendations",
                        "trust_safety_abuse_signals",
                        "moderation_media_records",
                        "alembic_version",
                    )
                }
                self.assertTrue(all(tables.values()), tables)

                worker_state = await session.get(
                    NotificationWorkerState,
                    WORKER_NAME_ACTIVITY_REMINDERS,
                )
                self.assertIsNotNone(worker_state)

                locked = await lock_worker_state(session)
                self.assertIsNotNone(locked)
                self.assertEqual(locked.worker_name, WORKER_NAME_ACTIVITY_REMINDERS)
                await session.rollback()
            finally:
                await session.close()
                await Database.dispose()

        asyncio.run(run_case())


if __name__ == "__main__":
    unittest.main()
