"""Register the complete SQLAlchemy ORM graph for non-web processes.

FastAPI imports many domain modules through routers, which historically made mapper
registration an accidental side effect of the web composition root. Standalone
workers and integration tools must not depend on that import order.
"""

from sqlalchemy.orm import configure_mappers

# Legacy backbone first. Relationships use string class names, so importing the
# complete graph before configure_mappers() is what matters, not incidental router
# imports.
from components.user import model as _user_model  # noqa: F401
from components.room import model as _room_model  # noqa: F401
from components.message import model as _message_model  # noqa: F401
from components.message import reaction_model as _message_reaction_model  # noqa: F401
from components.device import model as _device_model  # noqa: F401

# Revival domains.
from components.identity import model as _identity_model  # noqa: F401
from components.space import model as _space_model  # noqa: F401
from components.moderation import model as _moderation_model  # noqa: F401
from components.moderation import ai_model as _moderation_ai_model  # noqa: F401
from components.moderation import abuse_model as _moderation_abuse_model  # noqa: F401
from components.moderation import media_model as _moderation_media_model  # noqa: F401
from components.transcription import model as _transcription_model  # noqa: F401
from components.engagement import model as _engagement_model  # noqa: F401
from components.engagement import occurrence_model as _occurrence_model  # noqa: F401
from components.engagement import round_model as _round_model  # noqa: F401
from components.achievement import model as _achievement_model  # noqa: F401
from components.notification import model as _notification_model  # noqa: F401
from components.support import model as _support_model  # noqa: F401


def ensure_models_registered() -> None:
    """Fail fast if any ORM string relationship cannot be resolved."""
    configure_mappers()
