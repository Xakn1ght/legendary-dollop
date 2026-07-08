import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from app.core.redis_config import close_redis, init_redis
from app.core.settings import ADMIN_BOT_TOKEN, security_sanity_warnings
from app.database.models import AsyncSessionLocal, engine, init_db
from app.handlers.admin import (
    bot_texts,
    broadcast,
    cache,
    charge,
    dashboard,
    deletion_requests,
    financial,
    gifts,
    indexes,
    menu,
    reward_settings,
    service_management,
    stats,
    subscription,
    support,
    system,
    toggle,
    user_management,
    vip,
)
from app.handlers.admin import (
    settings as admin_settings,
)
from app.handlers.admin.common import ADMIN_IDS
from app.utils.error_middleware import ErrorHandlingMiddleware
from app.utils.logger import bot_logger, log_error, setup_logging


def _telegram_user_from_event(event):
    """Resolve actor on outer ``dp.update`` middleware (event is often a full Update)."""
    user = getattr(event, "from_user", None)
    if user is not None:
        return user
    cb = getattr(event, "callback_query", None)
    if cb is not None:
        return getattr(cb, "from_user", None)
    msg = getattr(event, "message", None)
    if msg is not None:
        return getattr(msg, "from_user", None)
    edited = getattr(event, "edited_message", None)
    if edited is not None:
        return getattr(edited, "from_user", None)
    return None


class AdminOnlyMiddleware:
    """Drop any update that is not from ADMIN_ID."""

    async def __call__(self, handler, event, data):
        try:
            user = _telegram_user_from_event(event)
            if not user or user.id not in ADMIN_IDS:
                return
        except Exception:
            return
        return await handler(event, data)


class DbSessionMiddleware:
    def __init__(self, session_pool):
        self.session_pool = session_pool

    async def __call__(self, handler, event, data):
        async with self.session_pool() as session:
            data["session"] = session
            return await handler(event, data)


async def main() -> None:
    setup_logging(log_level="INFO", log_file="logs/admin_bot.log")
    bot_logger.info("Starting ASSTRO admin bot (isolated)...")

    # Only log critical config; admin bot runs separately from user bot
    if not ADMIN_BOT_TOKEN:
        bot_logger.critical("ADMIN_BOT_TOKEN is missing. Set it in .env then restart.")
        return

    # Initialize DB + Redis (needed by admin handlers)
    try:
        await init_db()
    except Exception as e:
        log_error(e, {"operation": "admin_bot_db_init"})
        bot_logger.critical("Failed to initialize database. Exiting.")
        return

    try:
        await init_redis()
    except Exception as e:
        log_error(e, {"operation": "admin_bot_redis_init"})
        bot_logger.warning("Redis init failed for admin bot, continuing without cache")

    # aiogram 3.7+ dropped the `default_parse_mode` kwarg; it was silently
    # swallowed by **kwargs so /errors etc. showed raw <b> tags (audit fix).
    bot = Bot(token=ADMIN_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    # Middlewares
    dp.update.outer_middleware.register(ErrorHandlingMiddleware())
    dp.update.outer_middleware.register(AdminOnlyMiddleware())
    dp.update.outer_middleware.register(DbSessionMiddleware(session_pool=AsyncSessionLocal))

    # Routers (all admin features)
    routers = [
        menu.router,
        subscription.router,
        charge.router,
        toggle.router,
        deletion_requests.router,
        broadcast.router,
        cache.router,
        dashboard.router,
        financial.router,
        gifts.router,
        indexes.router,
        reward_settings.router,
        service_management.router,
        admin_settings.router,
        stats.router,
        support.router,
        system.router,
        user_management.router,
        vip.router,
        # LAST on purpose: its free-text handler catches search/edit input
        # only after every other admin text handler declined the update.
        bot_texts.router,
    ]
    for r in routers:
        try:
            dp.include_router(r)
        except Exception as e:
            bot_logger.warning(f"Failed to include admin router: {e}")

    try:
        await bot.set_my_commands(
            [
                BotCommand(command="start", description="Start"),
                BotCommand(command="admin", description="Open admin panel"),
            ]
        )
    except Exception:
        pass

    async def shutdown():
        try:
            await close_redis()
        except Exception:
            pass
        try:
            from app.utils.admin_bot_helper import close_user_bot

            await close_user_bot()
        except Exception:
            pass
        try:
            await engine.dispose()
        except Exception:
            pass

    dp.shutdown.register(shutdown)

    # Watchdog: alert admins when the user bot / web server stops answering.
    watchdog_task = None
    try:
        from app.utils.service_watchdog import service_watchdog

        watchdog_task = asyncio.create_task(service_watchdog(bot))
    except Exception as e:
        bot_logger.warning(f"Failed to start service watchdog: {e}")

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        bot_logger.info("Admin bot ready, starting polling...")
        await dp.start_polling(bot)
    except Exception as e:
        log_error(e, {"operation": "admin_bot_startup"})
        bot_logger.critical(f"Failed to start admin bot polling: {e}. Exiting.")
    finally:
        if watchdog_task is not None:
            watchdog_task.cancel()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        bot_logger.info("Admin bot stopped by user.")
    except Exception as e:
        log_error(e, {"operation": "admin_main_execution"})
        bot_logger.critical("Admin bot crashed with unhandled exception.")
