"""Bot purchase flow: optional season-coupon step (one per purchase, no stacking).

Only the coupon_id is held in FSM state; pricing/validation/consumption all happen
in the shared services (flows.pricing quotes it, flows.purchase consumes/restores it).
"""
from aiogram.fsm.context import FSMContext
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import crud
from app.handlers.user.rewards.menu import _coupon_label
from app.services.flows.pricing import SUPPORTED_COUPON_TYPES
from app.utils.bot_i18n import normalize_lang, set_cached_lang

from .common import PurchaseState, router
from .summary import show_order_summary


async def _supported_coupons(session: AsyncSession, user_id: int):
    coupons = await crud.get_active_coupons(session, user_id)
    return [c for c in coupons if c.coupon_type in SUPPORTED_COUPON_TYPES]


async def _prompt_credit_or_summary(message: Message, state: FSMContext, session: AsyncSession, user, lang: str):
    """Shared next-step after discount/coupon: ask about credit if any, else summarize."""
    if user and (user.credit or 0) > 0:
        await state.set_state(PurchaseState.ask_credit)
        credit_markup = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text=(f"✅ بله، {user.credit:,} تومان اعتبار را استفاده کن" if lang == "fa" else f"✅ Yes, use {user.credit:,} credit"))],
                [KeyboardButton(text=("خیر، برای بعد ذخیره کن" if lang == "fa" else "No, save for later"))],
            ],
            resize_keyboard=True,
            one_time_keyboard=True,
        )
        await message.answer(
            (f"شما **{user.credit:,} تومان اعتبار** دارید! آیا می‌خواهید آن را روی این خرید استفاده کنید؟" if lang == "fa" else f"You have **{user.credit:,}** credit. Do you want to use it for this purchase?"),
            reply_markup=credit_markup,
        )
        return
    await show_order_summary(message, state, session)


async def prompt_coupon_or_next(message: Message, state: FSMContext, session: AsyncSession, user, lang: str):
    """If the user holds spendable coupons, offer to apply one; otherwise continue."""
    coupons = await _supported_coupons(session, user.id)
    # free_autorenew only discounts a renewal plan — hide it when this order has none,
    # so the user can't pick a coupon that would fail to price at summary.
    data = await state.get_data()
    if not (data.get("auto_renewal") and data.get("renewal_template")):
        coupons = [c for c in coupons if c.coupon_type != "free_autorenew"]
    if not coupons:
        await state.update_data(coupon_id=None)
        await _prompt_credit_or_summary(message, state, session, user, lang)
        return

    choices = []
    buttons = []
    for i, c in enumerate(coupons, start=1):
        choices.append(c.id)
        buttons.append([KeyboardButton(text=f"{i}) {_coupon_label(c, lang)}")])
    buttons.append([KeyboardButton(text=("بدون کوپن" if lang == "fa" else "No coupon"))])

    await state.update_data(coupon_choices=choices)
    await state.set_state(PurchaseState.ask_coupon)
    await message.answer(
        (
            "🎁 کوپن جایزه دارید! یکی را برای این خرید انتخاب کنید (هر خرید فقط یک کوپن):"
            if lang == "fa"
            else "🎁 You have reward coupons! Pick one for this purchase (one coupon per purchase):"
        ),
        reply_markup=ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True, one_time_keyboard=True),
    )


@router.message(PurchaseState.ask_coupon)
async def process_coupon_choice(message: Message, state: FSMContext, session: AsyncSession):
    if message.text and message.text.startswith("/start"):
        await state.clear()
        return

    user = await crud.get_user(session, message.chat.id)
    lang = normalize_lang(getattr(user, "language", None)) if user else normalize_lang(getattr(message.from_user, "language_code", None))
    set_cached_lang(message.chat.id, lang)

    data = await state.get_data()
    choices = data.get("coupon_choices") or []
    text = (message.text or "").strip()

    selected = None
    if text not in ("بدون کوپن", "No coupon"):
        # Buttons are prefixed "N) ..." — parse the leading index into the choices list.
        lead = text.split(")", 1)[0].strip()
        if lead.isdigit():
            idx = int(lead) - 1
            if 0 <= idx < len(choices):
                cid = choices[idx]
                c = await crud.get_coupon_by_id(session, cid)
                # Re-validate ownership/active/expiry before trusting the pick.
                import datetime as _dt
                if c and c.user_id == user.id and c.status == "active" and not (c.expires_at and c.expires_at < _dt.datetime.utcnow()):
                    selected = c

    # Only the id matters: the shared quote re-validates and prices the coupon.
    await state.update_data(coupon_id=selected.id if selected is not None else None)

    await _prompt_credit_or_summary(message, state, session, user, lang)
