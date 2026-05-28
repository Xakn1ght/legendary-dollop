import json

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import settings
from app.core.paths import core_path
from app.database import crud
from app.database.models import Referral, User
from app.shared.admin_access import ADMIN_IDS
from app.utils.bot_i18n import t
from app.utils.logger import bot_logger

from .common import UserManagementStates, _lang_for_tg_user, router
from .user_detail import show_user_details

USER_CATEGORIES_FILE = core_path("user_categories.json")


def _save_user_categories():
    try:
        with open(USER_CATEGORIES_FILE, "w", encoding="utf-8") as f:
            json.dump(settings.USER_CATEGORIES, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("Failed to save user_categories.json:", e)


# FSM for editing user category (global list / free text — shares state name with monolith)
class UserCategoryEditState(StatesGroup):
    waiting_category = State()


@router.callback_query(F.data.startswith("edit_category_"))
async def edit_category_free_text_prompt(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
):
    lang = _lang_for_tg_user(callback.from_user)
    user_id = int(callback.data.split("_")[2])
    result = await session.execute(select(User).filter_by(chat_id=user_id))
    user = result.scalar_one_or_none()
    if not user:
        await callback.answer(t(lang, "user_not_found"), show_alert=True)
        return
    await state.update_data(edit_user_id=user_id)
    await callback.message.edit_text(
        t(lang, "admin_user_category_prompt").format(category=user.category),
        parse_mode="Markdown",
    )
    await state.set_state(UserCategoryEditState.waiting_category)
    await callback.answer()


@router.message(UserCategoryEditState.waiting_category)
async def edit_category_process(
    message: Message, state: FSMContext, session: AsyncSession
):
    lang = _lang_for_tg_user(message.from_user)
    data = await state.get_data()
    user_id = data.get("edit_user_id")
    new_category = message.text.strip()
    result = await session.execute(select(User).filter_by(chat_id=user_id))
    user = result.scalar_one_or_none()
    if not user:
        await message.answer(t(lang, "user_not_found"))
        await state.clear()
        return
    user.category = new_category
    await session.commit()
    await message.answer(
        t(lang, "admin_user_category_updated").format(category=new_category)
    )
    await state.clear()
    # Show updated user details
    class DummyCb:
        from_user = message.from_user
        message = message

    await show_user_details(DummyCb(), user=user, session=session)


# Add admin-only UI to manage user categories
@router.message(F.text.in_(["🏷️ مدیریت دسته‌بندی‌ها", "مدیریت دسته‌بندی"]))
async def manage_categories_menu(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    kb = InlineKeyboardBuilder()
    for cat in settings.USER_CATEGORIES:
        kb.button(text=f"✏️ {cat}", callback_data=f"edit_cat_{cat}")
        kb.button(text=f"🗑️ {cat}", callback_data=f"del_cat_{cat}")
    kb.button(text="➕ افزودن دسته‌بندی", callback_data="add_cat")
    kb.button(text="⬅️ بازگشت", callback_data="back_to_user_management")
    kb.adjust(2)
    await message.answer(
        "🏷️ دسته‌بندی‌های فعلی:\n" + "\n".join(settings.USER_CATEGORIES),
        reply_markup=kb.as_markup(),
    )


@router.callback_query(F.data == "add_cat")
async def add_category_prompt(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("نام دسته‌بندی جدید را وارد کنید:")
    await state.set_state(UserCategoryEditState.waiting_category)
    await state.update_data(add_mode=True)
    await callback.answer()


@router.message(UserCategoryEditState.waiting_category)
async def add_or_edit_category_process(message: Message, state: FSMContext):
    data = await state.get_data()
    new_cat = message.text.strip()
    if data.get("add_mode"):
        if new_cat in settings.USER_CATEGORIES:
            await message.answer("این دسته‌بندی وجود دارد.")
        else:
            settings.USER_CATEGORIES.append(new_cat)
            _save_user_categories()
            await message.answer(f'✅ دسته‌بندی "{new_cat}" اضافه شد.')
        await state.clear()
        return
    # Otherwise, it's an edit
    old_cat = data.get("edit_cat")
    if old_cat and old_cat in settings.USER_CATEGORIES:
        idx = settings.USER_CATEGORIES.index(old_cat)
        settings.USER_CATEGORIES[idx] = new_cat
        _save_user_categories()
        await message.answer(f'✅ دسته‌بندی "{old_cat}" به "{new_cat}" تغییر یافت.')
    else:
        await message.answer("دسته‌بندی یافت نشد.")
    await state.clear()


@router.callback_query(F.data.startswith("edit_cat_"))
async def edit_category_name_prompt(callback: CallbackQuery, state: FSMContext):
    cat = callback.data[len("edit_cat_") :]
    await callback.message.edit_text(f'نام جدید برای دسته‌بندی "{cat}" را وارد کنید:')
    await state.set_state(UserCategoryEditState.waiting_category)
    await state.update_data(edit_cat=cat, add_mode=False)
    await callback.answer()


@router.callback_query(F.data.startswith("del_cat_"))
async def delete_category(callback: CallbackQuery):
    cat = callback.data[len("del_cat_") :]
    if cat in settings.USER_CATEGORIES:
        settings.USER_CATEGORIES.remove(cat)
        _save_user_categories()
        await callback.answer(f'دسته‌بندی "{cat}" حذف شد.', show_alert=True)
    else:
        await callback.answer("دسته‌بندی یافت نشد.", show_alert=True)
    # Refresh menu
    class DummyMsg:
        from_user = callback.from_user

        async def answer(self, text, reply_markup=None):
            await callback.message.edit_text(text, reply_markup=reply_markup)

    await manage_categories_menu(DummyMsg())


# Update category assignment to use dropdown/select (same callback prefix as free-text handler)
@router.callback_query(F.data.startswith("edit_category_"))
async def edit_category_select_prompt(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
):
    user_id = int(callback.data.split("_")[2])
    result = await session.execute(select(User).filter_by(chat_id=user_id))
    user = result.scalar_one_or_none()
    if not user:
        await callback.answer(
            t(_lang_for_tg_user(callback.from_user), "user_not_found"),
            show_alert=True,
        )
        return
    kb = InlineKeyboardBuilder()
    for cat in settings.USER_CATEGORIES:
        kb.button(text=cat, callback_data=f"set_user_cat_{user_id}_{cat}")
    kb.button(text="❌ لغو", callback_data=f"user_details_{user_id}")
    kb.adjust(2)
    await callback.message.edit_text(
        f"دسته‌بندی فعلی: `{user.category}`\nیک دسته‌بندی جدید انتخاب کنید:",
        reply_markup=kb.as_markup(),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("set_user_cat_"))
async def set_user_category(callback: CallbackQuery, session: AsyncSession):
    payload = callback.data.removeprefix("set_user_cat_")
    user_id_str, sep, cat = payload.partition("_")
    if not sep:
        await callback.answer("❌ داده نامعتبر.", show_alert=True)
        return
    user_id = int(user_id_str)
    result = await session.execute(select(User).filter_by(chat_id=user_id))
    user = result.scalar_one_or_none()
    if not user:
        await callback.answer(
            t(_lang_for_tg_user(callback.from_user), "user_not_found"),
            show_alert=True,
        )
        return
    user.category = cat
    await session.commit()
    await callback.answer(f'دسته‌بندی کاربر به "{cat}" تغییر یافت.', show_alert=True)
    await show_user_details(callback, user=user, session=session)


@router.callback_query(F.data.startswith("add_referrer_"))
async def add_referrer_prompt(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
):
    """Prompt admin to enter referrer chat_id or username"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(
            t(_lang_for_tg_user(callback.from_user), "not_authorized"),
            show_alert=True,
        )
        return

    user_id = int(callback.data.split("_")[2])
    result = await session.execute(select(User).filter_by(chat_id=user_id))
    user = result.scalar_one_or_none()

    if not user:
        await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
        return

    # Check if user already has a referrer
    existing_referral = await session.scalar(
        select(Referral).filter(Referral.referee_id == user.id)
    )
    if existing_referral:
        await callback.answer("❌ این کاربر قبلاً معرف دارد.", show_alert=True)
        return

    # Store user_id in state
    await state.update_data(target_user_id=user_id)
    await state.set_state(UserManagementStates.waiting_referrer_id)

    await callback.message.edit_text(
        f"➕ **افزودن معرف برای {user.full_name or user.username or user.chat_id}**\n\n"
        "📝 لطفاً شناسه تلگرام یا نام کاربری معرف را ارسال کنید:\n\n"
        "💡 مثال:\n"
        "• `123456789` (شناسه تلگرام)\n"
        "• `@username` (نام کاربری)",
        parse_mode="Markdown",
    )
    await callback.answer()


@router.message(UserManagementStates.waiting_referrer_id)
async def process_add_referrer(
    message: Message, state: FSMContext, session: AsyncSession
):
    """Process adding referrer for OG user"""
    if message.from_user.id not in ADMIN_IDS:
        await state.clear()
        return

    data = await state.get_data()
    target_user_id = data.get("target_user_id")

    if not target_user_id:
        await message.answer("❌ خطا: اطلاعات کاربر یافت نشد.")
        await state.clear()
        return

    # Get target user
    target_user = await session.scalar(select(User).filter_by(chat_id=target_user_id))

    if not target_user:
        await message.answer("❌ کاربر یافت نشد.")
        await state.clear()
        return

    # Check if already has referrer
    existing_referral = await session.scalar(
        select(Referral).filter(Referral.referee_id == target_user.id)
    )
    if existing_referral:
        await message.answer("❌ این کاربر قبلاً معرف دارد.")
        await state.clear()
        return

    # Parse referrer input
    referrer_input = message.text.strip()
    referrer = None

    # Try to find by chat_id
    if referrer_input.isdigit():
        referrer = await session.scalar(
            select(User).filter_by(chat_id=int(referrer_input))
        )

    # Try to find by username
    if not referrer and referrer_input.startswith("@"):
        username = referrer_input[1:].strip()
        referrer = await session.scalar(select(User).filter_by(username=username))
    elif not referrer:
        # Try without @
        referrer = await session.scalar(select(User).filter_by(username=referrer_input))

    if not referrer:
        await message.answer(
            "❌ معرف یافت نشد.\n\n"
            "لطفاً شناسه تلگرام یا نام کاربری معتبر ارسال کنید."
        )
        return

    if referrer.id == target_user.id:
        await message.answer("❌ کاربر نمی‌تواند معرف خودش باشد.")
        return

    # Create referral
    try:
        await crud.create_referral(
            session, referrer_id=referrer.id, referee_id=target_user.id
        )

        # Rewards policy: do not grant XP/loyalty/challenge rewards for referrals.
        # Referral vouchers (if any) are granted only after a real purchase.

        referrer_name = referrer.full_name or referrer.username or f"ID:{referrer.chat_id}"
        await message.answer(
            f"✅ معرف با موفقیت افزوده شد!\n\n"
            f"👤 کاربر: {target_user.full_name or target_user.username or target_user.chat_id}\n"
            f"👤 معرف: {referrer_name}\n\n"
            f"🎁 پاداش فوری ندارد (بن بعد از خرید فعال می‌شود).",
            reply_markup=InlineKeyboardBuilder()
            .button(
                text="🔙 بازگشت به اطلاعات کاربر",
                callback_data=f"user_details_{target_user_id}",
            )
            .as_markup(),
        )

        await state.clear()

    except Exception as e:
        bot_logger.error(f"Error adding referrer: {e}", exc_info=e)
        await message.answer("❌ خطا در افزودن معرف. لطفاً دوباره تلاش کنید.")
