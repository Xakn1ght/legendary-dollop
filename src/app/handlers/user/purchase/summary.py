from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import crud
from app.keyboards.reply import get_main_keyboard
from app.services.flows.errors import FlowError
from app.services.flows.pricing import quote_purchase

from .common import PurchaseState, _confirm_keyboard, _lang_for


async def build_quote_from_state(session: AsyncSession, user, data: dict):
    """Price the order from the current FSM selections via the shared quote service.

    Used by both the summary display and the confirmation step so the number the
    user saw is exactly the number they are charged."""
    return await quote_purchase(
        session,
        user,
        plan_name=data["plan"],
        renewal_plan=data.get("renewal_template") if data.get("auto_renewal") else None,
        discount_ids=(data.get("used_discount_ids") or []) if data.get("apply_discount") else [],
        coupon_id=data.get("coupon_id"),
        use_credit=bool(data.get("apply_credit")),
    )


async def show_order_summary(message: Message, state: FSMContext, session: AsyncSession):
    """Compose and send the order summary. Display only — nothing is consumed or
    persisted until the user confirms."""
    lang = await _lang_for(message, session)
    data = await state.get_data()
    user = await crud.get_user(session, message.chat.id)

    try:
        quote = await build_quote_from_state(session, user, data)
    except FlowError:
        await state.clear()
        await message.answer(
            ("خطا در محاسبه قیمت سفارش. لطفاً دوباره تلاش کنید." if lang == "fa" else "Could not price your order. Please try again."),
            reply_markup=get_main_keyboard(message.chat.id, lang=lang),
        )
        return

    from app.services.flows.pricing import get_plan_info, plan_display_name
    plan_info = get_plan_info(quote.plan_name)
    marzban_username = data.get("marzban_username", "-")

    summary_lines = [
        ("<b>خلاصه سفارش شما:</b>" if lang == "fa" else "<b>Your order summary:</b>"),
        (f"🔸 <b>پلن:</b> {plan_display_name(quote.plan_name)} ({plan_info['gb']} گیگابایت)" if lang == "fa" else f"🔸 <b>Plan:</b> {plan_display_name(quote.plan_name, 'en')} ({plan_info['gb']} GB)"),
        (f"🔸 <b>نام سرویس:</b> <code>{marzban_username}</code>" if lang == "fa" else f"🔸 <b>Service name:</b> <code>{marzban_username}</code>"),
    ]
    if quote.renewal_plan:
        renewal_info = get_plan_info(quote.renewal_plan)
        summary_lines.append(
            (
                f"🔹 <b>تمدید خودکار:</b> {plan_display_name(quote.renewal_plan)} ({renewal_info['gb']} گیگابایت) – {quote.renewal_price:,} تومان"
                if lang == "fa"
                else f"🔹 <b>Auto-renew:</b> {plan_display_name(quote.renewal_plan, 'en')} ({renewal_info['gb']} GB) – {quote.renewal_price:,} Toman"
            )
        )

    summary_lines.append(
        f"🔸 <b>قیمت اولیه:</b> {quote.base_total:,} تومان" if lang == "fa" else f"🔸 <b>Base price:</b> {quote.base_total:,} Toman"
    )

    coupon_amount = quote.coupon.discount_amount if quote.coupon else 0
    percent_discount_amount = quote.discount_amount - coupon_amount
    if percent_discount_amount > 0:
        summary_lines.append(
            (
                f"🔹 <b>تخفیف اعمال شده ({quote.discount_percent}%):</b> -{percent_discount_amount:,} تومان"
                if lang == "fa"
                else f"🔹 <b>Discount applied ({quote.discount_percent}%):</b> -{percent_discount_amount:,} Toman"
            )
        )

    if coupon_amount > 0:
        summary_lines.append(
            (f"🎁 <b>کوپن جایزه:</b> -{coupon_amount:,} تومان" if lang == "fa" else f"🎁 <b>Reward coupon:</b> -{coupon_amount:,} Toman")
        )
    if quote.coupon_free_gb > 0:
        summary_lines.append(
            (f"🎁 <b>ترافیک هدیه کوپن:</b> +{quote.coupon_free_gb} گیگابایت" if lang == "fa" else f"🎁 <b>Coupon bonus traffic:</b> +{quote.coupon_free_gb} GB")
        )

    if quote.credit_used > 0:
        summary_lines.append(
            f"🔹 <b>اعتبار استفاده‌شده:</b> -{quote.credit_used:,} تومان" if lang == "fa" else f"🔹 <b>Credit used:</b> -{quote.credit_used:,} Toman"
        )

    final_display = max(0, quote.final_price)
    summary_lines.append(
        f"💵 <b>مبلغ نهایی قابل پرداخت:</b> {final_display:,} تومان" if lang == "fa" else f"💵 <b>Total to pay:</b> {final_display:,} Toman"
    )

    summary_lines.append(
        "\nلطفا برای تایید و رفتن به مرحله پرداخت، دکمه 'تایید و پرداخت' را بزنید."
        if lang == "fa"
        else "\nTo confirm and continue to payment, tap 'Confirm & Pay'."
    )

    await state.set_state(PurchaseState.confirmation)
    await message.answer("\n".join(summary_lines), reply_markup=_confirm_keyboard(lang), parse_mode='HTML')
