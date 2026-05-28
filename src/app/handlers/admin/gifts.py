from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import crud
from app.database.models import Subscription, User, UserGift
from app.handlers.admin.common import ADMIN_IDS
from app.utils.bot_i18n import get_cached_lang, guess_lang_from_telegram, t

router = Router()


@router.callback_query(F.data == 'admin_gifts')
async def admin_gifts_menu(callback: CallbackQuery, session: AsyncSession):
    lang = get_cached_lang(callback.from_user.id) or guess_lang_from_telegram(getattr(callback.from_user, "language_code", None))
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(t(lang, "not_authorized"), show_alert=True)
        return
    # List recent pending paid gifts
    result = await session.execute(select(UserGift).filter(UserGift.payment_status == 'pending').order_by(UserGift.created_at.desc()).limit(10))
    gifts = result.scalars().all()
    text = '🎁 مدیریت هدایای پرداختی (رسید ارسال‌شده):\n\n'
    if not gifts:
        text += 'موردی در انتظار نیست.'
    else:
        for g in gifts:
            text += f"#{g.id} | نوع: {g.gift_type} | مبلغ: {g.gift_value:,} | به: {g.receiver_id}\n"
    kb = InlineKeyboardBuilder()
    for g in gifts:
        kb.button(text=f"مشاهده #{g.id}", callback_data=f"show_gift_{g.id}")
    kb.adjust(1)
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith('show_gift_'))
async def show_gift(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    lang = get_cached_lang(callback.from_user.id) or guess_lang_from_telegram(getattr(callback.from_user, "language_code", None))
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(t(lang, "not_authorized"), show_alert=True)
        return
    gid = int(callback.data.split('_')[2])
    gift = await session.get(UserGift, gid)
    if not gift:
        await callback.answer(t(lang, "admin_gift_not_found"), show_alert=True)
        return
    await session.refresh(gift, attribute_names=['sender', 'receiver'])
    # Copy receipt if available
    if gift.payment_receipt_message_id and gift.sender:
        try:
            await bot.copy_message(chat_id=callback.from_user.id, from_chat_id=gift.sender.chat_id, message_id=gift.payment_receipt_message_id)
        except Exception:
            pass
    kb = InlineKeyboardBuilder()
    kb.button(text='✅ تایید', callback_data=f'approve_gift_{gid}')
    kb.button(text='❌ رد', callback_data=f'deny_gift_{gid}')
    kb.adjust(2)
    await callback.message.edit_text(
        t(lang, "admin_gift_details").format(
            id=gift.id,
            sender=(gift.sender.full_name if gift.sender else gift.sender_id),
            receiver=(gift.receiver.full_name if gift.receiver else gift.receiver_id),
            type=gift.gift_type,
            value=f"{gift.gift_value:,}",
            plan=(gift.plan_name or '-'),
            status=gift.payment_status,
            accepted=gift.accepted,
        ),
        reply_markup=kb.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith('approve_gift_'))
async def approve_gift(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    lang = get_cached_lang(callback.from_user.id) or guess_lang_from_telegram(getattr(callback.from_user, "language_code", None))
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(t(lang, "not_authorized"), show_alert=True)
        return
    gid = int(callback.data.split('_')[2])
    gift = await session.get(UserGift, gid)
    if not gift:
        await callback.answer(t(lang, "admin_gift_not_found"), show_alert=True)
        return
    gift.payment_status = 'approved'
    await session.commit()
    # Notify sender and receiver that gift is now payable/available
    try:
        if gift.sender and gift.sender.chat_id:
            await bot.send_message(gift.sender.chat_id, f"✅ پرداخت هدیه #{gid} تایید شد. گیرنده می‌تواند آن را بپذیرد.")
        if gift.receiver and gift.receiver.chat_id:
            from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
            kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='✅ پذیرش هدیه', callback_data=f'gift_accept:{gift.id}')]])
            await bot.send_message(gift.receiver.chat_id, f"🎁 یک هدیه جدید برای شما آماده است. برای افزودن به حساب، دکمه را لمس کنید.", reply_markup=kb)
    except Exception:
        pass
    await callback.answer(t(lang, "admin_gift_approved"))


@router.callback_query(F.data.startswith('deny_gift_'))
async def deny_gift(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    lang = get_cached_lang(callback.from_user.id) or guess_lang_from_telegram(getattr(callback.from_user, "language_code", None))
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(t(lang, "not_authorized"), show_alert=True)
        return
    gid = int(callback.data.split('_')[2])
    gift = await session.get(UserGift, gid)
    if not gift:
        await callback.answer(t(lang, "admin_gift_not_found"), show_alert=True)
        return
    gift.payment_status = 'denied'
    await session.commit()
    try:
        if gift.sender and gift.sender.chat_id:
            await bot.send_message(gift.sender.chat_id, f"❌ پرداخت هدیه #{gid} رد شد. لطفاً دوباره تلاش کنید.")
    except Exception:
        pass
    await callback.answer(t(lang, "admin_gift_denied"))
