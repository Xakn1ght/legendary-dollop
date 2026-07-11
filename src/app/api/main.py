from aiohttp import web

from app.api.http_middleware import (
    admin_audit_log_middleware,
    admin_auth_middleware,
    security_headers_middleware,
)
from app.api.rate_limiter import rate_limit_middleware
from app.api.route_registry import register_all_routes
from app.api.telegram_only_middleware import telegram_only_middleware
from app.core.paths import webapp_dir
from app.core.settings import GAME_WEBAPP_HOST, GAME_WEBAPP_PORT


def build_app() -> web.Application:
    wd = webapp_dir()

    # Order matters: security headers should wrap all responses.
    # Increase max request body size because the dashboard uploads receipts as base64 JSON.
    # (base64 adds ~33% overhead; 12MB is enough for a ~8-9MB image payload.)
    app = web.Application(
        client_max_size=12 * 1024 * 1024,
        middlewares=[
            security_headers_middleware,
            telegram_only_middleware,  # Restrict dashboard to Telegram only
            rate_limit_middleware,
            admin_audit_log_middleware,
            admin_auth_middleware,
        ],
    )

    async def _cleanup_app(app_: web.Application):
        """Tear down resources when the aiohttp app stops.

        When ``embedded_user_bot`` is True (normal ``main.py`` embed), the user bot's
        shutdown handler already closes PasarGuard, Redis, DB, and both bot helper sessions;
        we only run the lightweight path here to avoid double-disposing the engine.
        """
        embedded = app_.get("embedded_user_bot", False)
        try:
            from app.utils.admin_bot_helper import close_admin_bot, close_user_bot

            await close_admin_bot()
            await close_user_bot()
        except Exception:
            pass
        if embedded:
            return
        try:
            from app.services.pasarguard import pasarguard_api

            await pasarguard_api.close()
        except Exception:
            pass
        try:
            from app.core.redis_config import close_redis

            await close_redis()
        except Exception:
            pass
        try:
            from app.database.models import engine

            await engine.dispose()
        except Exception:
            pass

    app.on_cleanup.append(_cleanup_app)

    register_all_routes(app, wd)
    return app


async def start_webserver(loop, bot=None, scheduler=None):
    app = build_app()
    # Store bot instance and scheduler in app state for use in handlers
    app["bot"] = bot
    app["scheduler"] = scheduler
    app["embedded_user_bot"] = bot is not None
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host=GAME_WEBAPP_HOST, port=GAME_WEBAPP_PORT)
    await site.start()
    return runner
