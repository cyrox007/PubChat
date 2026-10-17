from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context
from settings import config as cfg

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option('sqlalchemy.url', cfg.alembic_database_url())

# Import all model modules so Alembic sees one shared Database.Base metadata.
from components.user.model import User, Penalty, UserRelationship
from components.room.model import Room, RoomMember, RoomBan
from components.message.model import Message, PrivateMessage
from components.message.reaction_model import MessageReaction
from components.message.e2ee_model import PrivateMessageEnvelope
from components.message.e2ee_attachment_model import EncryptedPrivateAttachment
from components.transcription.model import MediaTranscriptionJob
from components.reputation.model import AccountReputationAssessment
from components.social.availability_model import PersonaSocialAvailability
from components.device.model import UserDevice
from components.device.crypto_model import DeviceCryptographicIdentity, DeviceOneTimePreKey
from components.identity.model import (
    Account,
    AccountRelationship,
    AccountRole,
    Credential,
    IdentitySession,
    Persona,
    PlatformPermission,
    PlatformRole,
    PrivacySettings,
    RolePermission,
)
from components.achievement.model import AccountAchievement, AchievementDefinition
from components.engagement.model import ActivityRSVP, PersonaAppearance, SpaceActivity, SpaceAppearance
from components.engagement.occurrence_model import ActivityOccurrence
from components.engagement.round_model import ConversationRound, ConversationRoundResponse
from components.notification.model import (
    ActivityReminderPreference,
    ExternalDeliveryLedger,
    MessageNotificationPreference,
    NotificationWorkerState,
    UserNotification,
)
from components.moderation.model import ModerationAction, ModerationAppeal, ModerationReport
from components.moderation.ai_model import ModerationAIRecommendation
from components.moderation.abuse_model import TrustSafetyAbuseSignal
from components.moderation.media_model import ModerationMediaRecord
from components.support.model import (
    CosmeticEntitlement,
    CreatorSupportProfile,
    GiftDefinition,
    SpaceSupportSettings,
    SupportLedgerEntry,
)
from components.space.model import (
    SpaceEvent,
    SpaceHistoryEntry,
    SpaceInvitation,
    SpaceMembership,
    SpaceRule,
    SpaceSettings,
    SpaceTag,
)

target_metadata = User.__table__.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
