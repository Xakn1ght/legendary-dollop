import re
import time

from aiogram import F
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import BufferedInputFile, CallbackQuery, InputMediaAnimation
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Subscription
from app.services.marzban import marzban_api
from app.utils.bot_i18n import get_cached_lang, t
from app.utils.render_manager import render_subscription_gif_async

from ..constants import STATUS_MAP_NO_EMOJI
from ..subscription_details import build_subscription_detail
from ..utils import convert_to_gb
from .common import _last_gif_refresh, _last_text_refresh, router


@router.callback_query(F.data.startswith("refresh_"))
async def refresh_subscription(callback: CallbackQuery, session: AsyncSession):
    """Manual refresh of subscription details (instant read) - updates text first, then GIF."""
    lang = get_cached_lang(callback.from_user.id)
    sub_id = int(callback.data.split("_")[1])
    sub = await session.get(Subscription, sub_id)
    if not sub:
        await callback.answer(t(lang, "service_not_found"), show_alert=True)
        return

    # Text-only cooldown (30s per user/sub)
    key = (callback.from_user.id, sub_id)
    now = time.time()
    last_ts = _last_text_refresh.get(key)
    if last_ts and now - last_ts < 30:
        remaining = int(30 - (now - last_ts))
        if remaining < 1:
            remaining = 1
        await callback.answer(t(lang, "wait_seconds").format(sec=remaining), show_alert=True)
        return
    _last_text_refresh[key] = now

    user_info = await marzban_api.get_fast_user_info(sub.marzban_username, getattr(sub, 'sub_token', None))
    if not user_info:
        await callback.answer(t(lang, "error_fetch_service"), show_alert=True)
        return

    # Answer callback immediately
    await callback.answer(t(lang, "updating"))

    # Ensure we persist a stable token for the subscription link and avoid duplicates in text
    try:
        if not getattr(sub, 'sub_token', None):
            sub_url_candidate = user_info.get('subscription_url') if isinstance(user_info, dict) else None
            if not sub_url_candidate:
                from app.services.marzban import marzban_api as _api
                sub_url_candidate = await _api.get_subscription_url(sub.marzban_username)
            if sub_url_candidate:
                m = re.search(r"/sub/([^/]+)/?", sub_url_candidate)
                if m:
                    sub.sub_token = m.group(1)
                    await session.commit()
    except Exception:
        pass

    # Build latest text and keyboard (single canonical link rendered inside)
    text, kb, _ = build_subscription_detail(sub, user_info, generate_image=False)
    try:
        await callback.message.edit_caption(
            caption=text, parse_mode="HTML", reply_markup=kb.as_markup()
        )
    except (TelegramBadRequest, AttributeError):
        # If no media, edit text instead
        try:
            await callback.message.edit_text(
                text, parse_mode="HTML", reply_markup=kb.as_markup()
            )
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e):
                pass

    # Update caption immediately
    try:
        await callback.message.edit_caption(caption=text, parse_mode="HTML", reply_markup=kb.as_markup())
    except Exception:
        try:
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb.as_markup())
        except Exception:
            pass

    # If GIF cooldown (1h) has passed, silently regenerate in background
    try:
        key_gif = (callback.from_user.id, sub_id)
        now2 = time.time()
        last_gif = _last_gif_refresh.get(key_gif)
        if not last_gif or now2 - last_gif >= 3600:
            _last_gif_refresh[key_gif] = now2
            expire_ts = int(user_info.get('expire') or 0)
            if expire_ts > 0:
                import time as _t
                secs_left = max(0, expire_ts - int(_t.time()))
                days_num = secs_left // (60 * 60 * 24)
            else:
                days_num = "نامحدود"
            gif_bytes = await render_subscription_gif_async(
                used_gb=convert_to_gb(user_info.get('used_traffic', 0)),
                limit_gb=convert_to_gb(user_info.get('data_limit', 0)),
                days_remaining=days_num,
                carry_gb=convert_to_gb(getattr(sub, 'carry_over_bytes', 0) or 0),
                status_str=STATUS_MAP_NO_EMOJI.get(user_info.get('status', 'unknown'), 'نامشخص'),
                username=sub.marzban_username,
            )
            media = InputMediaAnimation(
                media=BufferedInputFile(file=gif_bytes, filename="chart.gif"),
                caption=text,
                parse_mode="HTML"
            )
            await callback.message.edit_media(media=media, reply_markup=kb.as_markup())
    except Exception:
        pass


@router.callback_query(F.data.startswith("svc_"))
async def subscription_detail(callback: CallbackQuery, session: AsyncSession):
    """Show details for a single subscription and management buttons."""
    lang = get_cached_lang(callback.from_user.id)
    sub_id = int(callback.data.split("_")[1])

    # Load subscription
    sub: Subscription | None = await session.get(Subscription, sub_id)
    if not sub:
        await callback.answer(t(lang, "service_not_found"), show_alert=True)
        return

    # Prefer fast read via share-link token when available; for pending, synthesize minimal info
    if str(sub.status) == 'pending':
        user_info = {
            'status': 'pending',
            'used_traffic': 0,
            'data_limit': 0,
            'expire': 0,
        }
    else:
        user_info = await marzban_api.get_fast_user_info(sub.marzban_username, getattr(sub, 'sub_token', None))
    if not user_info:
        await callback.answer(t(lang, "error_fetch_service"), show_alert=True)
        return

    # Answer callback immediately to prevent timeout
    await callback.answer()

    text, kb, _ = build_subscription_detail(sub, user_info, generate_image=False)
    try:
        await callback.message.edit_caption(caption=text, parse_mode="HTML", reply_markup=kb.as_markup())
    except Exception:
        try:
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb.as_markup())
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e):
                pass
    # Auto-regenerate GIF in background on open if 1h cooldown passed (no button press needed)
    try:
        key_gif = (callback.from_user.id, sub_id)
        now2 = time.time()
        last_gif = _last_gif_refresh.get(key_gif)
        if not last_gif or now2 - last_gif >= 3600:
            _last_gif_refresh[key_gif] = now2
            expire_ts = int(user_info.get('expire') or 0)
            if expire_ts > 0:
                import time as _t
                secs_left = max(0, expire_ts - int(_t.time()))
                days_num = secs_left // (60 * 60 * 24)
            else:
                days_num = "نامحدود"
            gif_bytes = await render_subscription_gif_async(
                used_gb=convert_to_gb(user_info.get('used_traffic', 0)),
                limit_gb=convert_to_gb(user_info.get('data_limit', 0)),
                days_remaining=days_num,
                carry_gb=convert_to_gb(getattr(sub, 'carry_over_bytes', 0) or 0),
                status_str=STATUS_MAP_NO_EMOJI.get(user_info.get('status', 'unknown'), 'نامشخص'),
                username=sub.marzban_username,
            )
            media = InputMediaAnimation(
                media=BufferedInputFile(file=gif_bytes, filename="chart.gif"),
                caption=text,
                parse_mode="HTML"
            )
            await callback.message.edit_media(media=media, reply_markup=kb.as_markup())
    except Exception:
        pass


@router.callback_query(F.data.startswith("pending_"))
async def pending_subscription_detail(callback: CallbackQuery, session: AsyncSession):
    """Inform user that the service is awaiting admin confirmation and show read-only card."""
    lang = get_cached_lang(callback.from_user.id)
    try:
        sub_id = int(callback.data.split("_")[1])
    except Exception:
        await callback.answer(t(lang, "invalid_request"), show_alert=True)
        return

    sub: Subscription | None = await session.get(Subscription, sub_id)
    if not sub:
        await callback.answer(t(lang, "service_not_found"), show_alert=True)
        return

    # Only show alert. Do not render any menu/buttons for pending items.
    await callback.answer(t(lang, "waiting_admin"), show_alert=True)
    return
