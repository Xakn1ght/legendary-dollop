from datetime import datetime

from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.settings import PLANS, VIP_DISCOUNT_PERCENT
from app.database import crud, models
from app.database.crud import mark_user_discounts_used

from .common import PurchaseState, _confirm_keyboard, _lang_for


async def show_order_summary(message: Message, state: FSMContext, session: AsyncSession):
    """Compose and send order summary, updating subscription row if needed. Used when skipping name step."""
    lang = await _lang_for(message, session)
    data = await state.get_data()
    plan_info = PLANS[data['plan']]
    renewal_template = data.get('renewal_template')
    renewal_price = PLANS[renewal_template]['price'] if renewal_template else None
    renewal_paid = data.get('auto_renewal', False)
    renewal_requested_at = datetime.utcnow() if renewal_paid else None
    # Ensure subscription row updated
    sub_id = data.get('sub_id')
    marzban_username = data['marzban_username']
    user = await crud.get_user(session, message.chat.id)
    if not sub_id:
        # Should not happen, but safeguard
        sub = await crud.create_subscription(
            db=session,
            user_id=user.id,
            referrer_id=data.get('referrer_id'),
            marzban_username=marzban_username,
            plan=data['plan'],
            receipt_message_id=None,
            renewal_paid=renewal_paid,
            renewal_template=renewal_template,
            renewal_price=renewal_price,
            renewal_requested_at=renewal_requested_at,
            renewal_applied=False,
            price=plan_info['price'],
        )
        await state.update_data(sub_id=sub.id)
    else:
        result = await session.execute(select(models.Subscription).filter(models.Subscription.id == sub_id))
        sub = result.scalars().first()
        if sub:
            sub.plan_name = data['plan']
            sub.renewal_paid = renewal_paid
            sub.renewal_template = renewal_template
            sub.renewal_price = renewal_price
            sub.renewal_requested_at = renewal_requested_at
            await session.commit()
            await session.refresh(sub)
    # Pricing
    initial_price = plan_info['price'] + (renewal_price or 0)

    # VIP Discount
    vip_discount_applied = 0
    is_vip = await crud.is_user_vip(session, user.id)
    if is_vip:
        vip_discount_applied = int(initial_price * (VIP_DISCOUNT_PERCENT / 100))
        initial_price = initial_price - vip_discount_applied

    # New Discount Logic (on top of VIP discount)
    apply_discount_flag = data.get('apply_discount', False)
    used_discount_percents = data.get('used_discount_percents', [])
    used_discount_ids = data.get('used_discount_ids', [])
    total_discount_percent = sum(used_discount_percents)
    price_after_discount = initial_price
    discount_applied = 0

    if apply_discount_flag and total_discount_percent > 0:
        discount_amount = int(initial_price * (total_discount_percent / 100))
        price_after_discount = initial_price - discount_amount
        discount_applied = discount_amount
        # IMPORTANT: Consume the discounts after applying them
        await mark_user_discounts_used(session, used_discount_ids)
        await state.update_data(discount_applied_amount=discount_amount)

    # Use credit_used from state, do not recalculate
    credit_used = data.get('credit_used', 0)
    final_price = price_after_discount - credit_used

    summary_lines = [
        ("<b>خلاصه سفارش شما:</b>" if lang == "fa" else "<b>Your order summary:</b>"),
        (f"🔸 <b>پلن:</b> {data['plan']} ({plan_info['gb']} گیگابایت)" if lang == "fa" else f"🔸 <b>Plan:</b> {data['plan']} ({plan_info['gb']} GB)"),
        (f"🔸 <b>نام سرویس:</b> <code>{marzban_username}</code>" if lang == "fa" else f"🔸 <b>Service name:</b> <code>{marzban_username}</code>"),
    ]
    if renewal_template:
        renewal_info = PLANS[renewal_template]
        summary_lines.append(
            (
                f"🔹 <b>تمدید خودکار:</b> {renewal_template} ({renewal_info['gb']} گیگابایت) – {renewal_info['price']:,} تومان"
                if lang == "fa"
                else f"🔹 <b>Auto-renew:</b> {renewal_template} ({renewal_info['gb']} GB) – {renewal_info['price']:,} Toman"
            )
        )

    # Show original price before VIP discount if VIP
    if vip_discount_applied > 0:
        original_price = initial_price + vip_discount_applied
        summary_lines.append(f"🔸 <b>قیمت اولیه:</b> {original_price:,} تومان" if lang == "fa" else f"🔸 <b>Base price:</b> {original_price:,} Toman")
        summary_lines.append(f"👑 <b>تخفیف VIP ({VIP_DISCOUNT_PERCENT}%):</b> -{vip_discount_applied:,} تومان" if lang == "fa" else f"👑 <b>VIP discount ({VIP_DISCOUNT_PERCENT}%):</b> -{vip_discount_applied:,} Toman")
    else:
        summary_lines.append(f"🔸 <b>قیمت اولیه:</b> {initial_price:,} تومان" if lang == "fa" else f"🔸 <b>Base price:</b> {initial_price:,} Toman")

    if discount_applied > 0:
        summary_lines.append(
            (
                f"🔹 <b>تخفیف اعمال شده ({'+'.join(str(p) for p in used_discount_percents)}%):</b> -{discount_applied:,} تومان"
                if lang == "fa"
                else f"🔹 <b>Discount applied ({'+'.join(str(p) for p in used_discount_percents)}%):</b> -{discount_applied:,} Toman"
            )
        )

    if credit_used > 0:
        summary_lines.append(f"🔹 <b>اعتبار استفاده‌شده:</b> -{credit_used:,} تومان" if lang == "fa" else f"🔹 <b>Credit used:</b> -{credit_used:,} Toman")

    summary_lines.append(f"💵 <b>مبلغ نهایی قابل پرداخت:</b> {final_price:,} تومان" if lang == "fa" else f"💵 <b>Total to pay:</b> {final_price:,} Toman")

    summary_lines.append(
        "\nلطفا برای تایید و رفتن به مرحله پرداخت، دکمه 'تایید و پرداخت' را بزنید."
        if lang == "fa"
        else "\nTo confirm and continue to payment, tap 'Confirm & Pay'."
    )
    # Persist rollback info on the subscription row
    try:
        sub_id_persist = data.get('sub_id')
        if sub_id_persist:
            result = await session.execute(select(models.Subscription).filter(models.Subscription.id == sub_id_persist))
            sub_persist = result.scalars().first()
            if sub_persist:
                sub_persist.credit_used = int(credit_used or 0)
                # store discount ids as comma-separated
                sub_persist.applied_discount_ids = ",".join(str(i) for i in (used_discount_ids or [])) if used_discount_ids else None
                await session.commit()
    except Exception:
        pass

    await state.set_state(PurchaseState.confirmation)
    await message.answer("\n".join(summary_lines), reply_markup=_confirm_keyboard(lang), parse_mode='HTML')
