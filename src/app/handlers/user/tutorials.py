from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup

from app.core.settings import TUTORIAL_CHANNEL_ID
from app.database import crud
from app.keyboards.reply import get_main_keyboard
from app.utils.bot_i18n import normalize_lang, set_cached_lang, t, text_matches

router = Router()

class TutorialState(StatesGroup):
    platform = State()

def _tutorial_keyboard(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t(lang, "btn_android")), KeyboardButton(text=t(lang, "btn_ios")), KeyboardButton(text=t(lang, "btn_windows"))],
            [KeyboardButton(text=t(lang, "btn_back"))],
        ],
        resize_keyboard=True,
    )


@router.message(text_matches("btn_guide"))
async def tutorial_start(message: Message, state: FSMContext, session):
    await state.set_state(TutorialState.platform)
    user = await crud.get_user(session, message.chat.id)
    lang = normalize_lang(getattr(user, "language", None)) if user else normalize_lang(getattr(message.from_user, "language_code", None))
    set_cached_lang(message.chat.id, lang)
    await message.answer(
        t(lang, "tutorial_choose_device"),
        reply_markup=_tutorial_keyboard(lang),
    )

@router.message(TutorialState.platform, text_matches("btn_android"))
async def tutorial_android(message: Message, bot: Bot, session):
    user = await crud.get_user(session, message.chat.id)
    lang = normalize_lang(getattr(user, "language", None)) if user else normalize_lang(getattr(message.from_user, "language_code", None))
    try:
        # These are message IDs from your channel.
        # You should update them to match your actual tutorial messages.
        await bot.forward_message(chat_id=message.chat_id, from_chat_id=TUTORIAL_CHANNEL_ID, message_id=2)
        await bot.forward_message(chat_id=message.chat_id, from_chat_id=TUTORIAL_CHANNEL_ID, message_id=3)
    except Exception as e:
        await message.answer(t(lang, "tutorial_send_error"))
        print(f"Error forwarding Android tutorial: {e}")

@router.message(TutorialState.platform, text_matches("btn_ios"))
async def tutorial_ios(message: Message, bot: Bot, session):
    user = await crud.get_user(session, message.chat.id)
    lang = normalize_lang(getattr(user, "language", None)) if user else normalize_lang(getattr(message.from_user, "language_code", None))
    try:
        await bot.forward_message(chat_id=message.chat_id, from_chat_id=TUTORIAL_CHANNEL_ID, message_id=6)
        await bot.forward_message(chat_id=message.chat_id, from_chat_id=TUTORIAL_CHANNEL_ID, message_id=7)
        await bot.forward_message(chat_id=message.chat_id, from_chat_id=TUTORIAL_CHANNEL_ID, message_id=8)
    except Exception as e:
        await message.answer(t(lang, "tutorial_send_error"))
        print(f"Error forwarding iOS tutorial: {e}")

@router.message(TutorialState.platform, text_matches("btn_windows"))
async def tutorial_windows(message: Message, bot: Bot, session):
    user = await crud.get_user(session, message.chat.id)
    lang = normalize_lang(getattr(user, "language", None)) if user else normalize_lang(getattr(message.from_user, "language_code", None))
    try:
        await bot.forward_message(chat_id=message.chat_id, from_chat_id=TUTORIAL_CHANNEL_ID, message_id=4)
        await bot.forward_message(chat_id=message.chat_id, from_chat_id=TUTORIAL_CHANNEL_ID, message_id=5)
    except Exception as e:
        await message.answer(t(lang, "tutorial_send_error"))
        print(f"Error forwarding Windows tutorial: {e}")

@router.message(TutorialState.platform, text_matches("btn_back"))
async def tutorial_back(message: Message, state: FSMContext, session):
    await state.clear()
    user = await crud.get_user(session, message.chat.id)
    lang = normalize_lang(getattr(user, "language", None)) if user else normalize_lang(getattr(message.from_user, "language_code", None))
    set_cached_lang(message.chat.id, lang)
    await message.answer(
        ('به منوی اصلی بازگشتید.' if lang == "fa" else "Back to main menu."),
        reply_markup=get_main_keyboard(message.chat.id, lang=lang),
    )

@router.message(TutorialState.platform)
async def invalid_tutorial_option(message: Message, session):
    user = await crud.get_user(session, message.chat.id)
    lang = normalize_lang(getattr(user, "language", None)) if user else normalize_lang(getattr(message.from_user, "language_code", None))
    await message.answer(t(lang, "tutorial_invalid"), reply_markup=_tutorial_keyboard(lang))