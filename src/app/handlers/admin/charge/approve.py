import logging
from datetime import datetime

from aiogram import Bot, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import crud, notifications_crud
from app.database.models import User as _User
from app.handlers.admin.common import _send_pending_requests
from app.services.marzban import marzban_api
from app.utils.admin_bot_helper import get_user_bot
from app.utils.bot_i18n import t

from .common import GB, _admin_lang, router


@router.callback_query(F.data.startswith("approve_charge_"))
async def approve_charge(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    lang = await _admin_lang(session, callback.from_user)
    charge_id = int(callback.data.split("_")[2])
    charge_req = await crud.get_charge_request(session, charge_id)
    if not charge_req or charge_req.status != "pending":
        await callback.answer(t(lang, "admin_charge_not_found_or_handled"), show_alert=True)
        return

    await session.refresh(charge_req, attribute_names=["subscription", "user"])

    sub = charge_req.subscription
    user = charge_req.user

    cfg = await crud.get_reward_config(session)

    if not sub or not sub.marzban_username:
        await callback.answer(t(lang, "admin_charge_sub_invalid"), show_alert=True)
        return
    if not user:
        await callback.answer(t(lang, "admin_charge_user_missing"), show_alert=True)
        return

    if sub.status != "active":
        await callback.answer(t(lang, "admin_charge_sub_inactive"), show_alert=True)
        return

    user_bot = get_user_bot()
    if not user_bot:
        await callback.answer("User bot unavailable (BOT_TOKEN).", show_alert=True)
        return

    user_info = await marzban_api.get_user_info(sub.marzban_username)
    if not user_info:
        await callback.answer(t(lang, "admin_charge_fetch_marzban_failed"), show_alert=True)
        return

    now_ts = datetime.utcnow().timestamp()
    expire_ts = user_info.get("expire", 0) or 0

    data_limit_current = user_info.get("data_limit", 0) or 0
    used_traffic = user_info.get("used_traffic", 0) or 0
    remaining_bytes_current = max(data_limit_current - used_traffic, 0)

    expired = bool(expire_ts and expire_ts < now_ts)
    traffic_exhausted = remaining_bytes_current == 0
    subscription_ended = expired or traffic_exhausted

    data_limit_after = data_limit_current
    reset_usage = False

    new_expire_ts = expire_ts or 0

    add_days_only = bool(charge_req.extra_days) and not (charge_req.traffic_bytes and charge_req.traffic_bytes > 0)
    is_5gb_limit_charge = False

    if add_days_only:
        carry_bytes = 0
        lost_bytes = 0
        reset_at = None
        base = now_ts if expired else (expire_ts or now_ts)
        new_expire_ts = int(base + charge_req.extra_days * 24 * 3600)
    elif subscription_ended:
        carry_bytes = 0
        lost_bytes = 0
        reset_at = None
        if charge_req.traffic_bytes and charge_req.traffic_bytes > 0:
            data_limit_after = charge_req.traffic_bytes
            reset_usage = True
        if charge_req.extra_days:
            base = now_ts if expired else (expire_ts or now_ts)
            new_expire_ts = int(base + charge_req.extra_days * 24 * 3600)
    else:
        is_5gb_limit_charge = getattr(charge_req, "charge_type", "normal") == "normal_5gb_limit"

        remaining = remaining_bytes_current

        if is_5gb_limit_charge:
            carry_bytes = min(remaining, 5 * GB)
            lost_bytes = max(0, remaining - 5 * GB)
            data_limit_after = carry_bytes + (charge_req.traffic_bytes or 0)
            reset_usage = True
            if charge_req.extra_days:
                new_expire_ts = int(now_ts + charge_req.extra_days * 24 * 3600)
            reset_at = None

        elif remaining <= 5 * GB:
            carry_bytes = remaining if (charge_req.traffic_bytes and charge_req.traffic_bytes > 0) else 0
            lost_bytes = 0
            data_limit_after = carry_bytes + (charge_req.traffic_bytes or 0)
            reset_usage = True
            if charge_req.extra_days:
                new_expire_ts = int((expire_ts or now_ts) + charge_req.extra_days * 24 * 3600)
            reset_at = None
        else:
            carry_bytes = min(remaining, 5 * GB) if (charge_req.traffic_bytes and charge_req.traffic_bytes > 0) else 0
            lost_bytes = max(0, remaining - 5 * GB)
            data_limit_after = carry_bytes + (charge_req.traffic_bytes or 0)
            reset_usage = True
            if charge_req.extra_days:
                new_expire_ts = int((expire_ts or now_ts) + charge_req.extra_days * 24 * 3600)
            reset_at = None

    if reset_usage:
        ok = await marzban_api.reset_user_traffic_bytes(
            sub.marzban_username,
            new_data_limit_bytes=data_limit_after,
            new_expire_ts=new_expire_ts,
        )
        if not ok:
            await callback.answer(t(lang, "admin_charge_marzban_reset_failed"), show_alert=True)
            return
    else:
        session_http = await marzban_api._get_session()
        headers = await marzban_api._get_headers()
        url = f"{marzban_api.base_url}/api/user/{sub.marzban_username}"
        patch_body = {
            "data_limit": data_limit_after,
            "expire": new_expire_ts,
            "status": "active",
            "data_limit_reset_strategy": "no_reset",
        }
        async with session_http.put(url, headers=headers, json=patch_body) as resp:
            if resp.status not in (200, 204):
                await callback.answer(t(lang, "admin_charge_marzban_update_failed"), show_alert=True)
                return

    await crud.set_subscription_carry_over(session, sub.id, carry_bytes, reset_at)
    await crud.update_charge_request_status(session, charge_id, "approved")

    if sub.referrer_id:
        result_ref = await session.execute(select(_User).filter(_User.id == sub.referrer_id))
        ref_user = result_ref.scalars().first()

        if ref_user:
            traffic_reward_bytes = None
            extra_days_reward = None
            credit_reward_amount = None

            if charge_req.traffic_bytes and charge_req.traffic_bytes > 0 and cfg.traffic_percent:
                traffic_reward_bytes = int(charge_req.traffic_bytes * cfg.traffic_percent / 100)

            if charge_req.extra_days and charge_req.extra_days > 0 and cfg.days_percent is not None:
                extra_days_calc = int(charge_req.extra_days * cfg.days_percent / 100)
                extra_days_reward = max(1, extra_days_calc) if extra_days_calc else None
            elif charge_req.traffic_bytes and charge_req.traffic_bytes > 0 and cfg.days_percent is not None:
                default_days = 30
                extra_days_calc = int(default_days * cfg.days_percent / 100)
                extra_days_reward = max(1, extra_days_calc) if extra_days_calc else None

            if cfg.credit_percent and cfg.credit_percent > 0:
                credit_reward_amount = int(charge_req.price * cfg.credit_percent / 100)

            if traffic_reward_bytes or extra_days_reward or credit_reward_amount:
                traffic_bytes = int(charge_req.traffic_bytes or 0)
                star_increment = max(0, traffic_bytes // (20 * GB))
                reward = await crud.create_referral_reward(
                    db=session,
                    subscription_id=sub.id,
                    referrer_id=sub.referrer_id,
                    traffic_bytes=traffic_reward_bytes,
                    extra_days=extra_days_reward,
                    credit_amount=credit_reward_amount,
                    reward_value=star_increment,
                )

                stars_progress = ref_user.stars

                from app.keyboards.inline import get_enhanced_reward_voucher_keyboard

                kb_reward = get_enhanced_reward_voucher_keyboard(
                    reward.id,
                    extra_gb=(traffic_reward_bytes or 0) / GB if traffic_reward_bytes else None,
                    extra_days=extra_days_reward,
                    credit_amount=credit_reward_amount,
                    stars_progress=stars_progress,
                    star_increment=star_increment,
                    show_star=star_increment > 0,
                    show_enhanced_stars=False,
                )

                desc_parts = []
                if charge_req.traffic_bytes:
                    desc_parts.append(f"+{(charge_req.traffic_bytes / GB):.0f}GB")
                if charge_req.extra_days:
                    desc_parts.append(f"+{charge_req.extra_days}D")
                purchase_desc = " & ".join(desc_parts) or "شارژ"

                try:
                    await user_bot.send_message(
                        ref_user.chat_id,
                        (
                            "🎉 کاربر جدیدی که با کد شما عضو شده بود سرویس خود را شارژ کرد!\n"
                            f"مقدار شارژ: {purchase_desc}\n"
                            "🎁 پاداش آماده است – یکی را انتخاب کنید:"
                        ),
                        reply_markup=kb_reward,
                    )
                except Exception as e:
                    logging.error(f"Could not notify referrer {sub.referrer_id} about charge reward: {e}")

    msg_lines = [
        "✅ شارژ سرویس شما تایید شد و اعمال گردید.",
    ]
    added_gb = charge_req.traffic_bytes / GB
    if added_gb:
        msg_lines.append(f"🔸 حجم افزوده‌شده: {added_gb:.0f} GB")
    if charge_req.extra_days:
        msg_lines.append(f"🔸 روزهای افزوده‌شده: {charge_req.extra_days} روز")
    if carry_bytes:
        msg_lines.append(f"🔹 ترافیک منتقل‌شده از دوره قبل: {carry_bytes / GB:.1f} GB")
    if lost_bytes and lost_bytes > 0:
        if is_5gb_limit_charge:
            msg_lines.append(f"⚠️ بر اساس انتخاب شما، {lost_bytes / GB:.1f} GB بیش از حد 5GB حذف شد.")
        else:
            msg_lines.append(f"⚠️ {lost_bytes / GB:.1f} GB به حد مجاز انتقال کاهش یافت.")

    kb = InlineKeyboardBuilder()
    kb.button(text="🔍 مدیریت اشتراک", callback_data=f"svc_{sub.id}")
    kb.adjust(1)

    await user_bot.send_message(user.chat_id, "\n".join(msg_lines), reply_markup=kb.as_markup())

    try:
        title = "Charge approved"
        message = (
            f"✅ Charge approved for {sub.marzban_username}.\n"
            f"Added: {added_gb:.0f}GB"
            + (f", +{charge_req.extra_days} days" if charge_req.extra_days else "")
            + (f", carried: {(carry_bytes / GB):.1f}GB" if carry_bytes else "")
        )
        await notifications_crud.create_notification(
            session,
            user_id=user.id,
            type="charge_approved",
            title=title,
            message=message,
            sent_to_webapp=True,
            sent_to_bot=False,
        )
    except Exception:
        pass

    await callback.answer(t(lang, "admin_charge_approved"))
    try:
        await callback.message.delete()
    except Exception:
        pass
    await _send_pending_requests(bot, session, callback.from_user.id, None)

    try:
        from app.api.routes.admin_ws import broadcast_admin_event

        await broadcast_admin_event("receipts_updated", {"charge_id": charge_id})
    except Exception as e:
        logging.warning(f"Failed to broadcast charge approval to admin panel: {e}")
