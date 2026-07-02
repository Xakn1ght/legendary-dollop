from aiogram.fsm.context import FSMContext
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import crud
from app.database.crud import get_active_user_discounts
from app.utils.bot_i18n import normalize_lang, set_cached_lang, t
from app.utils.validation import InputValidator, sanitize_user_input

from .common import PurchaseState, _get_plan_keyboard_for_user, _lang_for, router
from .coupon import prompt_coupon_or_next
from .username import generate_unique_username, generate_username_suggestions, is_username_taken


# Accept **only** pure-text messages when we ask for the service name
@router.message(PurchaseState.name, lambda m: m.content_type == 'text')
async def process_name(message: Message, state: FSMContext, session: AsyncSession):
    lang = await _lang_for(message, session)

    # Allow /start to reset flow
    if message.text and message.text.startswith("/start"):
        await state.clear()
        return  # Let start handler handle it

    # Validate and sanitize username input
    if not InputValidator.validate_safe_text(message.text):
        await message.answer(
            "نام سرویس نامعتبر است. لطفاً از حروف فارسی، انگلیسی، اعداد و کاراکترهای مجاز استفاده کنید."
            if lang == "fa"
            else "Invalid service name. Please use only allowed characters."
        )
        return

    if not InputValidator.validate_length(message.text, 'custom_username'):
        await message.answer("نام سرویس باید بین ۳ تا ۲۰ کاراکتر باشد." if lang == "fa" else "Service name must be 3 to 20 characters.")
        return

    # Sanitize input
    sanitized_name = sanitize_user_input(message.text)
    if message.text in ('بازگشت🔙', 'Back 🔙', t(lang, "btn_back")):
        await state.set_state(PurchaseState.plan)
        plan_kb = await _get_plan_keyboard_for_user(session, message.chat.id, lang)
        await message.answer(
            ("لطفا یکی از پلن های زیر را انتخاب کنید:" if lang == "fa" else "Please choose a plan:"),
            reply_markup=plan_kb,
        )
        return

    # Be forgiving about stray spaces: "my name 12" -> "myname12" instead of a
    # rejection (the regex below still guards everything else).
    sub_name = (message.text or '').replace(' ', '')
    if message.text in ('اتفاقی', 'Random'):
        import random
        import string

        sub_name = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    else:
        # Validate: only English letters & digits
        import re

        if not re.fullmatch(r'[A-Za-z0-9]+', sub_name):
            error_msg = (
                "❌ نام سرویس نامعتبر است!\n\n"
                "✅ نام باید شامل:\n"
                "• فقط حروف انگلیسی (A-Z, a-z)\n"
                "• فقط اعداد (0-9)\n"
                "• حداقل ۳ کاراکتر\n\n"
                "❌ مجاز نیست:\n"
                "• فاصله، خط تیره، یا کاراکترهای خاص\n"
                "• حروف فارسی یا عربی\n\n"
                "لطفاً نام دیگری وارد کنید یا از گزینه 'اتفاقی' استفاده کنید:"
                if lang == "fa"
                else "❌ Invalid service name!\n\n"
                "✅ Name must include:\n"
                "• Only English letters (A-Z, a-z)\n"
                "• Only numbers (0-9)\n"
                "• At least 3 characters\n\n"
                "❌ Not allowed:\n"
                "• Spaces, dashes, or special characters\n"
                "• Non-English letters\n\n"
                "Please enter another name or use 'Random':"
            )
            await message.answer(
                error_msg,
                reply_markup=ReplyKeyboardMarkup(
                    keyboard=[[KeyboardButton(text=t(lang, "btn_back"))]],
                    resize_keyboard=True,
                    one_time_keyboard=True,
                ),
            )
            return

        # For custom names ensure availability first
        if await is_username_taken(session, sub_name):
            suggestions = await generate_username_suggestions(session, sub_name)
            rows = [[KeyboardButton(text=s)] for s in suggestions]
            rows.append([KeyboardButton(text=('اتفاقی' if lang == 'fa' else 'Random'))])
            rows.append([KeyboardButton(text=t(lang, "btn_back"))])
            markup = ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, one_time_keyboard=True)
            await message.answer(
                ("⚠️ این نام قبلاً گرفته شده است. لطفاً یکی از گزینه‌های پیشنهادی را انتخاب کنید یا نام دیگری وارد کنید:" if lang == "fa" else "⚠️ This name is already taken. Choose a suggestion or enter another name:"),
                reply_markup=markup,
            )
            return  # Stay in the same state until user picks a new name

    # At this point sub_name is available (or random). The order row itself is only
    # created at confirmation (services/flows/purchase.start_purchase_order) — until
    # then everything lives in FSM state.
    await state.update_data(name=sub_name)
    user = await crud.get_user(session, message.chat.id)
    if not user:
        await message.answer(t(lang, "start_bot_first"))
        return
    # Ensure marzban_username is unique; random names still go through uniqueness check
    marzban_username = sub_name if message.text != 'اتفاقی' else await generate_unique_username(session, sub_name)
    await state.update_data(marzban_username=marzban_username)

    # NEW: Check for and ask about applying discounts
    user = await crud.get_user(session, message.chat.id)
    discounts = await get_active_user_discounts(session, user.id)

    if discounts:
        await state.set_state(PurchaseState.ask_discount)

        discount_buttons = []
        for d in discounts:
            discount_buttons.append(
                [
                    KeyboardButton(
                        text=(f"✅ استفاده از {d.percent}% (از {d.source})" if lang == "fa" else f"✅ Use {d.percent}% ({d.source})"),
                    )
                ]
            )

        if len(discounts) > 1:
            discount_buttons.append([KeyboardButton(text=("✅ استفاده از همه تخفیف‌ها (جمع)" if lang == "fa" else "✅ Use all discounts"))])

        discount_buttons.append([KeyboardButton(text=("خیر، برای بعد ذخیره کن" if lang == "fa" else "No, save for later"))])

        discount_markup = ReplyKeyboardMarkup(
            keyboard=discount_buttons,
            resize_keyboard=True,
            one_time_keyboard=True,
        )

        await message.answer(
            ("شما چند تخفیف فعال دارید! کدام را می‌خواهید روی این خرید اعمال کنید?" if lang == "fa" else "You have active discounts. Which one do you want to apply?"),
            reply_markup=discount_markup,
        )
        return
    # No active discounts → offer reward coupons (then credit, then summary).
    await prompt_coupon_or_next(message, state, session, user, lang)


@router.message(PurchaseState.ask_discount)
async def process_discount_choice(message: Message, state: FSMContext, session: AsyncSession):
    """Handles the user's choice on whether to apply their discount."""
    # Allow /start to reset flow
    if message.text and message.text.startswith("/start"):
        await state.clear()
        return  # Let start handler handle it

    user = await crud.get_user(session, message.chat.id)
    lang = normalize_lang(getattr(user, "language", None)) if user else normalize_lang(getattr(message.from_user, "language_code", None))
    set_cached_lang(message.chat.id, lang)
    discounts = await get_active_user_discounts(session, user.id)

    selected_ids = []
    used_percents = []

    if ("استفاده از همه" in (message.text or "")) or ("Use all" in (message.text or "")):
        selected_ids = [d.id for d in discounts]
        used_percents = [d.percent for d in discounts]
    else:
        for d in discounts:
            txt = (message.text or "")
            if (f"{d.percent}%" in txt) and (("استفاده" in txt) or ("Use" in txt) or ("%" in txt)):
                selected_ids.append(d.id)
                used_percents.append(d.percent)
                break

    if selected_ids:
        await state.update_data(apply_discount=True, used_discount_percents=used_percents, used_discount_ids=selected_ids)
    else:
        await state.update_data(apply_discount=False, used_discount_percents=[], used_discount_ids=[])

    # After discount → offer reward coupons (then credit, then summary).
    await prompt_coupon_or_next(message, state, session, user, lang)


# Any non-text (media, voice, sticker, etc.) in the *name* step → politely reject
@router.message(PurchaseState.name)
async def reject_name_media(message: Message, session: AsyncSession):
    lang = await _lang_for(message, session)
    await message.answer(
        t(lang, "purchase_text_name_only"),
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="اتفاقی"), KeyboardButton(text="Random")], [KeyboardButton(text="بازگشت🔙"), KeyboardButton(text="Back 🔙")]],
            resize_keyboard=True,
            one_time_keyboard=True,
        ),
    )
