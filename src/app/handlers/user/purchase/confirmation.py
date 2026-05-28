from aiogram import Bot, F
from aiogram.fsm.context import FSMContext
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import ADMIN_ID, PLANS
from app.database import crud
from app.handlers.admin.subscription import process_approved_subscription
from app.keyboards.reply import KEYBOARD_MARKUP_BACK, get_main_keyboard
from app.utils.bot_i18n import t

from .common import PurchaseState, _lang_for, router


@router.message(PurchaseState.confirmation, lambda m: (m.text or "").strip() in {"تایید و پرداخت ✅", "Confirm & Pay ✅"})
async def process_confirmation(message: Message, state: FSMContext, session: AsyncSession, bot: Bot):
    lang = await _lang_for(message, session)
    data = await state.get_data()
    plan_info = PLANS[data['plan']]
    renewal_template = data.get('renewal_template')
    renewal_price = PLANS[renewal_template]['price'] if renewal_template else 0
    initial_price = plan_info['price'] + (renewal_price or 0)
    used_discount_percents = data.get('used_discount_percents', [])
    total_discount_percent = sum(used_discount_percents)
    price_after_discount = initial_price
    if total_discount_percent > 0:
        discount_amount = int(initial_price * (total_discount_percent / 100))
        price_after_discount = initial_price - discount_amount
    credit_used = data.get('credit_used', 0)
    final_price = price_after_discount - credit_used
    if final_price <= 0:
        # FULLY PAID BY CREDIT/DISCOUNT
        sub_id = data.get('sub_id')
        if not sub_id:
            await message.answer(
                ("خطا: شماره سفارش یافت نشد. لطفاً دوباره تلاش کنید." if lang == "fa" else "Error: order id not found. Please try again."),
                reply_markup=get_main_keyboard(message.chat.id, lang=lang),
            )
            await state.clear()
            return

        # Use the centralized processing function
        success = await process_approved_subscription(sub_id, session, bot)

        if success:
            await message.answer(
                ("✅ سفارش شما با موفقیت با اعتبار پرداخت و فعال شد." if lang == "fa" else "✅ Your order was paid with credit/discount and activated."),
                reply_markup=get_main_keyboard(message.chat.id, lang=lang),
            )
            # Send admin notification
            user = await crud.get_user(session, message.chat.id)
            marzban_username = data.get('marzban_username', '-')
            admin_msg = (
                f"✅ سفارش جدید با پرداخت کامل توسط اعتبار/تخفیف (پردازش خودکار):\n"
                f"کاربر: {user.full_name} ({user.chat_id})\n"
                f"پلن: {data['plan']} ({plan_info['gb']} گیگابایت)\n"
                f"نام سرویس: {marzban_username}\n"
                f"مبلغ اولیه: {initial_price:,} تومان\n"
            )
            if total_discount_percent > 0:
                admin_msg += f"تخفیف: {total_discount_percent}%\n"
            if credit_used > 0:
                admin_msg += f"اعتبار استفاده‌شده: {credit_used:,} تومان\n"
            admin_msg += f"مبلغ نهایی: ۰ تومان (پرداخت کامل)\n"
            admin_msg += f"شماره سفارش: {sub_id}"
            from app.utils.admin_bot_helper import get_admin_bot

            _ab = get_admin_bot()
            if _ab:
                try:
                    await _ab.send_message(ADMIN_ID, admin_msg)
                except Exception:
                    pass
        else:
            await message.answer(
                ("متاسفانه در فعال‌سازی سرویس شما مشکلی پیش آمد. لطفاً به پشتیبانی اطلاع دهید." if lang == "fa" else "We couldn't activate your service. Please contact support."),
                reply_markup=get_main_keyboard(message.chat.id, lang=lang),
            )

        await state.clear()
        return

    await message.answer(
        (
            (
                "✅ سفارش شما تایید شد.\n\n"
                "لطفا هزینه را به شماره کارت زیر واریز کرده و سپس تصویر رسید را ارسال کنید:\n"
                if lang == "fa"
                else
                "✅ Your order is confirmed.\n\n"
                "Please transfer the amount to the card below, then send the receipt image:\n"
            )
            + "<code>6037-xxxx-xxxx-xxxx</code>\n\n"
            + (
                "پس از ارسال رسید، سرویس شما در اسرع وقت فعال خواهد شد."
                if lang == "fa"
                else "After you send the receipt, your service will be activated as soon as possible."
            )
        ),
        reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=t(lang, "btn_back"))]], resize_keyboard=True, one_time_keyboard=True),
        parse_mode='HTML',
    )
    await state.set_state(PurchaseState.receipt)

@router.callback_query(F.data == "enable_auto_renew")
async def enable_auto_renew_callback(callback, state: FSMContext):
    await state.update_data(auto_renew=True)
    plan_buttons = [[KeyboardButton(text=plan)] for plan in PLANS.keys()]
    markup = ReplyKeyboardMarkup(keyboard=plan_buttons, resize_keyboard=True, one_time_keyboard=True)
    await callback.message.answer(
        "برای تمدید خودکار، لطفا پلن مورد نظر برای دوره بعد را انتخاب کنید:",
        reply_markup=markup,
    )
    await state.set_state(PurchaseState.renewal_template)
    await callback.answer()

@router.callback_query(F.data == "confirm_payment")
async def confirm_payment_callback(callback, state: FSMContext):
    await callback.message.answer(
        "لطفا هزینه را به شماره کارت زیر واریز کرده و سپس تصویر رسید را ارسال کنید:\n"
        "<code>6037-xxxx-xxxx-xxxx</code>\n\n"
        "پس از ارسال رسید، سرویس شما در اسرع وقت فعال خواهد شد.",
        reply_markup=KEYBOARD_MARKUP_BACK,
        parse_mode='HTML',
    )
    await callback.answer()
