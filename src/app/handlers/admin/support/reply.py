from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import crud
from app.database.crud import get_user_by_id
from app.handlers.admin.common import ADMIN_IDS
from app.utils.bot_i18n import t

from .common import AdminSupportStates, _lang_for_tg_user, router


@router.callback_query(F.data.startswith("admin_sup_reply_"))
async def admin_reply_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(
            t(_lang_for_tg_user(callback.from_user), "not_authorized"),
            show_alert=True,
        )
        return
    ticket_id = int(callback.data.removeprefix("admin_sup_reply_"))
    await state.set_state(AdminSupportStates.replying)
    await state.update_data(ticket_id=ticket_id)
    kb = InlineKeyboardBuilder()
    kb.button(text="📨 ارسال و باز", callback_data="admin_sup_mode_open")
    kb.button(text="⏳ ارسال و انتظار", callback_data="admin_sup_mode_wait")
    kb.button(text="✅ ارسال و بستن", callback_data="admin_sup_mode_close")
    kb.adjust(2)
    await callback.message.answer(
        "پاسخ خود را ارسال کنید (متن). حالت ارسال را انتخاب کنید:",
        reply_markup=kb.as_markup(),
    )
    await callback.answer()


@router.message(AdminSupportStates.replying, F.text)
async def admin_reply_text(message: Message, state: FSMContext, session: AsyncSession):
    if message.from_user.id not in ADMIN_IDS:
        return
    data = await state.get_data()
    ticket_id = data.get("ticket_id")

    if not ticket_id:
        lang = _lang_for_tg_user(message.from_user)
        await message.answer(t(lang, "admin_support_ticket_id_missing"))
        await state.clear()
        return

    tkt = await crud.get_ticket_by_id(session, ticket_id)
    if not tkt:
        lang = _lang_for_tg_user(message.from_user)
        await message.answer(t(lang, "admin_support_ticket_not_found"))
        await state.clear()
        return

    await crud.add_ticket_message(
        session,
        ticket_id,
        sender="admin",
        content_type="text",
        text=message.text,
    )

    user = await get_user_by_id(session, tkt.user_id)
    if not user:
        lang = _lang_for_tg_user(message.from_user)
        await message.answer(t(lang, "admin_support_ticket_user_not_found"))
        await state.clear()
        return

    user_lang = getattr(user, "language", None)
    outbound = t(user_lang, "support_admin_reply").format(
        ticket_id=tkt.id, text=message.text
    )
    try:
        await message.bot.send_message(user.chat_id, outbound)
    except Exception:
        try:
            await message.bot.send_message(user.chat_id, outbound)
        except Exception as e:
            lang = _lang_for_tg_user(message.from_user)
            await message.answer(
                t(lang, "admin_support_send_user_failed").format(err=str(e)[:100])
            )

    await state.clear()
    lang = _lang_for_tg_user(message.from_user)
    await message.answer(t(lang, "admin_support_sent"))


@router.callback_query(
    F.data.in_(["admin_sup_mode_open", "admin_sup_mode_wait", "admin_sup_mode_close"])
)
async def admin_reply_mode(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(
            t(_lang_for_tg_user(callback.from_user), "not_authorized"),
            show_alert=True,
        )
        return
    mode = callback.data
    data = await state.get_data()
    ticket_id = data.get("ticket_id")
    if not ticket_id:
        await callback.answer()
        return
    if mode == "admin_sup_mode_wait":
        await crud.update_ticket_status(session, ticket_id, "awaiting_user")
    elif mode == "admin_sup_mode_close":
        await crud.update_ticket_status(session, ticket_id, "closed")
    await callback.answer(
        t(_lang_for_tg_user(callback.from_user), "admin_support_mode_saved")
    )
