import logging
from datetime import datetime, timedelta

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery
from sqlalchemy import update as _sql_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import BOT_TOKEN
from app.database import crud, notifications_crud
from app.database.models import User, VipOrder
from app.handlers.admin.common import ADMIN_IDS
from app.utils.bot_i18n import guess_lang_from_telegram, normalize_lang, set_cached_lang, t

router = Router()


async def _admin_lang(session: AsyncSession, tg_user) -> str:
    try:
        u = await crud.get_user(session, int(tg_user.id))
        lang = normalize_lang(getattr(u, "language", None)) if u else guess_lang_from_telegram(getattr(tg_user, "language_code", None))
        set_cached_lang(int(tg_user.id), lang)
        return lang
    except Exception:
        return guess_lang_from_telegram(getattr(tg_user, "language_code", None))


async def _notify_user_via_main_bot(chat_id: int, text: str, parse_mode: str = "Markdown") -> None:
    if not BOT_TOKEN:
        return
    try:
        from aiogram import Bot as _Bot

        b = _Bot(token=BOT_TOKEN)
        try:
            await b.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode)
        finally:
            try:
                await b.session.close()
            except Exception:
                pass
    except Exception:
        return


async def claim_pending_vip_order(session: AsyncSession, order_id: int) -> bool:
    """Atomic pending → processing claim (same pattern as the admin panel's
    vip_orders handlers) so a double-tap or panel+bot race can't approve or
    deny the same order twice. Returns False when someone else already took it."""
    res = await session.execute(
        _sql_update(VipOrder)
        .where(VipOrder.id == order_id, VipOrder.status == "pending")
        .values(status="processing")
    )
    await session.commit()
    return (res.rowcount or 0) > 0


async def unclaim_vip_order(session: AsyncSession, order_id: int) -> None:
    try:
        await session.execute(
            _sql_update(VipOrder)
            .where(VipOrder.id == order_id, VipOrder.status == "processing")
            .values(status="pending")
        )
        await session.commit()
    except Exception:
        logging.exception(f"[VIP] could not release claim on order {order_id}")


async def activate_vip_order(session: AsyncSession, vip_order: VipOrder, *,
                             approved_by: int | None = None,
                             notify_user_bot=None,
                             claimed: bool = False) -> bool:
    """Grant VIP for an order and notify the user. Shared by the admin Approve
    button and the SMS auto-approver so both paths behave identically.

    Only acts on a still-'pending' order (idempotent), or a 'processing' one
    when the caller already won the atomic claim (``claimed=True``).
    ``notify_user_bot`` is an optional live user-bot to DM through; falls back
    to a short-lived bot. Returns True if it flipped the order to approved.
    """
    expected = "processing" if claimed else "pending"
    if vip_order.status != expected:
        return False
    user: User | None = await session.get(User, vip_order.user_id)
    if not user:
        return False

    user.is_vip = True
    duration_text = "دائمی"
    if vip_order.days and vip_order.days > 0:
        now = datetime.utcnow()
        if user.vip_until and user.vip_until > now:
            user.vip_until = user.vip_until + timedelta(days=int(vip_order.days))
        else:
            user.vip_until = now + timedelta(days=int(vip_order.days))
        duration_text = f"{int(vip_order.days)} روز"
    else:
        user.vip_until = None

    vip_order.status = "approved"
    try:
        vip_order.approved_at = datetime.utcnow()
    except Exception:
        pass
    if approved_by is not None:
        try:
            vip_order.approved_by = int(approved_by)
        except Exception:
            pass

    try:
        await notifications_crud.create_notification(
            db=session,
            user_id=user.id,
            type="vip_granted",
            title="تبریک! VIP فعال شد",
            message=f"اشتراک VIP شما فعال شد ({duration_text}). از مزایای ویژه لذت ببرید!",
            sent_to_webapp=True,
            sent_to_bot=True,
        )
    except Exception as e:
        logging.warning(f"[VIP] Failed to create notification: {e}")

    await session.commit()

    msg = (
        f"*تبریک! VIP فعال شد*\n\n"
        f"اشتراک VIP شما با موفقیت فعال شد.\n"
        f"مدت: {duration_text}\n\n"
        f"از مزایای ویژه VIP لذت ببرید!"
    )
    try:
        if user.chat_id and notify_user_bot is not None:
            await notify_user_bot.send_message(chat_id=int(user.chat_id), text=msg, parse_mode="Markdown")
        elif user.chat_id:
            await _notify_user_via_main_bot(int(user.chat_id), msg, parse_mode="Markdown")
    except Exception:
        pass
    return True


@router.callback_query(F.data.startswith("approve_vip_"))
async def approve_vip_order(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    lang = await _admin_lang(session, callback.from_user)
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(t(lang, "not_authorized"), show_alert=True)
        return

    try:
        order_id = int(callback.data.split("_")[2])
    except Exception:
        await callback.answer("Invalid order id", show_alert=True)
        return

    if not await claim_pending_vip_order(session, order_id):
        vip_order = await session.get(VipOrder, order_id)
        if not vip_order:
            await callback.answer("Order not found", show_alert=True)
            return
        await callback.answer("Already processed", show_alert=True)
        try:
            await callback.message.delete()
        except Exception:
            pass
        return

    vip_order: VipOrder | None = await session.get(VipOrder, order_id)
    await session.refresh(vip_order)

    # Any failure inside activation must release the claim, or the order
    # wedges in 'processing' and the button looks dead forever (this is
    # exactly what the int32 approved_by overflow did).
    try:
        activated = await activate_vip_order(session, vip_order, approved_by=callback.from_user.id, claimed=True)
    except Exception:
        logging.exception(f"[VIP] approve failed for order {order_id}")
        try:
            await session.rollback()
        except Exception:
            pass
        await unclaim_vip_order(session, order_id)
        await callback.answer("خطا در تایید — دوباره تلاش کنید", show_alert=True)
        return
    if not activated:
        await unclaim_vip_order(session, order_id)
        await callback.answer("User not found", show_alert=True)
        return

    await callback.answer("✅ تایید شد")
    # Audit trail: stamp the VIP receipt card verified instead of deleting
    # (2026-07-13, Pasha — same rule as purchase/charge receipts).
    try:
        from app.utils.receipt_captions import verified_stamp

        approver = (
            getattr(callback.from_user, "full_name", None)
            or getattr(callback.from_user, "username", None)
            or "ادمین"
        )
        stamped = f"{callback.message.caption or callback.message.text or ''}\n\n{verified_stamp(approver)}".strip()
        if callback.message.caption is not None:
            await callback.message.edit_caption(caption=stamped, reply_markup=None)
        else:
            await callback.message.edit_text(stamped, reply_markup=None)
    except Exception:
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass


@router.callback_query(F.data.startswith("deny_vip_"))
async def deny_vip_order(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    lang = await _admin_lang(session, callback.from_user)
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(t(lang, "not_authorized"), show_alert=True)
        return

    try:
        order_id = int(callback.data.split("_")[2])
    except Exception:
        await callback.answer("Invalid order id", show_alert=True)
        return

    if not await claim_pending_vip_order(session, order_id):
        vip_order = await session.get(VipOrder, order_id)
        if not vip_order:
            await callback.answer("Order not found", show_alert=True)
            return
        await callback.answer("Already processed", show_alert=True)
        try:
            await callback.message.delete()
        except Exception:
            pass
        return

    vip_order: VipOrder | None = await session.get(VipOrder, order_id)
    await session.refresh(vip_order)
    user: User | None = await session.get(User, vip_order.user_id)

    vip_order.status = "denied"
    try:
        vip_order.approved_at = datetime.utcnow()
    except Exception:
        pass

    if user:
        try:
            await notifications_crud.create_notification(
                db=session,
                user_id=user.id,
                type="vip_denied",
                title="درخواست VIP رد شد",
                message="درخواست خرید VIP شما رد شد. برای اطلاعات بیشتر با پشتیبانی تماس بگیرید.",
                sent_to_webapp=True,
                sent_to_bot=True,
            )
        except Exception as e:
            logging.warning(f"[VIP] Failed to create denial notification: {e}")

    await session.commit()

    # Notify user in the main (user-facing) bot (best-effort)
    try:
        if user and user.chat_id:
            msg = "❌ *درخواست VIP رد شد*\n\nدرخواست خرید VIP شما رد شد.\nبرای اطلاعات بیشتر با پشتیبانی تماس بگیرید."
            await _notify_user_via_main_bot(int(user.chat_id), msg, parse_mode="Markdown")
    except Exception:
        pass

    await callback.answer("❌ رد شد")
    try:
        await callback.message.delete()
    except Exception:
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
