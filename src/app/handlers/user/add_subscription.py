from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import PLANS
from app.database import crud
from app.keyboards.reply import KEYBOARD_MARKUP_BACK, KEYBOARD_MARKUP_MAIN, get_main_keyboard
from app.services.marzban import marzban_api
from app.utils.bot_i18n import normalize_lang, set_cached_lang, t, text_matches

router = Router()

class AddSubState(StatesGroup):
    link = State()


def _build_plan_keyboard() -> ReplyKeyboardMarkup:
    """Return a reply keyboard showing available plans plus a back button."""
    plan_keys = [k for k, _ in sorted(PLANS.items(), key=lambda kv: kv[1].get('gb', 0))]
    rows = []
    # put two buttons per row
    for i in range(0, len(plan_keys), 2):
        row = [KeyboardButton(text=plan_keys[i])]
        if i + 1 < len(plan_keys):
            row.append(KeyboardButton(text=plan_keys[i + 1]))
        rows.append(row)
    rows.append([KeyboardButton(text='بازگشت🔙')])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


@router.message(text_matches("btn_add_service"))
async def start_add_subscription(message: Message, state: FSMContext, session: AsyncSession):
    """Begin flow: ask user to paste their subscription link."""
    user = await crud.get_user(session, message.chat.id)
    # Better language detection: check user language first, then Telegram language_code, then default to fa
    lang = "fa"
    if user and hasattr(user, "language") and user.language:
        lang = normalize_lang(user.language)
    elif message.from_user and hasattr(message.from_user, "language_code") and message.from_user.language_code:
        lang = normalize_lang(message.from_user.language_code)
    # Ensure lang is either 'fa' or 'en'
    if lang not in ("fa", "en"):
        lang = "fa"
    set_cached_lang(message.chat.id, lang)
    
    # Check if user is registered (has referral code)
    if not user:
        # User not registered, ask for referral code first
        from app.handlers.user.start import ReferralStates
        await state.set_state(ReferralStates.awaiting_code)
        await state.update_data(lang=lang, return_to="add_subscription")
        await message.answer(
            (
                "🔐 برای افزودن اشتراک، ابتدا باید در ربات ثبت‌نام کنید.\n\n"
                "لطفاً کد دعوت خود را ارسال کنید:\n"
                "کد دعوت را از دوستان خود بگیرید یا در گروه های ما بپرسید."
                if lang == "fa" else
                "🔐 To add a subscription, you need to register first.\n\n"
                "Please send your referral code:\n"
                "Get the invitation code from your friends or ask in our groups."
            ),
        )
        return
    
    await state.set_state(AddSubState.link)
    await message.answer(
        t(lang, "add_subscription_prompt"),
        reply_markup=KEYBOARD_MARKUP_BACK,
    )


@router.message(AddSubState.link)
async def receive_link(message: Message, state: FSMContext, session: AsyncSession):
    user = await crud.get_user(session, message.chat.id)
    # Better language detection: check user language first, then Telegram language_code, then default to fa
    lang = "fa"
    if user and hasattr(user, "language") and user.language:
        lang = normalize_lang(user.language)
    elif message.from_user and hasattr(message.from_user, "language_code") and message.from_user.language_code:
        lang = normalize_lang(message.from_user.language_code)
    # Ensure lang is either 'fa' or 'en'
    if lang not in ("fa", "en"):
        lang = "fa"
    set_cached_lang(message.chat.id, lang)

    # Allow /start to reset flow
    if message.text and message.text.startswith("/start"):
        await state.clear()
        return  # Let start handler handle it

    if message.text in (t(lang, "btn_back"), 'بازگشت🔙', 'Back 🔙'):
        await state.clear()
        await message.answer(
            ('عملیات لغو شد.' if lang == "fa" else 'Cancelled.'),
            reply_markup=get_main_keyboard(message.chat.id, lang=lang),
        )
        return

    if not message.text:
        await message.answer('لطفاً لینک اشتراک معتبر ارسال کنید.' if lang == "fa" else 'Please send a valid subscription link.')
        return

    link = message.text.strip()

    # Extract token from link
    import re
    import urllib.parse
    token_match = re.search(r"/sub/([^/]+)/?", link)
    if not token_match:
        await message.answer(t(lang, "add_subscription_invalid_format"))
        return
    token = token_match.group(1)

    sub_info = await marzban_api.get_subscription_info(token)
    if not sub_info:
        await message.answer(t(lang, "add_subscription_fetch_failed"))
        return

    marzban_username = sub_info.get('username')
    if not marzban_username:
        await message.answer(t(lang, "add_subscription_no_username"))
        return

    # Ensure bot user exists in DB (needed for link regardless)
    db_user = await crud.get_user(session, message.chat.id)
    if not db_user:
        db_user = await crud.create_user(
            session,
            message.chat.id,
            message.from_user.username,
            message.from_user.full_name,
            language=lang,
        )

    # Prevent the same user from adding the same subscription twice, but allow
    # other users to add it as well (shared account scenario).
    from sqlalchemy import select

    from app.database.models import Subscription
    dup_check = await session.execute(
        select(Subscription).filter(Subscription.marzban_username == marzban_username)
    )
    existing_sub = dup_check.scalars().first()

    if existing_sub:
        # Link to existing subscription
        await crud.add_subscription_link(session, db_user.id, existing_sub.id)
        await state.clear()
        await message.answer(
            t(lang, "add_subscription_existing_added"),
            reply_markup=get_main_keyboard(message.chat.id, lang=lang),
        )
        return

    # Validate existence on Marzban
    user_info = await marzban_api.get_user_info(marzban_username)
    if not user_info:
        await message.answer(t(lang, "add_subscription_marzban_not_found"))
        return

    plan_name = 'custom'

    # Insert subscription row as pending, then mark active immediately
    new_sub = await crud.create_subscription(
        db=session,
        user_id=db_user.id,
        marzban_username=marzban_username,
        plan=plan_name,
        receipt_message_id=None,
        referrer_id=None,
        renewal_paid=False,
        price=0  # Custom admin-added subscriptions have no price
    )
    await crud.activate_subscription(session, new_sub.id)

    await state.clear()
    await message.answer(
        t(lang, "add_subscription_success"),
        reply_markup=get_main_keyboard(message.chat.id, lang=lang),
    )