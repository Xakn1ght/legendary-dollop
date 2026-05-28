from __future__ import annotations

import json
import os
import re
from datetime import datetime

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import crud
from app.utils.logger import log_error

from .common import control_msg_registry, router, safe_edit_message


@router.callback_query(F.data == "private_chat_end")
async def end_private_chat(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    """End an active private chat session"""
    data = await state.get_data()
    ticket_id = data.get("ticket_id")
    partner_chat_id = data.get("partner_chat_id")
    role = data.get("role")

    if not ticket_id or not partner_chat_id:
        await callback.answer("چت فعالی یافت نشد", show_alert=True)
        return

    # End the chat in database
    await crud.end_private_chat(session, ticket_id)
    
    # Clear active chat records
    await state.clear()
    
    # Build JSON transcript and send ONLY to admin
    try:
        msgs = await crud.get_ticket_messages(session, ticket_id, limit=2000)
        # Fetch ticket and user/admin info
        t = await crud.get_ticket_by_id(session, ticket_id)
        from app.database.crud import get_user_by_id
        user_rec = await get_user_by_id(session, t.user_id) if t else None
        admin_rec = await get_user_by_id(session, t.assigned_admin_id) if t and t.assigned_admin_id else None

        def _iso(dt):
            try:
                return dt.isoformat()
            except Exception:
                return None

        data = {
            "ticket_id": ticket_id,
            "category": getattr(t, 'category', None),
            "started_at": _iso(getattr(t, 'created_at', None)),
            "ended_at": _iso(datetime.utcnow()),
            "user": {
                "id": getattr(user_rec, 'id', None),
                "chat_id": getattr(user_rec, 'chat_id', None),
                "username": getattr(user_rec, 'username', None),
                "full_name": getattr(user_rec, 'full_name', None),
            },
            "admin": {
                "id": getattr(admin_rec, 'id', None),
                "chat_id": getattr(admin_rec, 'chat_id', None),
            },
            "messages": [
                {
                    "id": m.id,
                    "sender": m.sender,
                    "content_type": m.content_type,
                    "text": m.text,
                    "telegram_message_id": m.telegram_message_id,
                    "file_id": m.file_id,
                    "file_unique_id": m.file_unique_id,
                    "file_name": m.file_name,
                    "file_size": m.file_size,
                    "file_mime_type": m.file_mime_type,
                    "voice_duration": m.voice_duration,
                    "reply_to_message_id": m.reply_to_message_id,
                    "replied_to": m.replied_to,
                    "created_at": _iso(m.created_at),
                }
                for m in msgs
            ],
        }

        # Build filename: username or full_name or user_id; include date
        date_str = datetime.utcnow().strftime('%Y-%m-%d')
        base_name = None
        if user_rec and user_rec.username:
            base_name = user_rec.username
        elif user_rec and user_rec.full_name:
            base_name = user_rec.full_name
        elif user_rec and user_rec.chat_id:
            base_name = f"user_{user_rec.chat_id}"
        else:
            base_name = f"ticket_{ticket_id}"

        # Sanitize filename
        import re
        safe = re.sub(r"[^A-Za-z0-9._-]+", "_", base_name).strip("._-") or f"ticket_{ticket_id}"
        filename = f"{safe}_{date_str}.json"

        # Persist to disk
        dir_path = os.path.join('logs', 'transcripts')
        try:
            os.makedirs(dir_path, exist_ok=True)
            file_path = os.path.join(dir_path, filename)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            file_path = None

        # Send to admin only as JSON document
        admin_chat_id = getattr(admin_rec, 'chat_id', None) or partner_chat_id if role == 'user' else callback.message.chat.id
        try:
            content = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
            buf = BufferedInputFile(content, filename=filename)
            await callback.bot.send_document(admin_chat_id, buf, caption=f"📄 Transcript for ticket #{ticket_id}")
        except Exception:
            # Fallback: send as text if document send fails
            try:
                await callback.bot.send_message(admin_chat_id, "📄 Transcript (JSON too large to attach).")
            except Exception:
                pass
    except Exception:
        pass

    # Notify both parties
    end_message_self = f"🔚 گفتگوی خصوصی برای تیکت #{ticket_id} به پایان رسید."
    partner_end_message = (
        f"🔚 گفتگوی خصوصی برای تیکت #{ticket_id} توسط ادمین پایان یافت." if role == 'admin'
        else f"🔚 گفتگوی خصوصی برای تیکت #{ticket_id} توسط کاربر پایان یافت."
    )
    
    await safe_edit_message(callback, end_message_self)
    
    try:
        # Notify the other party
        # Clean partner's keyboard if we have the control message id
        reg = control_msg_registry.get(ticket_id)
        if reg:
            try:
                # Determine which side ended
                ended_is_admin = (role == 'admin')
                partner_msg_id = reg['user_msg_id'] if ended_is_admin else reg['admin_msg_id']
                partner_chat_id_resolved = reg['user_chat_id'] if ended_is_admin else reg['admin_chat_id']
                await callback.bot.edit_message_text(
                    partner_end_message,
                    chat_id=partner_chat_id_resolved,
                    message_id=partner_msg_id
                )
                # Also send a fresh notification message so it's clearly visible
                try:
                    await callback.bot.send_message(partner_chat_id_resolved, partner_end_message)
                except Exception:
                    pass
            except Exception:
                # Fallback to sending a new message
                try:
                    other_chat_id = reg['user_chat_id'] if role == 'admin' else reg['admin_chat_id']
                    if other_chat_id:
                        await callback.bot.send_message(other_chat_id, partner_end_message)
                except Exception:
                    pass
            # Remove registry entry
            control_msg_registry.pop(ticket_id, None)
        else:
            # No registry; send a new message
            if partner_chat_id:
                await callback.bot.send_message(partner_chat_id, partner_end_message)
        
        # Record in ticket messages
        await crud.add_ticket_message(
            session,
            ticket_id,
            sender="system",
            content_type="text",
            text="گفتگوی خصوصی پایان یافت"
        )
    except Exception as e:
        log_error(e, {"operation": "end_private_chat", "ticket_id": ticket_id})
