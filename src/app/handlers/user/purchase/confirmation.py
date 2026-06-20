from aiogram import Bot, F
from aiogram.fsm.context import FSMContext
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import ADMIN_ID, PLANS
from app.database import crud
from app.keyboards.reply import KEYBOARD_MARKUP_BACK, get_main_keyboard
from app.services.flows.errors import FlowError
from app.services.flows.purchase import start_purchase_order
from app.utils.bot_i18n import t

from .common import PurchaseState, _lang_for, _name_keyboard, router
from .summary import build_quote_from_state


@router.message(PurchaseState.confirmation, lambda m: (m.text or "").strip() in {"تایید و پرداخت ✅", "Confirm & Pay ✅"})
async def process_confirmation(message: Message, state: FSMContext, session: AsyncSession, bot: Bot):
    lang = await _lang_for(message, session)
    data = await state.get_data()
    user = await crud.get_user(session, message.chat.id)
    if not user:
        await state.clear()
        await message.answer(t(lang, "start_bot_first"), reply_markup=get_main_keyboard(message.chat.id, lang=lang))
        return

    try:
        # Same quote the summary displayed; the order (and the consumption of
        # credit/discounts/coupon) is created here in one shared-service call.
        quote = await build_quote_from_state(session, user, data)
        result = await start_purchase_order(
            session,
            user,
            quote=quote,
            service_name=data.get("marzban_username"),
            referrer_id=data.get("referrer_id"),
            auto_renewal=bool(data.get("auto_renewal")),
            bot=bot,
        )
    except FlowError as e:
        if e.code in ("invalid_service_name", "service_name_taken"):
            await state.set_state(PurchaseState.name)
            await message.answer(
                ("⚠️ این نام دیگر در دسترس نیست. لطفاً نام دیگری انتخاب کنید:" if lang == "fa" else "⚠️ That name is no longer available. Please pick another:"),
                reply_markup=_name_keyboard(lang),
            )
            return
        await state.clear()
        await message.answer(
            (
                "متاسفانه در ثبت سفارش شما مشکلی پیش آمد. لطفاً دوباره تلاش کنید یا به پشتیبانی اطلاع دهید."
                if lang == "fa"
                else "We couldn't register your order. Please try again or contact support."
            ),
            reply_markup=get_main_keyboard(message.chat.id, lang=lang),
        )
        return

    sub = result.subscription
    await state.update_data(sub_id=sub.id, marzban_username=sub.marzban_username)
    from app.services.flows.pricing import get_plan_info
    plan_info = get_plan_info(quote.plan_name)

    if result.auto_approved:
        # FULLY PAID BY CREDIT/DISCOUNT/COUPON
        await message.answer(
            ("✅ سفارش شما با موفقیت با اعتبار پرداخت و فعال شد." if lang == "fa" else "✅ Your order was paid with credit/discount and activated."),
            reply_markup=get_main_keyboard(message.chat.id, lang=lang),
        )
        admin_msg = (
            f"✅ سفارش جدید با پرداخت کامل توسط اعتبار/تخفیف (پردازش خودکار):\n"
            f"کاربر: {user.full_name} ({user.chat_id})\n"
            f"پلن: {quote.plan_name} ({plan_info['gb']} گیگابایت)\n"
            f"نام سرویس: {sub.marzban_username}\n"
            f"مبلغ اولیه: {quote.base_total:,} تومان\n"
        )
        if quote.discount_percent > 0:
            admin_msg += f"تخفیف: {quote.discount_percent}%\n"
        if quote.credit_used > 0:
            admin_msg += f"اعتبار استفاده‌شده: {quote.credit_used:,} تومان\n"
        admin_msg += "مبلغ نهایی: ۰ تومان (پرداخت کامل)\n"
        admin_msg += f"شماره سفارش: {sub.id}"
        from app.utils.admin_bot_helper import get_admin_bot

        _ab = get_admin_bot()
        if _ab:
            try:
                await _ab.send_message(ADMIN_ID, admin_msg)
            except Exception:
                pass

        await state.clear()
        return

    # Same admin-configured card the webapp shows (read at call time — the admin
    # panel can change it at runtime).
    from app.core.settings import payment_ui as _payment

    card_line = f"<code>{_payment.PAYMENT_CARD_NUMBER}</code>"
    if _payment.PAYMENT_CARD_HOLDER:
        card_line += f"\n{_payment.PAYMENT_CARD_HOLDER}"

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
            + card_line + "\n\n"
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
    from app.core.settings import payment_ui as _payment

    await callback.message.answer(
        "لطفا هزینه را به شماره کارت زیر واریز کرده و سپس تصویر رسید را ارسال کنید:\n"
        f"<code>{_payment.PAYMENT_CARD_NUMBER}</code>\n\n"
        "پس از ارسال رسید، سرویس شما در اسرع وقت فعال خواهد شد.",
        reply_markup=KEYBOARD_MARKUP_BACK,
        parse_mode='HTML',
    )
    await callback.answer()
