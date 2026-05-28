import asyncio

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.settings import ADMIN_ID
from app.database import crud, models
from app.keyboards.reply import get_main_keyboard

from .common import PurchaseState, _cleanup_pending_subscription, router


@router.message(PurchaseState.receipt, F.photo)
async def process_receipt(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    user = await crud.get_user(session, message.chat.id)
    user_full_name = user.full_name
    user_chat_id = user.chat_id
    sub_id = data.get('sub_id')
    marzban_username = data.get('marzban_username')
    # Only update the existing subscription with the receipt message id
    sub = None
    if sub_id:
        result = await session.execute(select(models.Subscription).filter(models.Subscription.id == sub_id))
        sub = result.scalars().first()
        if sub:
            sub.receipt_message_id = message.message_id
            await session.commit()
            await session.refresh(sub)
            # Notify admin web panel (live update)
            try:
                from app.api.routes.admin_ws import broadcast_admin_event

                asyncio.create_task(broadcast_admin_event('receipts_updated', {'order_id': sub.id}))
            except Exception:
                pass
    else:
        return  # Should not happen

    # Forward the receipt to admin bot (not user bot)
    from app.utils.admin_bot_helper import get_admin_bot

    admin_bot = get_admin_bot()
    if admin_bot:
        try:
            from app.utils.admin_bot_helper import relay_user_receipt_photo_to_admin

            forwarded = await relay_user_receipt_photo_to_admin(message.bot, admin_bot, ADMIN_ID, message)
            if sub and forwarded:
                sub.admin_receipt_forward_message_id = forwarded.message_id
                await session.commit()
                await session.refresh(sub)
        except Exception:
            pass

    builder = InlineKeyboardBuilder()
    builder.button(text="✅ تایید", callback_data=f"approve_sub_{sub_id}")
    builder.button(text="❌ رد", callback_data=f"deny_sub_{sub_id}")
    builder.button(text="💬 Chat", callback_data=f"chat_sub_{sub_id}_{user_chat_id}")
    builder.adjust(2)

    admin_msg = (
        f" رسید جدید برای کاربر {user_full_name} ({user_chat_id}) برای پلن {data['plan']} با نام {marzban_username}"
    )
    renewal_tpl = data.get('renewal_template')
    if renewal_tpl:
        admin_msg += f" – تمدید خودکار برای پلن {renewal_tpl}"

    # Send the actionable admin message to admin bot (not user bot)
    admin_action_msg = None
    if admin_bot:
        try:
            admin_action_msg = await admin_bot.send_message(ADMIN_ID, admin_msg, reply_markup=builder.as_markup())
        except Exception:
            pass
    try:
        if sub and admin_action_msg is not None:
            sub.admin_request_message_id = admin_action_msg.message_id
            await session.commit()
    except Exception:
        pass
    await state.clear()
    await message.answer(
        " رسید شما با موفقیت ارسال شد.\n"
        "لطفا منتظر تایید ادمین بمانید. به محض تایید، لینک اشتراک برای شما ارسال خواهد شد.",
        reply_markup=get_main_keyboard(message.chat.id),
    )

@router.message(PurchaseState.receipt, F.text == 'بازگشت🔙')
async def cancel_purchase_receipt(message: Message, state: FSMContext, session: AsyncSession):
    # Refund credit if used and purchase cancelled
    data_state = await state.get_data()
    credit_used = data_state.get('credit_used', 0)
    if credit_used:
        await crud.add_credit(session, message.chat.id, credit_used)

    # Delete pending subscription (no receipt)
    await _cleanup_pending_subscription(session, state)

    await state.clear()
    await message.answer("خرید لغو شد. به منوی اصلی بازگشتید.", )
