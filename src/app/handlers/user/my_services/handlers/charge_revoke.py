import base64
from datetime import datetime

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import crud
from app.database.models import Subscription
from app.handlers.user.charge import check_subscription_traffic
from app.services.pasarguard import pasarguard_api
from app.utils.bot_i18n import get_cached_lang, t

from ..utils import to_persian_digits

try:
    import jdatetime
except ImportError:
    jdatetime = None

from ..subscription_details import build_subscription_detail
from .common import router


@router.callback_query(F.data.startswith("charge_service_"))
async def start_inline_charge(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Start the charge flow from an inline button."""
    lang = get_cached_lang(callback.from_user.id)
    sub_id = int(callback.data.split("_")[2])

    # Get subscription details
    subscription = await session.get(Subscription, sub_id)
    if not subscription:
        await callback.answer(t(lang, "service_not_found"), show_alert=True)
        return

    # Set state and redirect to charge flow
    await state.update_data(subscription_id=subscription.id)

    # Send a message to redirect to charge flow
    await callback.message.answer(
        t(lang, "use_main_menu_charge"),
        parse_mode="HTML"
    )
    await callback.answer(t(lang, "use_main_menu_charge"))


@router.callback_query(F.data.startswith("charge_"))
async def handle_charge_button(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Handle charge button from subscription details - open the charge menu directly for this subscription."""
    lang = get_cached_lang(callback.from_user.id)
    token = callback.data.split("_", 1)[1]
    subscription: Subscription | None = None
    user = await crud.get_user(session, callback.from_user.id)
    # Prefer numeric id when provided; otherwise treat as panel username.
    # Either way the subscription must belong to the caller (the numeric path
    # previously skipped that check and leaked other users' traffic info).
    try:
        sub_id = int(token)
        subscription = await session.get(Subscription, sub_id)
        if subscription and (not user or subscription.user_id != user.id):
            subscription = None
    except ValueError:
        # Lookup by username for notifications keyboards like charge_{username}
        if user:
            subs = await crud.get_user_active_subscriptions(session, user.id)
            subscription = next((s for s in subs if s.marzban_username == token), None)
    if not subscription:
        await callback.answer(t(lang, "service_not_found"), show_alert=True)
        return

    # Set the subscription in state for the charge flow
    await state.update_data(subscription_id=subscription.id)

    # Open the charge menu directly for this subscription
    await check_subscription_traffic(callback.message, state, session, subscription)


@router.callback_query(F.data.startswith("revoke_"))
async def revoke_subscription(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    lang = get_cached_lang(callback.from_user.id)
    sub_id = int(callback.data.split("_")[1])
    sub = await session.get(Subscription, sub_id)
    if not sub:
        await callback.answer(t(lang, "service_not_found"), show_alert=True)
        return
    # Ownership is enforced by the shared flow — this button previously revoked ANY
    # subscription id, letting a non-owner rotate someone else's link.
    from app.services.flows.errors import FlowError
    from app.services.flows.subs import revoke_subscription as revoke_flow

    db_user = await crud.get_user(session, callback.from_user.id)
    if not db_user:
        await callback.answer(t(lang, "service_not_found"), show_alert=True)
        return
    try:
        try:
            revoke_result = await revoke_flow(session, db_user, sub_id)
            success = True
        except FlowError as e:
            if e.code in ("not_found", "unauthorized"):
                await callback.answer(t(lang, "service_not_found"), show_alert=True)
                return
            success = False
            revoke_result = None
        if success:
            user_info = revoke_result.user_info
            new_link = revoke_result.new_link
            plan = sub.plan_name or "-"
            status = user_info.get("status", "-") if user_info else "-"
            expire = user_info.get("expire", "-") if user_info else "-"
            # Format expire as Jalali date with Persian digits if possible
            jalali_warning = ""
            try:
                if expire and str(expire).isdigit() and int(expire) > 0 and jdatetime:
                    dt = datetime.fromtimestamp(int(expire))
                    jalali = jdatetime.date.fromgregorian(date=dt.date()).strftime('%Y/%m/%d')
                    expire_str = to_persian_digits(jalali)
                elif expire and str(expire).isdigit() and int(expire) > 0:
                    expire_str = to_persian_digits(datetime.fromtimestamp(int(expire)).strftime('%Y-%m-%d'))
                    jalali_warning = ""
                else:
                    expire_str = "نامحدود"
            except Exception:
                expire_str = str(expire)
                jalali_warning = "\n⚠️ خطا در تبدیل تاریخ به شمسی."
            # (new sub_token already persisted by the shared revoke flow)
            # Persist Base64 (optional) but avoid sending a new message; just update the existing card
            if new_link:
                _ = base64.b64encode(new_link.encode()).decode()
            else:
                _ = None
            # Rebuild the subscription detail card with the new URL and update the existing card
            try:
                sub_info = await pasarguard_api.get_fast_user_info(sub.marzban_username, getattr(sub, 'sub_token', None))
                detail_text, detail_kb, _ = build_subscription_detail(sub, sub_info, generate_image=False)
                # Try edit as text message
                try:
                    await callback.message.edit_text(detail_text, parse_mode="HTML", reply_markup=detail_kb.as_markup())
                except Exception:
                    # Media card (photo now; legacy animation cards too): keep the
                    # media, refresh only the caption + keyboard.
                    try:
                        await callback.message.edit_caption(detail_text, parse_mode="HTML", reply_markup=detail_kb.as_markup())
                    except Exception:
                        # Last resort: do nothing (keep prior card) to avoid blank captions
                        pass
            except Exception:
                pass
            # Brief confirmation only (no extra message)
            await callback.answer(t(lang, "new_link_issued"))
            await callback.answer(t(lang, "new_link_issued"), show_alert=True)
        else:
            await callback.answer(t(lang, "error_revoke_link"), show_alert=True)
    except Exception:
        await callback.answer(t(lang, "error_revoke_link"), show_alert=True)


@router.callback_query(F.data.startswith("remove_local_"))
async def remove_local_subscription(callback: CallbackQuery, session: AsyncSession):
    lang = get_cached_lang(callback.from_user.id)
    await callback.answer(t(lang, "removal_disabled"), show_alert=True)
