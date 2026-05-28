import logging
from datetime import datetime, timedelta

from aiogram import Bot

from app.core.redis_config import cache
from app.core.settings import RENEWAL_TRAFFIC_SKIP_PERCENT, SUPPORT_TICKET_AUTOCLOSE_DAYS, SUPPORT_TICKET_REMINDER_HOURS
from app.database import crud
from app.database.models import AsyncSessionLocal
from app.keyboards.inline import get_low_resource_keyboard, get_low_traffic_keyboard, get_renewal_keyboard
from app.services.marzban import marzban_api

EXPIRY_NOTIFY_THRESHOLD = timedelta(days=3)

async def check_low_data_job(bot: Bot):
    logging.debug("Running low data/time check job...")
    async with AsyncSessionLocal() as session:
        subscriptions = await crud.get_all_active_subscriptions_for_notification(session)
        
        for sub in subscriptions:
            try:
                user_info = await marzban_api.get_fast_user_info(sub.marzban_username, getattr(sub, 'sub_token', None))
                if not user_info:
                    continue
                # Some share-link responses may omit expire; fallback to admin API for completeness
                if not user_info.get('expire'):
                    admin_info = await marzban_api.get_user_info(sub.marzban_username)
                    if admin_info:
                        user_info['expire'] = admin_info.get('expire', user_info.get('expire'))

                # Normalize possible None values from API/share-link
                data_limit = user_info.get('data_limit') or 0
                used_traffic = user_info.get('used_traffic') or 0
                expire_ts = user_info.get('expire') or 0
                now = datetime.utcnow()
                
                # --- Low traffic and finished data notifications (once per day) ---
                if data_limit > 0:
                    remaining_bytes = max(data_limit - used_traffic, 0)
                    remaining_percent = (remaining_bytes / data_limit * 100) if data_limit > 0 else 0

                    # Skip low data warnings for users with auto-renewal - they'll be renewed automatically
                    if sub.renewal_paid and remaining_percent <= RENEWAL_TRAFFIC_SKIP_PERCENT:
                        logging.debug(f"[NOTIFY] Skip low-data warning (auto-renew active): {sub.marzban_username}")
                        continue

                    # Finished data branch
                    if remaining_bytes == 0:
                        if sub.renewal_paid:
                            # Inform user that auto-renew is active; no renew button to avoid confusion
                            today_key = f"notif:finished_auto:{sub.id}:{datetime.utcnow().date().isoformat()}"
                            if not await cache.get(today_key):
                                user = sub.user
                                message_text = (
                                    "❗️حجم اشتراک شما تمام شد!\n\n"
                                    f"برای سرویس با نام کاربری <code>{sub.marzban_username}</code> تمدید خودکار فعال است و به‌زودی انجام می‌گردد."
                                )
                                logging.debug(f"[NOTIFY] Sent finished+auto-renew: {sub.marzban_username}")
                                await bot.send_message(chat_id=user.chat_id, text=message_text, parse_mode="HTML")
                                # Set daily throttle to next midnight UTC
                                now_dt = datetime.utcnow()
                                next_midnight = (now_dt + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                                ttl_seconds = int((next_midnight - now_dt).total_seconds())
                                try:
                                    await cache.set(today_key, 1, ttl=ttl_seconds)
                                except Exception:
                                    pass
                        else:
                            # No booking; suggest renewal explicitly with button
                            today_key = f"notif:finished:{sub.id}:{datetime.utcnow().date().isoformat()}"
                            if not await cache.get(today_key):
                                user = sub.user
                                # Skip if user doesn't exist (orphaned subscription)
                                if not user:
                                    logging.warning(f"[NOTIFY] Skipping finished traffic for subscription {sub.id} - no user found")
                                    continue
                                
                                message_text = (
                                    "❗️حجم اشتراک شما تمام شد!\n\n"
                                    f"اشتراک با نام کاربری <code>{sub.marzban_username}</code> به اتمام رسیده است.\n\n"
                                    "برای تمدید و جلوگیری از حذف اشتراک از دکمه زیر استفاده کنید:"
                                )
                                logging.debug(f"[NOTIFY] Sent finished-traffic: {sub.marzban_username}")
                                await bot.send_message(
                                    chat_id=user.chat_id,
                                    text=message_text,
                                    reply_markup=get_renewal_keyboard(sub.marzban_username),
                                    parse_mode="HTML"
                                )
                                # Set daily throttle to next midnight UTC
                                now_dt = datetime.utcnow()
                                next_midnight = (now_dt + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                                ttl_seconds = int((next_midnight - now_dt).total_seconds())
                                try:
                                    await cache.set(today_key, 1, ttl=ttl_seconds)
                                except Exception:
                                    pass
                    # Low traffic notice for <= threshold percent
                    # Previously suppressed when renewal_paid=True; now we notify in both cases
                    elif remaining_percent <= RENEWAL_TRAFFIC_SKIP_PERCENT:
                        # Daily throttling key
                        today_key = f"notif:low_traffic:{sub.id}:{datetime.utcnow().date().isoformat()}"
                        if await cache.get(today_key):
                            # Already notified today
                            continue
                        user = sub.user
                        # Skip if user doesn't exist (orphaned subscription)
                        if not user:
                            logging.warning(f"[NOTIFY] Skipping low traffic for subscription {sub.id} - no user found")
                            continue
                        
                        remaining_gb = round(remaining_bytes / (1024**3), 2)
                        if sub.renewal_paid:
                            # Booking exists: inform but clarify auto‑renew behavior
                            message_text = (
                                "⚠️ هشدار حجم کم!\n\n"
                                f"حجم اشتراک <code>{sub.marzban_username}</code> رو به اتمام است (کمتر از {int(RENEWAL_TRAFFIC_SKIP_PERCENT)}٪).\n"
                                f"باقی‌مانده: {remaining_gb} گیگابایت (~{remaining_percent:.1f}٪).\n\n"
                                "تمدید خودکار فعال است و در زمان پایان سرویس اعمال می‌شود. در صورت نیاز می‌توانید همین حالا شارژ کنید."
                            )
                        else:
                            message_text = (
                                "⚠️ هشدار حجم کم!\n\n"
                                f"حجم اشتراک با نام کاربری <code>{sub.marzban_username}</code> رو به اتمام است (کمتر از {int(RENEWAL_TRAFFIC_SKIP_PERCENT)}٪).\n"
                                f"حجم باقی‌مانده: {remaining_gb} گیگابایت (~{remaining_percent:.1f}٪)\n\n"
                                "برای شارژ یا تمدید، از دکمه زیر استفاده کنید."
                            )
                        logging.debug(f"[NOTIFY] Sent low-traffic alert: {sub.marzban_username} ({remaining_gb:.1f}GB left)")
                        await bot.send_message(
                            chat_id=user.chat_id,
                            text=message_text,
                            reply_markup=get_low_traffic_keyboard(sub.marzban_username),
                            parse_mode="HTML"
                        )
                        # Set daily throttle TTL to next midnight UTC
                        now_dt = datetime.utcnow()
                        next_midnight = (now_dt + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                        ttl_seconds = int((next_midnight - now_dt).total_seconds())
                        try:
                            await cache.set(today_key, 1, ttl=ttl_seconds)
                        except Exception:
                            pass
                        await crud.set_low_data_notified(session, sub.id, True)
                # --- Imminent expiry notification (once per day) ---
                if expire_ts:
                    expire_dt = datetime.utcfromtimestamp(expire_ts)
                    # Trigger when remaining time is < 3 days (strict), also align with UI floor() logic
                    total_seconds_left = (expire_dt - now).total_seconds()
                    days_left_int = int(total_seconds_left // 86400)
                    threshold_days = 3
                    if total_seconds_left > 0 and (total_seconds_left < threshold_days * 86400 or days_left_int <= threshold_days - 1):
                        # Daily throttling key
                        today_key = f"notif:imminent_expiry:{sub.id}:{datetime.utcnow().date().isoformat()}"
                        has_today = await cache.get(today_key)
                        if not getattr(sub, 'imminent_expiry_notified', False) or not has_today:
                            user = sub.user
                            # Skip if user doesn't exist (orphaned subscription)
                            if not user:
                                logging.warning(f"[NOTIFY] Skipping imminent expiry for subscription {sub.id} - no user found")
                                continue
                            
                            message_text = (
                                "⚠️ از زمان اشتراک با نام کاربری "
                                f"<code>{sub.marzban_username}</code> کمتر از ۳ روز باقی مانده است. برای تمدید دکمه زیر را فشار دهید.\n\n"
                                "✅ در صورت تمدید، بسته خریداری شده برای شما رزرو شده و به محض پایان سرویس فعلی به طور خودکار فعال می‌گردد."
                            )
                            logging.debug(f"[NOTIFY] Sent expiry alert: {sub.marzban_username} ({days_left_int}d left)")
                            await bot.send_message(
                                chat_id=user.chat_id,
                                text=message_text,
                                reply_markup=get_low_resource_keyboard(sub.marzban_username),
                                parse_mode="HTML"
                            )
                            await crud.set_imminent_expiry_notified(session, sub.id, True)
                            # Set daily throttle TTL to next midnight UTC
                            now_dt = datetime.utcnow()
                            next_midnight = (now_dt + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                            ttl_seconds = int((next_midnight - now_dt).total_seconds())
                            try:
                                await cache.set(today_key, 1, ttl=ttl_seconds)
                            except Exception:
                                pass
                    # Expired notification
                    if expire_dt <= now:
                        if not getattr(sub, 'expired_notified', False):
                            user = sub.user
                            # Skip if user doesn't exist (orphaned subscription)
                            if not user:
                                logging.warning(f"[NOTIFY] Skipping expired notification for subscription {sub.id} - no user found")
                                continue
                            
                            message_text = (
                                f"❗️اشتراک شما با نام کاربری <code>{sub.marzban_username}</code> منقضی شد!\n\n"
                                "برای تمدید و جلوگیری از حذف اشتراک از دکمه زیر استفاده کنید:"
                            )
                            logging.debug(f"[NOTIFY] Sent expired alert: {sub.marzban_username}")
                            await bot.send_message(
                                chat_id=user.chat_id,
                                text=message_text,
                                reply_markup=get_renewal_keyboard(sub.marzban_username),
                                parse_mode="HTML"
                            )
                            await crud.set_expired_notified(session, sub.id, True)
            except Exception as e:
                user_info = f"user {sub.user.chat_id}" if sub.user else "no user"
                # "Connector is closed" typically happens during restarts/shutdown or transient aiohttp issues.
                # Don't spam error logs for this known transient; warn instead.
                msg = str(e).lower()
                if "connector is closed" in msg or "session is closed" in msg:
                    logging.warning(f"Transient HTTP error processing subscription {sub.id} for {user_info}: {e}")
                else:
                    logging.error(f"Error processing subscription {sub.id} for {user_info}: {e}")

        # --- Reminders for tickets awaiting user reply (every ~5s tick, throttled by configured hours) ---
        try:
            from sqlalchemy import or_, select

            from app.database.models import Ticket
            cutoff = datetime.utcnow() - timedelta(hours=SUPPORT_TICKET_REMINDER_HOURS)
            result = await session.execute(
                select(Ticket).where(
                    Ticket.status == 'awaiting_user',
                    Ticket.last_message_at <= cutoff
                ).limit(50)
            )
            tickets = result.scalars().all()
            for t in tickets:
                try:
                    user = await crud.get_user_by_id(session, t.user_id)
                    if user:
                        await bot.send_message(user.chat_id, f"⏰ یادآوری: لطفاً برای تیکت #{t.id} پاسخ دهید.")
                        t.last_reminder_at = datetime.utcnow()
                except Exception:
                    pass
            if tickets:
                await session.commit()
        except Exception:
            pass

        # --- Auto-close tickets idle beyond configured days while awaiting user ---
        try:
            from sqlalchemy import select

            from app.database.models import Ticket
            auto_cutoff = datetime.utcnow() - timedelta(days=SUPPORT_TICKET_AUTOCLOSE_DAYS)
            result = await session.execute(
                select(Ticket).where(
                    Ticket.status == 'awaiting_user',
                    Ticket.last_message_at <= auto_cutoff
                ).limit(100)
            )
            stale = result.scalars().all()
            for t in stale:
                try:
                    await crud.update_ticket_status(session, t.id, 'closed')
                    user = await crud.get_user_by_id(session, t.user_id)
                    if user:
                        await bot.send_message(user.chat_id, f"🔒 تیکت #{t.id} به دلیل عدم پاسخ طی {SUPPORT_TICKET_AUTOCLOSE_DAYS} روز بسته شد. در صورت نیاز می‌توانید دوباره باز کنید.")
                except Exception:
                    pass
        except Exception:
            pass
