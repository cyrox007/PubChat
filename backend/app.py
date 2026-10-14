import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from components.realtime import realtime_service
from middlewares import csrf_middleware, error_handling_middleware, security_headers_middleware
from settings import config
from utils.version import PROJECT_VERSION


@asynccontextmanager
async def lifespan(app: FastAPI):
    await realtime_service.start()
    try:
        yield
    finally:
        await realtime_service.stop()


def create_app() -> FastAPI:
    from views.admin import operations_routers as admin_operations_routes
    from views.admin import profile_routers as admin_profile_routes
    from views.admin import routers as admin_routers
    from views.achievements import routers as achievement_routes
    from views.calls import ws_routers as call_ws_routes
    from views.csrf import routers as csrf_routes
    from views.discovery import routers as discovery_routes
    from views.engagement import round_routers as engagement_round_routes
    from views.engagement import routers as engagement_routes
    from views.identity import routers as identity_routes
    from views.messages import routers as message_routes
    from views.messenger import routers as http_routers_messenger
    from views.messenger import ws_routers as ws_routers_messenger
    from views.moderation import ai_routers as moderation_ai_routes
    from views.moderation import abuse_routers as moderation_abuse_routes
    from views.moderation import media_routers as moderation_media_routes
    from views.moderation import operations_routers as moderation_operations_routes
    from views.moderation import restriction_routers as moderation_restriction_routes
    from views.moderation import routers as moderation_routes
    from views.notifications import routers as notification_routes
    from views.realtime import routers as realtime_routes
    from views.rooms import routers as http_routes_chat
    from views.rooms import ws_routers as ws_routes_chat
    from views.service import routers as service_routes
    from views.social import routers as social_routes
    from views.spaces import routers as spaces_routes
    from views.support import routers as support_routes
    from views.users import routers as user_routes

    app = FastAPI(title="PubChat API", version=PROJECT_VERSION, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.FRONTEND_URL,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["*"],
    )

    app.mount("/static", StaticFiles(directory="static"), name="static")
    if not os.path.exists("uploads"):
        os.makedirs("uploads")
    app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

    csrf_middleware(app)
    error_handling_middleware(app)
    security_headers_middleware(app)

    csrf_routes.install(app)
    service_routes.install(app)
    identity_routes.install(app)
    achievement_routes.install(app)
    realtime_routes.install(app)
    notification_routes.install(app)
    support_routes.install(app)
    discovery_routes.install(app)
    user_routes.install(app)
    social_routes.install(app)
    spaces_routes.install(app)
    moderation_routes.install(app)
    moderation_restriction_routes.install(app)
    moderation_ai_routes.install(app)
    moderation_abuse_routes.install(app)
    moderation_media_routes.install(app)
    moderation_operations_routes.install(app)
    engagement_routes.install(app)
    engagement_round_routes.install(app)
    http_routes_chat.install(app)
    ws_routes_chat.install(app)
    http_routers_messenger.install(app)
    ws_routers_messenger.install(app)
    call_ws_routes.install(app)
    message_routes.install(app)
    admin_routers.install(app)
    admin_profile_routes.install(app)
    admin_operations_routes.install(app)

    return app


app = create_app()
