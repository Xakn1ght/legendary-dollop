import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.redis_config import close_redis, init_redis
from app.core.settings import BOT_TOKEN, DATABASE_URL, JOB_SCHEDULES, security_sanity_warnings
from app.database.models import AsyncSessionLocal, engine, init_db
from app.handlers.user import (
    add_subscription,
    charge,
    common,
    flow_inline,
    my_services,
    purchase,
    referral,
    sms_receipts,
    start,
    support,
    tutorials,
)
from app.handlers.user import game as game_router
from app.handlers.user.rewards import challenges as challenges_router
from app.handlers.user.rewards import router as rewards_router
from app.handlers.user.rewards import star_levels as star_levels_router
from app.jobs.arcade_prizes import arcade_monthly_prizes_job
from app.jobs.arcade_rounds import arcade_round_sweep_job
from app.jobs.cleanup_draft_orders import cleanup_draft_orders_job
from app.jobs.enhanced_rewards import update_user_analytics_job
from app.jobs.expire_claims import expire_star_reward_claims_job
from app.jobs.node_watch import node_watch_job
from app.jobs.notifications import check_low_data_job
from app.jobs.renewal import renewal_job
from app.jobs.season_reset import season_reset_job
from app.jobs.sms_sweep import sms_sweep_job
from app.services.pasarguard import pasarguard_api
from app.utils.banned_user_middleware import BannedUserMiddleware
from app.utils.bot_session import bot_session
from app.utils.error_middleware import (
    ErrorHandlingMiddleware,
    PerformanceMiddleware,
    RateLimitMiddleware,
    ValidationMiddleware,
)
from app.utils.logger import bot_logger, log_error, log_job_execution, setup_logging
from app.utils.webapp_lock_middleware import WebappLockMiddleware

# Notification queue for real-time alerts
notification_queue = asyncio.Queue()
from app.webserver import start_webserver

http_runner = None  # set when embedded web server starts; cleaned up before DB dispose
_fsm_redis = None  # closed on shutdown when using Redis FSM storage


async def _create_fsm_storage():
    """Persist FSM in Redis so restarts do not drop referral onboarding mid-flow."""
    global _fsm_redis
    _fsm_redis = None
    try:
        from aiogram.fsm.storage.redis import DefaultKeyBuilder, RedisStorage
        from redis.asyncio import Redis

        from app.core.settings import REDIS_FSM_DB, REDIS_HOST, REDIS_PASSWORD, REDIS_PORT

        auth = f":{REDIS_PASSWORD}@" if REDIS_PASSWORD else ""
        url = f"redis://{auth}{REDIS_HOST}:{REDIS_PORT}/{REDIS_FSM_DB}"
        client = Redis.from_url(url, decode_responses=True)
        await client.ping()
        _fsm_redis = client
        bot_logger.info("FSM storage: Redis (persistent across restarts)")
        return RedisStorage(redis=client, key_builder=DefaultKeyBuilder(with_bot_id=True))
    except Exception as e:
        bot_logger.warning(f"FSM: using in-memory storage (Redis unavailable: {e})")
        return MemoryStorage()


class DbSessionMiddleware:
    def __init__(self, session_pool):
        self.session_pool = session_pool

    async def __call__(self, handler, event, data):
        async with self.session_pool() as session:
            data["session"] = session
            return await handler(event, data)

class DispatcherMiddleware:
    def __init__(self, dp):
        self.dp = dp

    async def __call__(self, handler, event, data):
        data['dispatcher'] = self.dp
        return await handler(event, data)

async def notification_worker(queue: asyncio.Queue, bot: Bot):
    """Watches the notification queue and sends messages to users."""
    bot_logger.info("Notification worker started.")
    while True:
        try:
            # Wait for a notification event
            event = await queue.get()
            bot_logger.debug(f"Notification event: {event}")

            user_id = event.get("user_id")
            message_text = event.get("message")

            if not user_id or not message_text:
                bot_logger.warning(f"Invalid notification event: {event}")
                queue.task_done()
                continue

            # We need a new session for this self-contained task
            async with AsyncSessionLocal() as session:
                from app.database.crud import get_user_by_id
                user = await get_user_by_id(session, user_id)
                if user and user.chat_id:
                    bot_logger.debug(f"Sending notification to user {user_id}")
                    try:
                        await bot.send_message(user.chat_id, message_text, parse_mode='Markdown')
                        bot_logger.debug(f"Notification sent to user {user_id}")
                    except Exception as e:
                        log_error(e, {"operation": "notification_send", "user_id": user_id})
                else:
                    bot_logger.warning(f"Could not find user or chat_id for user_id {user_id} to send notification.")

            # Mark the task as done
            queue.task_done()

        except asyncio.CancelledError:
            bot_logger.info("Notification worker received cancellation request.")
            break
        except Exception as e:
            log_error(e, {"operation": "notification_worker_loop"})
            # Sleep briefly to prevent fast-looping on persistent errors
            await asyncio.sleep(5)


async def main():
    # Logging setup
    setup_logging(log_level="INFO", log_file="logs/bot.log")
    bot_logger.info("Starting ASSTRO bot...")

    # Print high-signal warnings if critical secrets are missing
    try:
        security_sanity_warnings()
    except Exception:
        pass

    # Fail fast when critical config is missing (better than running insecure/broken)
    if not BOT_TOKEN:
        bot_logger.critical("BOT_TOKEN is missing. Set it in .env then restart.")
        return
    if not DATABASE_URL:
        bot_logger.critical("DATABASE_URL is missing. Set it in .env then restart.")
        return

    try:
        await init_db()
        bot_logger.info("Database initialized successfully")
        # Legacy star-tier seeding retired (2026-06-02): the old credit/plan tier ladder is
        # replaced by the Star Season coupon system. Existing tiers are deactivated; nothing
        # re-seeds them. See REWARDS_HANDOFF.md / final-reward-system-map §8.5.
        print("→ Database ready (detail: logs/bot.log)", flush=True)
    except Exception as e:
        log_error(e, {"operation": "database_init"})
        bot_logger.critical("Failed to initialize database. Exiting.")
        return

    # Initialize Redis cache
    try:
        redis_connected = await init_redis()
        if redis_connected:
            bot_logger.info("Redis cache initialized successfully")
        else:
            bot_logger.warning("Redis cache not available, continuing without caching")
    except Exception as e:
        log_error(e, {"operation": "redis_init"})
        bot_logger.warning("Failed to initialize Redis cache, continuing without caching")

    # aiogram 3.7+ silently swallows the old `default_parse_mode` kwarg — the
    # user bot ran with NO default parse mode (raw <b> tags in any message
    # that didn't pass parse_mode explicitly). Same fix as admin_main.py.
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML),
              session=bot_session())
    try:
        await bot.set_my_commands([
            BotCommand(command="start", description="شروع"),
            BotCommand(command="support", description="پشتیبانی"),
        ])
    except Exception:
        pass
    
    fsm_storage = await _create_fsm_storage()
    dp = Dispatcher(storage=fsm_storage)

    # Best-effort: warm language cache so keyboards are localized from first render
    try:
        from app.utils.bot_i18n import set_cached_lang
        async with AsyncSessionLocal() as _s:
            from sqlalchemy import select

            from app.database.models import User as _User
            res = await _s.execute(select(_User.chat_id, _User.language))
            for cid, lng in res.all():
                set_cached_lang(int(cid), str(lng or "fa"))
    except Exception:
        pass

    # Initialize middleware
    dp.update.outer_middleware.register(DbSessionMiddleware(session_pool=AsyncSessionLocal))
    dp.update.outer_middleware.register(ErrorHandlingMiddleware())
    dp.update.outer_middleware.register(RateLimitMiddleware())
    dp.update.outer_middleware.register(ValidationMiddleware())
    dp.update.outer_middleware.register(PerformanceMiddleware())
    dp.update.outer_middleware.register(BannedUserMiddleware())
    dp.update.outer_middleware.register(WebappLockMiddleware())
    dp.update.outer_middleware.register(DispatcherMiddleware(dp))

    # Pass the notification queue to the handlers via middleware
    dp["notification_queue"] = notification_queue


    # User bot only — admin approvals and admin Telegram UI run in admin_main (separate token).
    routers = [
        sms_receipts.router,  # bank-SMS channel ingest (scoped to SMS_SOURCE_CHAT_ID; inert if unset)
        start.router,
        flow_inline.router,
        purchase.router,
        referral.router,
        rewards_router,
        my_services.router,
        tutorials.router,
        charge.router,
        add_subscription.router,
        common.router,
        support.router,
        challenges_router.router,
        game_router.router,
        star_levels_router.router,
    ]

    # Use a set to ensure unique routers and avoid duplicates
    unique_routers = list({id(router): router for router in routers}.values())

    included_count = 0
    for router in unique_routers:
        try:
            dp.include_router(router)
            included_count += 1
        except Exception as e:
            if "already attached" not in str(e):
                bot_logger.warning(f"Failed to include router: {e}")

    bot_logger.info(f"Loaded {included_count} routers")
    print(f"→ Loaded {included_count} handlers — full logs: logs/bot.log", flush=True)

    # --- One-time backfill: persist share-link tokens for existing subscriptions ---
    async def backfill_share_link_tokens():
        from sqlalchemy import select

        from app.database.models import Subscription
        from app.utils.logger import bot_logger as _logger
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(Subscription).filter(Subscription.sub_token == None)  # noqa: E711
                )
                subs = result.scalars().all()
                if not subs:
                    _logger.info("[BACKFILL] No subscriptions missing sub_token")
                    return
                updated = 0
                import re
                token_re = re.compile(r"/sub/([^/]+)/?")
                for sub in subs:
                    try:
                        info = await pasarguard_api.get_user_info(sub.marzban_username)
                        if not info:
                            continue
                        sub_url = info.get("subscription_url")
                        if not sub_url:
                            continue
                        m = token_re.search(sub_url)
                        if m:
                            sub.sub_token = m.group(1)
                            updated += 1
                    except Exception:
                        continue
                if updated:
                    await session.commit()
                _logger.info("[BACKFILL] sub_token update", total=len(subs), updated=updated)
        except Exception as e:
            from app.utils.logger import log_error
            log_error(e, {"operation": "backfill_share_link_tokens"})

    # Scheduler for background jobs
    scheduler = AsyncIOScheduler(timezone="UTC")
    
    # Define jobs with error handling
    # Background jobs (keep only those truly necessary).
    # Challenge-related jobs are removed because challenge progress & creation
    # are now handled **event-driven** inside CRUD functions/handlers, which
    # also fire instant notifications.  This keeps the scheduler lightweight
    # and avoids duplicate/early completions that suppress user alerts.

    jobs = [
        (check_low_data_job, 'check_low_data_job'),
        (renewal_job, 'renewal_job'),
        (update_user_analytics_job, 'update_user_analytics_job'),
        (expire_star_reward_claims_job, 'expire_claims_job'),
        # reminder_unclaimed_star_rewards_job removed 2026-07-19: legacy star
        # tiers are retired — no more 12h DMs about unclaimable rewards.
        (cleanup_draft_orders_job, 'cleanup_draft_orders_job'),
        (season_reset_job, 'season_reset_job'),
        (arcade_monthly_prizes_job, 'arcade_monthly_prizes_job'),
        (arcade_round_sweep_job, 'arcade_round_sweep_job'),
        (sms_sweep_job, 'sms_sweep_job'),
        (node_watch_job, 'node_watch_job'),
    ]
    
    # Add jobs with error handling
    for job_func, job_name in jobs:
        try:
            schedule_config = JOB_SCHEDULES[job_name]
            job_type = schedule_config['type']
            # The admin panel saves an `enabled` flag (and older saves may carry
            # a legacy `interval_minutes` key) alongside the APScheduler kwargs;
            # passing those to add_job() would TypeError and drop the job.
            if schedule_config.get('enabled') is False:
                bot_logger.info(f"Job '{job_name}' is disabled via schedule config; skipping")
                continue
            job_args = {k: v for k, v in schedule_config.items() if k not in ('type', 'enabled', 'interval_minutes')}
            
            # Wrap job with error handling
            async def wrapped_job(bot, original_job=job_func, name=job_name):
                import time

                from app.services.job_status import record_job_run
                start_time = time.time()
                try:
                    await original_job(bot)
                    duration = time.time() - start_time
                    log_job_execution(name, True, duration)
                    record_job_run(name, True, duration)
                except asyncio.CancelledError:
                    bot_logger.info(f"Job '{name}' was cancelled gracefully during shutdown.")
                    # No need to log job execution as failure, it's an expected cancellation
                except Exception as e:
                    duration = time.time() - start_time
                    log_error(e, {"job_name": name, "duration": duration})
                    log_job_execution(name, False, duration)
                    record_job_run(name, False, duration)
            
            scheduler.add_job(wrapped_job, job_type, **job_args, args=[bot])
            
        except Exception as e:
            log_error(e, {"operation": "scheduler_setup", "job_name": job_name})
            bot_logger.error(f"Failed to add job {job_name}: {e}")
    
    scheduler.start()
    bot_logger.info("Scheduler started successfully")

    # Perform backfill in the background without blocking startup
    asyncio.create_task(backfill_share_link_tokens())

    # One-time PasarGuard template audit: logs which plan shapes are
    # template-backed (creation then uses /api/user/from_template for those).
    # Failure is non-fatal — creation falls back to the manual path.
    async def _audit_panel_templates():
        try:
            await pasarguard_api.audit_templates()
        except Exception as e:
            log_error(e, {"operation": "startup_template_audit"})

    asyncio.create_task(_audit_panel_templates())

    # Boot the image-render pool now, not on a customer's first tap — see
    # render_manager.warm_up (7.2s cold vs 0.35s warm).
    async def _warm_render_pool():
        try:
            from app.utils.render_manager import warm_up
            await warm_up()
            bot_logger.info("Render pool warmed")
        except Exception as e:
            log_error(e, {"operation": "startup_render_warmup"})

    asyncio.create_task(_warm_render_pool())

    # Start the dedicated notification worker
    notification_task = asyncio.create_task(notification_worker(notification_queue, bot))
    
    # Register shutdown handlers
    
    # Graceful shutdown handler
    async def shutdown_handler():
        global http_runner, _fsm_redis
        bot_logger.info("Shutting down bot gracefully...")
        try:
            # 1. Shutdown the scheduler first to stop new jobs and wait for running ones
            try:
                scheduler.shutdown()
            except Exception as se:
                # Ignore if scheduler already stopped
                bot_logger.info(f"Scheduler shutdown skipped or already stopped: {se}")

            # 2. Stop other background tasks
            notification_task.cancel()
            await notification_task

            # 3. Stop embedded aiohttp app (runs on_cleanup; skips global dispose when embedded)
            if http_runner is not None:
                try:
                    await http_runner.cleanup()
                except Exception as e:
                    bot_logger.info(f"HTTP runner cleanup: {e}")
                http_runner = None
            
            # 4. Close external connections
            await pasarguard_api.close()
            if _fsm_redis is not None:
                try:
                    await _fsm_redis.aclose()
                except Exception:
                    try:
                        close_fn = getattr(_fsm_redis, "close", None)
                        if callable(close_fn):
                            maybe = close_fn()
                            if asyncio.iscoroutine(maybe):
                                await maybe
                    except Exception:
                        pass
                _fsm_redis = None
            await close_redis()
            try:
                from app.utils.admin_bot_helper import close_admin_bot, close_user_bot

                await close_admin_bot()
                await close_user_bot()
            except Exception:
                pass

            # 5. Dispose DB engine last
            try:
                await engine.dispose()
            except Exception as de:
                bot_logger.info(f"DB engine dispose skipped or failed: {de}")
            
            bot_logger.info("Shutdown completed successfully")
        except Exception as e:
            log_error(e, {"operation": "shutdown"})
    
    dp.shutdown.register(shutdown_handler)

    try:
        global http_runner
        await bot.delete_webhook(drop_pending_updates=True)
        bot_logger.info("Webhook deleted, starting polling...")
        print("→ Polling Telegram — leave this terminal open. Ctrl+C to stop.", flush=True)
        # Start the embedded web server (for WebApp arcade)
        try:
            http_runner = await start_webserver(asyncio.get_event_loop(), bot=bot, scheduler=scheduler)
            bot_logger.info("Embedded web server started")
        except Exception as we:
            bot_logger.warning(f"Web server failed to start: {we}")
            http_runner = None
        await dp.start_polling(bot)
    except Exception as e:
        log_error(e, {"operation": "bot_startup"})
        bot_logger.critical("Failed to start bot polling. Exiting.")
        return

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        bot_logger.info("Bot stopped by user.")
    except Exception as e:
        log_error(e, {"operation": "main_execution"})
        bot_logger.critical("Bot crashed with unhandled exception.") 