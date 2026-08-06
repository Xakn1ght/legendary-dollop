import asyncio

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import ADMIN_ID
from app.database import crud
from app.keyboards.reply import get_main_keyboard
from app.services.flows.errors import FlowError
from app.services.flows.purchase import cancel_purchase_order, submit_purchase_receipt
from app.utils.bot_i18n import text_matches

from .common import PurchaseState, router


@router.message(PurchaseState.receipt, F.photo)
async def process_receipt(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    user = await crud.get_user(session, message.chat.id)
    user_chat_id = user.chat_id
    sub_id = data.get('sub_id')
    if not sub_id:
        return  # Should not happen

    try:
        sub = await submit_purchase_receipt(session, user, sub_id, receipt_message_id=message.message_id)
    except FlowError:
        await state.clear()
        await message.answer(
            "این سفارش قابل پردازش نیست. لطفاً دوباره از منوی خرید اقدام کنید.",
            reply_markup=get_main_keyboard(message.chat.id),
        )
        return

    # Notify admin web panel (live update)
    try:
        from app.api.routes.admin_ws import broadcast_admin_event

        asyncio.create_task(broadcast_admin_event('receipts_updated', {'order_id': sub.id}))
    except Exception:
        pass

    builder = InlineKeyboardBuilder()
    builder.button(text="تایید", callback_data=f"approve_sub_{sub_id}")
    builder.button(text="رد", callback_data=f"deny_sub_{sub_id}")
    builder.adjust(2)

    from app.core.settings import PLANS
    from app.utils.receipt_captions import purchase_receipt_caption

    admin_msg = purchase_receipt_caption(sub, user, source="bot", plans=PLANS)

    # ONE admin message: receipt photo + order details caption + approve/deny
    # buttons (previously the photo and the actionable text arrived separately).
    from app.utils.admin_bot_helper import get_admin_bot, relay_user_receipt_photo_to_admin

    admin_bot = get_admin_bot()
    admin_action_msg = None
    if admin_bot:
        try:
            admin_action_msg = await relay_user_receipt_photo_to_admin(
                message.bot, admin_bot, ADMIN_ID, message,
                caption=admin_msg, reply_markup=builder.as_markup(),
            )
        except Exception:
            admin_action_msg = None
        if admin_action_msg is None:
            # Photo relay failed — at least deliver the actionable text.
            try:
                admin_action_msg = await admin_bot.send_message(ADMIN_ID, admin_msg, reply_markup=builder.as_markup())
            except Exception:
                pass
    try:
        if sub and admin_action_msg is not None:
            sub.admin_receipt_forward_message_id = admin_action_msg.message_id
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

@router.message(PurchaseState.receipt, text_matches("btn_back"))
async def cancel_purchase_receipt(message: Message, state: FSMContext, session: AsyncSession):
    # Cancel the draft order: refunds credit and restores the coupon/discounts that
    # were consumed at order creation (all inside the shared cancel service).
    data_state = await state.get_data()
    sub_id = data_state.get('sub_id')
    if sub_id:
        user = await crud.get_user(session, message.chat.id)
        try:
            await cancel_purchase_order(session, user, sub_id)
        except FlowError:
            pass

    await state.clear()
    await message.answer("خرید لغو شد. به منوی اصلی بازگشتید.", )
