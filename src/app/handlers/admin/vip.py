import logging
from datetime import datetime, timedelta

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery
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

    vip_order: VipOrder | None = await session.get(VipOrder, order_id)
    if not vip_order:
        await callback.answer("Order not found", show_alert=True)
        return

    if vip_order.status != "pending":
        await callback.answer("Already processed", show_alert=True)
        try:
            await callback.message.delete()
        except Exception:
            pass
        return

    user: User | None = await session.get(User, vip_order.user_id)
    if not user:
        await callback.answer("User not found", show_alert=True)
        return

    # Set VIP status
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
        # Lifetime VIP
        user.vip_until = None

    vip_order.status = "approved"
    try:
        vip_order.approved_at = datetime.utcnow()
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

    # Notify user in the main (user-facing) bot (best-effort)
    try:
        if user.chat_id:
            msg = (
                f"*تبریک! VIP فعال شد*\n\n"
                f"اشتراک VIP شما با موفقیت فعال شد.\n"
                f"مدت: {duration_text}\n\n"
                f"از مزایای ویژه VIP لذت ببرید!"
            )
            await _notify_user_via_main_bot(int(user.chat_id), msg, parse_mode="Markdown")
    except Exception:
        pass

    await callback.answer("✅ تایید شد")
    try:
        await callback.message.delete()
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

    vip_order: VipOrder | None = await session.get(VipOrder, order_id)
    if not vip_order:
        await callback.answer("Order not found", show_alert=True)
        return

    if vip_order.status != "pending":
        await callback.answer("Already processed", show_alert=True)
        try:
            await callback.message.delete()
        except Exception:
            pass
        return

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
