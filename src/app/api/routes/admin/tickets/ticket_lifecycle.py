from app.utils.admin_bot_helper import resolve_user_bot

from ..common import *  # noqa: F403


async def handle_admin_ticket_close(request: web.Request):
    try:
        ticket_id = int(request.match_info['ticket_id'])
    except (ValueError, KeyError):
        return web.json_response({"ok": False, "error": "invalid_ticket_id"}, status=400)
    try:
        async with AsyncSessionLocal() as session:
            ticket = await session.get(Ticket, ticket_id)
            if not ticket:
                return web.json_response({"ok": False, "error": "not_found"}, status=404)
            
            ticket.status = 'closed'
            ticket.closed_at = datetime.utcnow()
            ticket.updated_at = datetime.utcnow()
            await session.commit()

            # Get ticket owner info
            user = await session.get(User, ticket.user_id)
            ticket_owner_chat_id = user.chat_id if user else None
            
            # Notify user
            await notifications_crud.create_notification(
                db=session,
                user_id=ticket.user_id,
                type='ticket_closed',
                title=f'تیکت #{ticket_id} بسته شد',
                message='تیکت پشتیبانی شما بسته شد',
                ticket_id=ticket.id,
                sent_to_webapp=True,
                sent_to_bot=True
            )
            await session.commit()
            
            # Send Telegram notification
            bot = resolve_user_bot(request.app.get('bot'))
            if bot and ticket_owner_chat_id:
                try:
                    await bot.send_message(
                        chat_id=ticket_owner_chat_id,
                        text=f"*تیکت #{ticket_id} بسته شد*\n\nتیکت پشتیبانی شما بسته شد.\nبرای مشکل جدید می‌توانید تیکت جدید ارسال کنید.",
                        parse_mode='Markdown'
                    )
                except Exception:
                    pass

            # Broadcast status update so both admin + user UIs update immediately
            try:
                await broadcast_ticket_update(ticket_id, 'status_change', {
                    'status': ticket.status,
                    'updated_at': ticket.updated_at.isoformat() if ticket.updated_at else None
                }, ticket_user_id=ticket_owner_chat_id)
            except Exception:
                pass
            
            return web.json_response({"ok": True})
    except Exception as e:
        return web.json_response({"ok": False, "error": "server_error"}, status=500)


async def handle_admin_ticket_archive(request: web.Request):
    """
    Archive a ticket:
    - Marks status=archived
    - Hides from user dashboard list (hidden_from_user=True)
    """
    try:
        ticket_id = int(request.match_info['ticket_id'])
    except (ValueError, KeyError):
        return web.json_response({"ok": False, "error": "invalid_ticket_id"}, status=400)
    try:
        async with AsyncSessionLocal() as session:
            ticket = await session.get(Ticket, ticket_id)
            if not ticket:
                return web.json_response({"ok": False, "error": "not_found"}, status=404)

            ticket.status = 'archived'
            ticket.hidden_from_user = True
            ticket.hidden_at = datetime.utcnow()
            ticket.closed_at = ticket.closed_at or datetime.utcnow()
            ticket.updated_at = datetime.utcnow()
            await session.commit()

            # Get ticket owner chat_id for targeted WebSocket updates
            ticket_owner_chat_id = None
            try:
                user = await session.get(User, ticket.user_id)
                if user and user.chat_id:
                    ticket_owner_chat_id = user.chat_id
            except Exception:
                ticket_owner_chat_id = None

            # Broadcast status update so both admin + user UIs update immediately
            try:
                await broadcast_ticket_update(ticket_id, 'status_change', {
                    'status': ticket.status,
                    'updated_at': ticket.updated_at.isoformat() if ticket.updated_at else None
                }, ticket_user_id=ticket_owner_chat_id)
            except Exception:
                pass

            return web.json_response({"ok": True})
    except Exception:
        return web.json_response({"ok": False, "error": "server_error"}, status=500)


async def handle_admin_ticket_reopen(request: web.Request):
    """Reopen a closed/archived ticket (admin action)."""
    try:
        ticket_id = int(request.match_info['ticket_id'])
    except (ValueError, KeyError):
        return web.json_response({"ok": False, "error": "invalid_ticket_id"}, status=400)
    try:
        async with AsyncSessionLocal() as session:
            ticket = await session.get(Ticket, ticket_id)
            if not ticket:
                return web.json_response({"ok": False, "error": "not_found"}, status=404)

            ticket.status = 'open'
            ticket.hidden_from_user = False
            ticket.hidden_at = None
            ticket.closed_at = None
            ticket.updated_at = datetime.utcnow()
            await session.commit()

            # Get ticket owner chat_id for targeted WebSocket updates
            ticket_owner_chat_id = None
            try:
                user = await session.get(User, ticket.user_id)
                if user and user.chat_id:
                    ticket_owner_chat_id = user.chat_id
            except Exception:
                ticket_owner_chat_id = None

            try:
                await broadcast_ticket_update(ticket_id, 'status_change', {
                    'status': ticket.status,
                    'updated_at': ticket.updated_at.isoformat() if ticket.updated_at else None
                }, ticket_user_id=ticket_owner_chat_id)
            except Exception:
                pass

            return web.json_response({"ok": True})
    except Exception:
        return web.json_response({"ok": False, "error": "server_error"}, status=500)
