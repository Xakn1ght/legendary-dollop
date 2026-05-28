from aiogram import F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import SUPPORT_CATEGORIES
from app.database import crud
from app.database.crud import get_user_by_id
from app.database.models import Subscription, Ticket
from app.handlers.admin.common import ADMIN_IDS
from app.utils.bot_i18n import t

from .common import _lang_for_tg_user, router, safe_edit_message


def _ticket_actions_kb(t: Ticket) -> InlineKeyboardBuilder:
    kb = InlineKeyboardBuilder()
    if t.assigned_admin_id:
        kb.button(text="🔓 عدم اختصاص", callback_data=f"admin_sup_unassign_{t.id}")
    else:
        kb.button(text="📌 اختصاص به من", callback_data=f"admin_sup_claim_{t.id}")
    kb.button(text="📜 نمایش پیام‌ها", callback_data=f"admin_sup_show_msgs_{t.id}")
    kb.button(text="✉️ پاسخ", callback_data=f"admin_sup_reply_{t.id}")
    kb.button(text="📄 پاسخ آماده", callback_data=f"admin_sup_canned_reply_{t.id}")

    if t.is_private_chat and t.chat_invitation_accepted and not t.chat_ended_at:
        kb.button(text="💬 چت فعال", callback_data=f"admin_sup_active_chat_{t.id}")
    elif (
        t.is_private_chat
        and t.chat_invitation_sent
        and not t.chat_invitation_accepted
        and not t.chat_invitation_expired
    ):
        kb.button(
            text="💬 دعوت ارسال شده",
            callback_data=f"admin_sup_pending_chat_{t.id}",
        )
    else:
        kb.button(
            text="💬 شروع چت خصوصی", callback_data=f"admin_sup_start_chat_{t.id}"
        )

    kb.button(text="ℹ️ درخواست اطلاعات بیشتر", callback_data=f"admin_sup_more_{t.id}")
    kb.button(text="🗂 تغییر دسته", callback_data=f"admin_sup_chcat_{t.id}")
    kb.button(text="⚖️ اولویت", callback_data=f"admin_sup_chprio_{t.id}")
    if t.status == "closed":
        kb.button(text="🔓 بازگشایی", callback_data=f"admin_sup_reopen_{t.id}")
    else:
        kb.button(text="🔒 بستن", callback_data=f"admin_sup_close_{t.id}")
    if t.subscription_id:
        kb.button(text="🔎 نمایش سرویس", callback_data=f"admin_sup_view_sub_{t.id}")
        kb.button(
            text="♻️ بروزرسانی وضعیت", callback_data=f"admin_sup_refresh_sub_{t.id}"
        )
        kb.button(text="🧾 تمدید", callback_data=f"admin_sup_renew_{t.id}")
        kb.button(text="📅 خرید روز", callback_data=f"admin_sup_buydays_{t.id}")
    kb.adjust(2)
    kb.button(text="⬅️ بازگشت", callback_data="admin_sup_back_main")
    return kb


async def render_ticket_view(
    callback: CallbackQuery, session: AsyncSession, ticket_id: int
):
    tkt = await crud.get_ticket_by_id(session, ticket_id)
    msgs = await crud.get_ticket_messages(session, ticket_id, limit=30)
    header = f"تیکت #{tkt.id} | {tkt.category} | {tkt.status}\n"
    if tkt.subscription_id:
        sub = await session.get(Subscription, tkt.subscription_id)
        if sub:
            header += f"سرویس مرتبط: {sub.marzban_username} (#{sub.id})\n"
    header += f"Assigned: {tkt.assigned_admin_id or '-'} | Priority: {tkt.priority}\n"
    if tkt.category == "connection":
        header += f"OS: {tkt.os or '-'} | ISP: {tkt.isp or '-'}\n"
    lines = []
    for m in msgs[-12:]:
        who = "👤" if m.sender == "user" else ("🛡" if m.sender == "admin" else "⚙️")
        if m.content_type == "text" and m.text:
            lines.append(f"{who} {m.text}")
        elif m.content_type == "photo":
            lines.append(f"{who} [photo]")
    kb = _ticket_actions_kb(tkt)
    await safe_edit_message(callback, header + "\n".join(lines), kb.as_markup())


@router.callback_query(F.data.startswith("admin_sup_open_"))
async def admin_open_ticket(callback: CallbackQuery, session: AsyncSession):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(
            t(_lang_for_tg_user(callback.from_user), "not_authorized"),
            show_alert=True,
        )
        return
    ticket_id = int(callback.data.removeprefix("admin_sup_open_"))
    await render_ticket_view(callback, session, ticket_id)
    await callback.answer()


@router.callback_query(F.data.startswith("admin_sup_view_sub_"))
async def admin_view_subscription(callback: CallbackQuery, session: AsyncSession):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(
            t(_lang_for_tg_user(callback.from_user), "not_authorized"),
            show_alert=True,
        )
        return
    ticket_id = int(callback.data.removeprefix("admin_sup_view_sub_"))
    tkt = await crud.get_ticket_by_id(session, ticket_id)
    if not tkt or not tkt.subscription_id:
        await callback.answer()
        return
    sub = await session.get(Subscription, tkt.subscription_id)
    if not sub:
        await callback.answer()
        return
    try:
        from app.handlers.user.my_services import build_subscription_detail
        from app.services.marzban import marzban_api

        ui = await marzban_api.get_fast_user_info(
            sub.marzban_username, getattr(sub, "sub_token", None)
        )
        text, kb = build_subscription_detail(sub, ui or {})
        await safe_edit_message(callback, "[نمایش سرویس مرتبط]\n" + text, kb.as_markup())
    except Exception:
        await safe_edit_message(
            callback, f"سرویس: {sub.marzban_username} (#{sub.id})"
        )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_sup_refresh_sub_"))
async def admin_refresh_subscription(callback: CallbackQuery, session: AsyncSession):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(
            t(_lang_for_tg_user(callback.from_user), "not_authorized"),
            show_alert=True,
        )
        return
    ticket_id = int(callback.data.removeprefix("admin_sup_refresh_sub_"))
    tkt = await crud.get_ticket_by_id(session, ticket_id)
    if not tkt or not tkt.subscription_id:
        await callback.answer()
        return
    sub = await session.get(Subscription, tkt.subscription_id)
    if not sub:
        await callback.answer()
        return
    from app.services.marzban import marzban_api

    ui = await marzban_api.get_fast_user_info(
        sub.marzban_username, getattr(sub, "sub_token", None)
    )
    status = ui.get("status") if ui else "-"
    await callback.answer(
        f"به‌روز شد: {sub.marzban_username} | {status}", show_alert=True
    )


@router.callback_query(F.data.startswith("admin_sup_renew_"))
async def admin_renew_subscription(callback: CallbackQuery, session: AsyncSession):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(
            t(_lang_for_tg_user(callback.from_user), "not_authorized"),
            show_alert=True,
        )
        return
    ticket_id = int(callback.data.removeprefix("admin_sup_renew_"))
    tkt = await crud.get_ticket_by_id(session, ticket_id)
    if not tkt or not tkt.subscription_id:
        await callback.answer()
        return
    sub = await session.get(Subscription, tkt.subscription_id)
    if not sub:
        await callback.answer()
        return
    try:
        await callback.bot.send_message(
            callback.message.chat.id,
            f"برای تمدید {sub.marzban_username} از منوی شارژ/تمدید استفاده کنید.",
        )
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("admin_sup_buydays_"))
async def admin_buydays_subscription(callback: CallbackQuery, session: AsyncSession):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(
            t(_lang_for_tg_user(callback.from_user), "not_authorized"),
            show_alert=True,
        )
        return
    ticket_id = int(callback.data.removeprefix("admin_sup_buydays_"))
    tkt = await crud.get_ticket_by_id(session, ticket_id)
    if not tkt or not tkt.subscription_id:
        await callback.answer()
        return
    sub = await session.get(Subscription, tkt.subscription_id)
    if not sub:
        await callback.answer()
        return
    try:
        await callback.bot.send_message(
            callback.message.chat.id,
            f"برای خرید روز بیشتر {sub.marzban_username} از منوی شارژ/خرید روز استفاده کنید.",
        )
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("admin_sup_claim_"))
async def admin_claim(callback: CallbackQuery, session: AsyncSession):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(
            t(_lang_for_tg_user(callback.from_user), "not_authorized"),
            show_alert=True,
        )
        return
    ticket_id = int(callback.data.removeprefix("admin_sup_claim_"))
    await crud.assign_ticket(session, ticket_id, admin_user_id=callback.from_user.id)
    await render_ticket_view(callback, session, ticket_id)
    tkt = await crud.get_ticket_by_id(session, ticket_id)
    user = await get_user_by_id(session, tkt.user_id)
    try:
        await callback.bot.send_message(
            user.chat_id, f"تیکت #{tkt.id} شما در حال بررسی است."
        )
    except Exception:
        pass
    await callback.answer("اختصاص یافت.")


@router.callback_query(F.data.startswith("admin_sup_unassign_"))
async def admin_unassign(callback: CallbackQuery, session: AsyncSession):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(
            t(_lang_for_tg_user(callback.from_user), "not_authorized"),
            show_alert=True,
        )
        return
    ticket_id = int(callback.data.removeprefix("admin_sup_unassign_"))
    await crud.assign_ticket(session, ticket_id, admin_user_id=None)
    await render_ticket_view(callback, session, ticket_id)
    await callback.answer("آزاد شد.")


@router.callback_query(F.data.startswith("admin_sup_close_"))
async def admin_close(callback: CallbackQuery, session: AsyncSession):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(
            t(_lang_for_tg_user(callback.from_user), "not_authorized"),
            show_alert=True,
        )
        return
    ticket_id = int(callback.data.removeprefix("admin_sup_close_"))
    await crud.update_ticket_status(session, ticket_id, "closed")
    tkt = await crud.get_ticket_by_id(session, ticket_id)
    user = await get_user_by_id(session, tkt.user_id)
    try:
        kb = InlineKeyboardBuilder()
        kb.button(text="👍 بله", callback_data=f"support_fb_yes_{tkt.id}")
        kb.button(text="👎 خیر", callback_data=f"support_fb_no_{tkt.id}")
        kb.adjust(2)
        await callback.bot.send_message(
            user.chat_id,
            f"تیکت #{tkt.id} بسته شد. آیا مشکل شما حل شد؟",
            reply_markup=kb.as_markup(),
        )
    except Exception:
        pass
    await render_ticket_view(callback, session, ticket_id)
    await callback.answer("بسته شد.")


@router.callback_query(F.data.startswith("admin_sup_reopen_"))
async def admin_reopen(callback: CallbackQuery, session: AsyncSession):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(
            t(_lang_for_tg_user(callback.from_user), "not_authorized"),
            show_alert=True,
        )
        return
    ticket_id = int(callback.data.removeprefix("admin_sup_reopen_"))
    await crud.update_ticket_status(session, ticket_id, "open")
    await render_ticket_view(callback, session, ticket_id)
    await callback.answer("باز شد.")


@router.callback_query(F.data.startswith("admin_sup_more_"))
async def admin_request_more(callback: CallbackQuery, session: AsyncSession):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(
            t(_lang_for_tg_user(callback.from_user), "not_authorized"),
            show_alert=True,
        )
        return
    ticket_id = int(callback.data.removeprefix("admin_sup_more_"))
    await crud.set_ticket_allow_more(session, ticket_id, True)
    tkt = await crud.get_ticket_by_id(session, ticket_id)
    user = await get_user_by_id(session, tkt.user_id)
    try:
        await callback.bot.send_message(
            user.chat_id, f"برای تیکت #{tkt.id} لطفاً اطلاعات بیشتری ارسال کنید."
        )
    except Exception:
        pass
    await render_ticket_view(callback, session, ticket_id)
    await callback.answer("درخواست شد.")


@router.callback_query(F.data.startswith("admin_sup_show_msgs_"))
async def admin_show_messages(callback: CallbackQuery, session: AsyncSession):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(
            t(_lang_for_tg_user(callback.from_user), "not_authorized"),
            show_alert=True,
        )
        return
    ticket_id = int(callback.data.removeprefix("admin_sup_show_msgs_"))
    msgs = await crud.get_ticket_messages(session, ticket_id, limit=10_000)
    if not msgs:
        await callback.answer("هیچ پیامی وجود ندارد.", show_alert=True)
        return
    await callback.message.answer(
        f"ارسال پیام‌های تیکت #{ticket_id} (تعداد: {len(msgs)})"
    )
    for m in msgs:
        prefix = (
            "👤 کاربر:"
            if m.sender == "user"
            else ("🛡 ادمین:" if m.sender == "admin" else "⚙️ سیستم:")
        )
        if m.content_type == "photo" and m.file_id:
            try:
                if m.telegram_message_id:
                    tkt = await crud.get_ticket_by_id(session, ticket_id)
                    user = await get_user_by_id(session, tkt.user_id)
                    await callback.bot.forward_message(
                        chat_id=callback.message.chat.id,
                        from_chat_id=user.chat_id,
                        message_id=m.telegram_message_id,
                    )
                else:
                    await callback.bot.send_photo(
                        chat_id=callback.message.chat.id,
                        photo=m.file_id,
                        caption=prefix + (f"\n{m.text}" if m.text else ""),
                    )
            except Exception:
                await callback.bot.send_message(
                    chat_id=callback.message.chat.id,
                    text=f"{prefix} [photo] {m.file_id}",
                )
        elif m.content_type == "text" and m.text:
            try:
                if m.telegram_message_id:
                    tkt = await crud.get_ticket_by_id(session, ticket_id)
                    user = await get_user_by_id(session, tkt.user_id)
                    await callback.bot.forward_message(
                        chat_id=callback.message.chat.id,
                        from_chat_id=user.chat_id,
                        message_id=m.telegram_message_id,
                    )
                else:
                    await callback.bot.send_message(
                        chat_id=callback.message.chat.id,
                        text=f"{prefix} {m.text}",
                    )
            except Exception:
                await callback.bot.send_message(
                    chat_id=callback.message.chat.id,
                    text=f"{prefix} {m.text}",
                )
        else:
            await callback.bot.send_message(
                chat_id=callback.message.chat.id,
                text=f"{prefix} [message]",
            )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_sup_chcat_"))
async def admin_change_category(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(
            t(_lang_for_tg_user(callback.from_user), "not_authorized"),
            show_alert=True,
        )
        return
    ticket_id = int(callback.data.removeprefix("admin_sup_chcat_"))
    kb = InlineKeyboardBuilder()
    for c in SUPPORT_CATEGORIES:
        kb.button(
            text=c["label"],
            callback_data=f"admin_sup_apply_cat_{ticket_id}_{c['key']}",
        )
    kb.adjust(2)
    kb.button(text="⬅️ بازگشت", callback_data=f"admin_sup_open_{ticket_id}")
    await safe_edit_message(callback, "انتخاب دسته جدید:", kb.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("admin_sup_apply_cat_"))
async def admin_apply_category(callback: CallbackQuery, session: AsyncSession):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(
            t(_lang_for_tg_user(callback.from_user), "not_authorized"),
            show_alert=True,
        )
        return
    parts = callback.data.split("_")
    ticket_id = int(parts[4])
    new_cat = parts[5]
    await crud.change_ticket_category(session, ticket_id, new_cat)
    await render_ticket_view(callback, session, ticket_id)
    await callback.answer("بروزرسانی شد.")


@router.callback_query(F.data.startswith("admin_sup_chprio_"))
async def admin_change_priority(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(
            t(_lang_for_tg_user(callback.from_user), "not_authorized"),
            show_alert=True,
        )
        return
    ticket_id = int(callback.data.removeprefix("admin_sup_chprio_"))
    kb = InlineKeyboardBuilder()
    for p in ["low", "normal", "high"]:
        kb.button(
            text=p, callback_data=f"admin_sup_apply_prio_{ticket_id}_{p}"
        )
    kb.adjust(3)
    kb.button(text="⬅️ بازگشت", callback_data=f"admin_sup_open_{ticket_id}")
    await safe_edit_message(callback, "انتخاب اولویت:", kb.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("admin_sup_apply_prio_"))
async def admin_apply_priority(callback: CallbackQuery, session: AsyncSession):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(
            t(_lang_for_tg_user(callback.from_user), "not_authorized"),
            show_alert=True,
        )
        return
    parts = callback.data.split("_")
    ticket_id = int(parts[4])
    prio = parts[5]
    await crud.change_ticket_priority(session, ticket_id, prio)
    await render_ticket_view(callback, session, ticket_id)
    await callback.answer("بروزرسانی شد.")
