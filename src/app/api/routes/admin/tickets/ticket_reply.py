from app.utils.admin_bot_helper import resolve_user_bot

from ..common import *  # noqa: F403


async def handle_admin_ticket_reply(request: web.Request):
    try:
        # NOTE: indentation normalized (no functional change)
        ticket_id = int(request.match_info['ticket_id'])
    except (ValueError, KeyError):
        return web.json_response({"ok": False, "error": "invalid_ticket_id"}, status=400)
    
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid_json"}, status=400)
    
    # Validate input using Pydantic schema
    validated, error = validate_request(AdminTicketReplyRequest, data)
    if error:
        return web.json_response(error, status=400)
    
    message = validated.message
    
    try:
        async with AsyncSessionLocal() as session:
            ticket = await session.get(Ticket, ticket_id)
            if not ticket:
                return web.json_response({"ok": False, "error": "not_found"}, status=404)

            # Enforce ticket state: no replies to closed/archived tickets
            if ticket.status in ('closed', 'archived'):
                return web.json_response({"ok": False, "error": "ticket_closed"}, status=400)
            
            # Add message
            new_msg = TicketMessage(
                ticket_id=ticket_id,
                sender='admin',
                content_type='text',
                text=message,
                # User hasn't read this message yet
                read_by_user=False,
                created_at=datetime.utcnow()
            )
            
            session.add(new_msg)
            
            # Update status if needed
            status_changed = False
            if ticket.status == 'pending':
                ticket.status = 'open'
                status_changed = True
            ticket.updated_at = datetime.utcnow()
            
            await session.commit()
            
            user = await session.get(User, ticket.user_id)

            # Support is WebApp-only, but we still notify in Telegram with a WebApp button
            # (no message content, just a deep-link to the ticket).
            bot = resolve_user_bot(request.app.get('bot'))
            ticket_owner_chat_id = user.chat_id if user else None
            if bot and user and user.chat_id:
                try:
                    from app.api.routes.admin_ws import is_user_connected_to_support, is_user_watching_ticket
                    from app.core.settings import DASHBOARD_PUBLIC_BASE_URL

                    url = f"{DASHBOARD_PUBLIC_BASE_URL}/webapp/dashboard/support.html?ticket_id={ticket_id}"
                    kb = InlineKeyboardBuilder()
                    kb.button(text="🎫 باز کردن پشتیبانی", web_app=WebAppInfo(url=url))
                    kb.adjust(1)

                    # If the user currently has the support page open, don't spam Telegram.
                    if not (
                        ticket_owner_chat_id
                        and (
                            is_user_watching_ticket(ticket_owner_chat_id, ticket_id)
                            or is_user_connected_to_support(ticket_owner_chat_id)
                        )
                    ):
                        visible_no = ticket.user_ticket_number or ticket_id
                        await bot.send_message(
                            user.chat_id,
                            f"📩 پیام جدید پشتیبانی برای تیکت #{visible_no}\n"
                            "برای مشاهده و پاسخ، دکمه زیر را بزنید:",
                            reply_markup=kb.as_markup(),
                        )
                except Exception:
                    pass
            
            # Create notification for user dashboard
            await notifications_crud.create_notification(
                db=session,
                user_id=ticket.user_id,
                type='ticket_new_message',
                title=f'پاسخ جدید به تیکت #{ticket_id}',
                message='پشتیبانی به تیکت شما پاسخ داده است',
                ticket_id=ticket.id,
                sent_to_webapp=True
            )
            await session.commit()
            
            # Broadcast to WebSocket (safe - does nothing if WS not connected)
            # Get user's chat_id (Telegram user_id) to match with WebSocket connection mapping
            # Pass ticket_owner_chat_id so we only notify the ticket owner, not all users
            try:
                await broadcast_ticket_update(ticket_id, 'new_message', {
                    'sender': 'admin',
                    'text': message,
                    'created_at': new_msg.created_at.isoformat()
                }, ticket_user_id=ticket_owner_chat_id)
            except Exception:
                pass  # WebSocket broadcast failed, no problem

            # If the reply transitioned the ticket from pending -> open, broadcast status update immediately
            if status_changed:
                try:
                    await broadcast_ticket_update(ticket_id, 'status_change', {
                        'status': ticket.status,
                        'updated_at': ticket.updated_at.isoformat() if ticket.updated_at else None
                    }, ticket_user_id=ticket_owner_chat_id)
                except Exception:
                    pass
            
            return web.json_response({"ok": True})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)
