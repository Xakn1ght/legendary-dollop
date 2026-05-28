import asyncio
from datetime import datetime

from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database.models import Ticket, TicketMessage

# WebSocket broadcast (safe import - if fails, just doesn't broadcast)
try:
    from app.api.routes.admin_ws import broadcast_ticket_update
    WS_ENABLED = True
except ImportError:
    WS_ENABLED = False
    async def broadcast_ticket_update(*args, **kwargs): pass

class TicketRepository:
    @staticmethod
    async def create_ticket(
        db: AsyncSession,
        user_id: int,
        category: str,
        status: str = 'pending',
        priority: str = 'normal',
        os: str | None = None,
        isp: str | None = None,
        subscription_id: int | None = None,
    ) -> Ticket:
        ticket = Ticket(
            user_id=user_id,
            category=category,
            status=status,
            priority=priority,
            os=os,
            isp=isp,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            last_message_at=datetime.utcnow(),
            subscription_id=subscription_id,
        )
        db.add(ticket)
        await db.commit()
        await db.refresh(ticket)
        return ticket

    @staticmethod
    async def add_ticket_message(
        db: AsyncSession,
        ticket_id: int,
        sender: str,
        content_type: str = 'text',
        text: str | None = None,
        telegram_message_id: int | None = None,
        file_id: str | None = None,
    ) -> TicketMessage:
        msg = TicketMessage(
            ticket_id=ticket_id,
            sender=sender,
            content_type=content_type,
            text=text,
            telegram_message_id=telegram_message_id,
            file_id=file_id,
            created_at=datetime.utcnow(),
        )
        db.add(msg)

        # Update parent ticket timestamps
        ticket = await db.get(Ticket, ticket_id)
        if ticket:
            ticket.last_message_at = datetime.utcnow()
            ticket.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(msg)
        
        # Broadcast to WebSocket for real-time admin updates (non-blocking)
        try:
            asyncio.create_task(broadcast_ticket_update(ticket_id, 'new_message', {
                'sender': sender,
                'text': text or '',
                'created_at': msg.created_at.isoformat() if msg.created_at else None
            }))
        except Exception:
            pass  # Don't let WebSocket issues affect message saving
        
        return msg

    @staticmethod
    async def get_ticket_by_id(db: AsyncSession, ticket_id: int) -> Ticket | None:
        result = await db.execute(select(Ticket).filter(Ticket.id == ticket_id))
        return result.scalars().first()

    @staticmethod
    async def list_tickets_by_user(db: AsyncSession, user_id: int, limit: int = 20):
        result = await db.execute(
            select(Ticket)
            .filter(Ticket.user_id == user_id)
            .order_by(Ticket.updated_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

    @staticmethod
    async def get_ticket_messages(db: AsyncSession, ticket_id: int, limit: int = 50):
        result = await db.execute(
            select(TicketMessage)
            .filter(TicketMessage.ticket_id == ticket_id)
            .order_by(TicketMessage.created_at.asc())
            .limit(limit)
        )
        return result.scalars().all()

    @staticmethod
    async def update_ticket_status(db: AsyncSession, ticket_id: int, status: str):
        ticket = await db.get(Ticket, ticket_id)
        if not ticket:
            return None
        ticket.status = status
        if status == 'closed':
            ticket.closed_at = datetime.utcnow()
        ticket.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(ticket)
        return ticket

    @staticmethod
    async def set_ticket_notify_on_reply(db: AsyncSession, ticket_id: int, enabled: bool):
        ticket = await db.get(Ticket, ticket_id)
        if not ticket:
            return None
        ticket.notify_on_reply = enabled
        ticket.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(ticket)
        return ticket

    @staticmethod
    async def save_ticket_feedback(db: AsyncSession, ticket_id: int, score: int | None, text: str | None):
        ticket = await db.get(Ticket, ticket_id)
        if not ticket:
            return None
        ticket.feedback_score = score
        ticket.feedback_text = text
        ticket.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(ticket)
        return ticket

    @staticmethod
    async def assign_ticket(db: AsyncSession, ticket_id: int, admin_user_id: int | None):
        ticket = await db.get(Ticket, ticket_id)
        if not ticket:
            return None
        ticket.assigned_admin_id = admin_user_id
        ticket.status = 'open' if admin_user_id else 'pending'
        ticket.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(ticket)
        return ticket

    @staticmethod
    async def change_ticket_category(db: AsyncSession, ticket_id: int, category: str):
        ticket = await db.get(Ticket, ticket_id)
        if not ticket:
            return None
        ticket.category = category
        ticket.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(ticket)
        return ticket

    @staticmethod
    async def change_ticket_priority(db: AsyncSession, ticket_id: int, priority: str):
        ticket = await db.get(Ticket, ticket_id)
        if not ticket:
            return None
        ticket.priority = priority
        ticket.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(ticket)
        return ticket

    @staticmethod
    async def set_ticket_allow_more(db: AsyncSession, ticket_id: int, allow: bool):
        ticket = await db.get(Ticket, ticket_id)
        if not ticket:
            return None
        ticket.allow_more_from_user = allow
        ticket.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(ticket)
        return ticket

    @staticmethod
    async def get_category_queue_position(db: AsyncSession, category: str, ticket_id: int) -> int:
        result = await db.execute(
            select(Ticket.id)
            .filter(Ticket.category == category, Ticket.status == 'pending')
            .order_by(Ticket.created_at.asc())
        )
        ids = [row[0] for row in result.fetchall()]
        try:
            idx = ids.index(ticket_id)
            return idx + 1
        except ValueError:
            return 1

    @staticmethod
    async def list_tickets_by_category(db: AsyncSession, category: str, status: str | None = None, limit: int = 50):
        query = select(Ticket).filter(Ticket.category == category)
        if status:
            query = query.filter(Ticket.status == status)
        result = await db.execute(query.order_by(Ticket.updated_at.desc()).limit(limit))
        return result.scalars().all()

    @staticmethod
    async def list_all_tickets(db: AsyncSession, status: str | None = None, limit: int = 100):
        query = select(Ticket)
        if status:
            query = query.filter(Ticket.status == status)
        result = await db.execute(query.order_by(Ticket.updated_at.desc()).limit(limit))
        return result.scalars().all()

    @staticmethod
    async def start_private_chat(db: AsyncSession, ticket_id: int, admin_user_id: int) -> Ticket | None:
        ticket = await db.get(Ticket, ticket_id)
        if not ticket:
            return None
        
        ticket.is_private_chat = True
        ticket.chat_invitation_sent = True
        ticket.chat_invitation_sent_at = datetime.utcnow()
        ticket.assigned_admin_id = admin_user_id
        ticket.status = 'open'
        ticket.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(ticket)
        return ticket

    @staticmethod
    async def accept_chat_invitation(db: AsyncSession, ticket_id: int) -> Ticket | None:
        ticket = await db.get(Ticket, ticket_id)
        if not ticket or not ticket.is_private_chat or not ticket.chat_invitation_sent:
            return None
        
        ticket.chat_invitation_accepted = True
        ticket.chat_started_at = datetime.utcnow()
        ticket.chat_invitation_expired = False
        ticket.updated_at = datetime.utcnow()
        ticket.status = 'private_chat'
        
        await db.commit()
        await db.refresh(ticket)
        return ticket

    @staticmethod
    async def expire_chat_invitation(db: AsyncSession, ticket_id: int) -> Ticket | None:
        ticket = await db.get(Ticket, ticket_id)
        if not ticket or not ticket.is_private_chat or not ticket.chat_invitation_sent:
            return None
        
        ticket.chat_invitation_expired = True
        ticket.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(ticket)
        return ticket

    @staticmethod
    async def end_private_chat(db: AsyncSession, ticket_id: int) -> Ticket | None:
        ticket = await db.get(Ticket, ticket_id)
        if not ticket or not ticket.is_private_chat:
            return None
        
        ticket.chat_ended_at = datetime.utcnow()
        ticket.status = 'closed'
        ticket.updated_at = datetime.utcnow()
        ticket.closed_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(ticket)
        return ticket

    @staticmethod
    async def add_ticket_message_with_reply(
        db: AsyncSession,
        ticket_id: int,
        sender: str,
        content_type: str = 'text',
        text: str | None = None,
        telegram_message_id: int | None = None,
        file_id: str | None = None,
        reply_to_message_id: int | None = None,
        replied_to: int | None = None,
        file_unique_id: str | None = None,
        file_name: str | None = None,
        file_size: int | None = None,
        file_mime_type: str | None = None,
        voice_duration: int | None = None,
    ) -> TicketMessage:
        msg = TicketMessage(
            ticket_id=ticket_id,
            sender=sender,
            content_type=content_type,
            text=text,
            telegram_message_id=telegram_message_id,
            file_id=file_id,
            reply_to_message_id=reply_to_message_id,
            replied_to=replied_to,
            file_unique_id=file_unique_id,
            file_name=file_name,
            file_size=file_size,
            file_mime_type=file_mime_type,
            voice_duration=voice_duration,
            created_at=datetime.utcnow(),
        )
        db.add(msg)

        ticket = await db.get(Ticket, ticket_id)
        if ticket:
            ticket.last_message_at = datetime.utcnow()
            ticket.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(msg)
        
        # Broadcast to WebSocket for real-time admin updates (non-blocking)
        try:
            asyncio.create_task(broadcast_ticket_update(ticket_id, 'new_message', {
                'sender': sender,
                'text': text or '',
                'created_at': msg.created_at.isoformat() if msg.created_at else None
            }))
        except Exception:
            pass  # Don't let WebSocket issues affect message saving
        
        return msg

    @staticmethod
    async def get_ticket_message_by_telegram_id(db: AsyncSession, telegram_message_id: int) -> TicketMessage | None:
        result = await db.execute(
            select(TicketMessage).filter(TicketMessage.telegram_message_id == telegram_message_id)
        )
        return result.scalars().first()

    @staticmethod
    async def update_ticket_message_text_by_telegram_id(db: AsyncSession, telegram_message_id: int, new_text: str) -> bool:
        result = await db.execute(
            update(TicketMessage).where(TicketMessage.telegram_message_id == telegram_message_id).values(text=new_text)
        )
        if result.rowcount:
            await db.commit()
            return True
        return False

    @staticmethod
    async def get_active_chat_tickets(db: AsyncSession, admin_user_id: int | None = None, limit: int = 50):
        query = select(Ticket).filter(Ticket.is_private_chat == True, Ticket.status == 'private_chat')
        if admin_user_id:
            query = query.filter(Ticket.assigned_admin_id == admin_user_id)
        
        result = await db.execute(query.order_by(Ticket.updated_at.desc()).limit(limit))
        return result.scalars().all()

