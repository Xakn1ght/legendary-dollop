from __future__ import annotations

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import crud

from .common import SupportStates, router, safe_edit_message


@router.callback_query(F.data.startswith("support_fb_yes_"))
async def support_feedback_yes(callback: CallbackQuery, session: AsyncSession):
    ticket_id = int(callback.data.removeprefix("support_fb_yes_"))
    await crud.save_ticket_feedback(session, ticket_id, score=1, text=None)
    await safe_edit_message(callback, "سپاس از بازخورد شما! خوشحالیم مشکل حل شد.")
    await callback.answer()


@router.callback_query(F.data.startswith("support_fb_no_"))
async def support_feedback_no(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    ticket_id = int(callback.data.removeprefix("support_fb_no_"))
    await crud.save_ticket_feedback(session, ticket_id, score=-1, text=None)
    await state.update_data(fb_ticket_id=ticket_id)
    await safe_edit_message(callback, "لطفاً خیلی کوتاه بفرمایید چه مشکلی باقی مانده:")
    await state.set_state(SupportStates.edit_description)
    await callback.answer()


@router.callback_query(F.data == "support_my_tickets")
async def list_my_tickets(callback: CallbackQuery, session: AsyncSession):
    from app.database.crud import get_user
    user = await get_user(session, callback.from_user.id)
    if not user:
        await callback.answer("ابتدا /start را ارسال کنید.", show_alert=True)
        return
    tickets = await crud.list_tickets_by_user(session, user.id, limit=20)
    if not tickets:
        await safe_edit_message(callback, "هیچ تیکتی ندارید.")
        await callback.answer()
        return
    kb = InlineKeyboardBuilder()
    for t in tickets:
        status_chip = {
            'pending': '🟡 در صف',
            'open': '🟢 در حال بررسی',
            'awaiting_user': '🟠 منتظر شما',
            'closed': '⚪️ بسته'
        }.get(t.status, t.status)
        kb.button(text=f"#{t.id} | {t.category} | {status_chip}", callback_data=f"support_ticket_{t.id}")
    kb.adjust(1)
    kb.button(text="بازگشت🔙", callback_data="support_back_main")
    await safe_edit_message(callback, "تیکت‌های شما:", kb.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("support_ticket_"))
async def view_ticket(callback: CallbackQuery, session: AsyncSession):
    ticket_id = int(callback.data.removeprefix("support_ticket_"))
    ticket = await crud.get_ticket_by_id(session, ticket_id)
    if not ticket:
        await callback.answer("تیکت یافت نشد.", show_alert=True)
        return
    messages = await crud.get_ticket_messages(session, ticket_id, limit=20)
    status_chip = {
        'pending': '🟡 در صف',
        'open': '🟢 در حال بررسی',
        'awaiting_user': '🟠 منتظر شما',
        'closed': '⚪️ بسته'
    }.get(ticket.status, ticket.status)
    header = f"تیکت #{ticket.id} | {ticket.category} | {status_chip}\n"
    if ticket.category == 'connection':
        header += f"OS: {ticket.os or '-'} | ISP: {ticket.isp or '-'}\n"
    body_lines = []
    for m in messages:
        who = '👤' if m.sender == 'user' else ('🛡' if m.sender == 'admin' else '⚙️')
        if m.content_type == 'text' and m.text:
            body_lines.append(f"{who} {m.text}")
        elif m.content_type == 'photo':
            body_lines.append(f"{who} [photo]")
    text = header + "\n".join(body_lines[-10:])  # compact
    kb = InlineKeyboardBuilder()
    if ticket.status != 'closed' and ticket.allow_more_from_user:
        kb.button(text="➕ افزودن متن", callback_data=f"support_addmsg_{ticket.id}")
    if ticket.status != 'closed':
        kb.button(text="🔒 بستن تیکت", callback_data=f"support_close_{ticket.id}")
    else:
        kb.button(text="🔓 بازگشایی", callback_data=f"support_reopen_{ticket.id}")
    kb.button(text="بازگشت🔙", callback_data="support_my_tickets")
    kb.adjust(2)
    await safe_edit_message(callback, text, kb.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("support_reopen_"))
async def user_reopen_ticket(callback: CallbackQuery, session: AsyncSession):
    ticket_id = int(callback.data.removeprefix("support_reopen_"))
    ticket = await crud.get_ticket_by_id(session, ticket_id)
    if not ticket:
        await callback.answer("تیکت یافت نشد.", show_alert=True)
        return
    if ticket.status != 'closed':
        await callback.answer()
        return
    # Reopen to pending and allow user messages
    await crud.update_ticket_status(session, ticket_id, 'pending')
    await crud.set_ticket_allow_more(session, ticket_id, True)
    # Notify admins optionally later
    await safe_edit_message(callback, f"تیکت #{ticket.id} باز شد و به صف بازگشت.")
    await callback.answer("باز شد.")


@router.callback_query(F.data.startswith("support_toggle_notify_"))
async def user_toggle_notify(callback: CallbackQuery, session: AsyncSession):
    ticket_id = int(callback.data.removeprefix("support_toggle_notify_"))
    t = await crud.get_ticket_by_id(session, ticket_id)
    if not t:
        await callback.answer()
        return
    new_val = not bool(t.notify_on_reply)
    await crud.set_ticket_notify_on_reply(session, ticket_id, new_val)
    label = "روشن" if new_val else "خاموش"
    await callback.answer(f"اطلاع‌رسانی پاسخ: {label}", show_alert=True)


@router.callback_query(F.data.startswith("support_addmsg_"))
async def start_add_message(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    ticket_id = int(callback.data.removeprefix("support_addmsg_"))
    ticket = await crud.get_ticket_by_id(session, ticket_id)
    if not ticket or ticket.status == 'closed' or not ticket.allow_more_from_user:
        await callback.answer("امکان افزودن پیام وجود ندارد.", show_alert=True)
        return
    await state.set_state(SupportStates.adding_message)
    await state.update_data(add_ticket_id=ticket_id)
    await callback.message.answer("لطفاً پیام متنی خود را ارسال کنید.")
    await callback.answer()


@router.message(SupportStates.adding_message, F.text)
async def add_message_text(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    ticket_id = data.get('add_ticket_id')
    ticket = await crud.get_ticket_by_id(session, ticket_id)
    if not ticket or ticket.status == 'closed' or not ticket.allow_more_from_user:
        await state.clear()
        await message.answer("امکان افزودن پیام وجود ندارد.")
        return
    await crud.add_ticket_message(session, ticket_id, sender='user', content_type='text', text=message.text)
    await state.clear()
    await message.answer("پیام شما افزوده شد.")
    from app.database.crud import get_user
    from app.services.support_assist import maybe_answer_ticket
    user = await get_user(session, message.from_user.id)
    if user:
        await maybe_answer_ticket(session, ticket, user, message.text, bot=message.bot)


@router.callback_query(F.data.startswith("support_close_"))
async def user_close_ticket(callback: CallbackQuery, session: AsyncSession):
    ticket_id = int(callback.data.removeprefix("support_close_"))
    ticket = await crud.update_ticket_status(session, ticket_id, 'closed')
    if not ticket:
        await callback.answer("خطا در بستن تیکت.", show_alert=True)
        return
    await safe_edit_message(callback, f"تیکت #{ticket.id} بسته شد.")
    await callback.answer("بسته شد.")
