"""
CRUD operations for notifications
"""
from datetime import datetime
from typing import List, Optional

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Notification, Ticket, User


async def create_notification(
    db: AsyncSession,
    user_id: int,
    type: str,
    title: str,
    message: str,
    ticket_id: Optional[int] = None,
    sent_to_webapp: bool = True,
    sent_to_bot: bool = False
) -> Notification:
    """
    Create a new notification for a user.
    
    Args:
        user_id: ID of the user to notify
        type: Type of notification (ticket_closed, ticket_status_changed, ticket_new_message, general)
        title: Notification title
        message: Notification message/body
        ticket_id: Optional ticket ID if ticket-related
        sent_to_webapp: Whether to show in webapp
        sent_to_bot: Whether to send via bot
        
    Returns:
        Created Notification object
    """
    notification = Notification(
        user_id=user_id,
        type=type,
        title=title,
        message=message,
        ticket_id=ticket_id,
        sent_to_webapp=sent_to_webapp,
        sent_to_bot=sent_to_bot
    )
    
    db.add(notification)
    await db.commit()
    await db.refresh(notification)
    
    return notification


async def get_user_notifications(
    db: AsyncSession,
    user_id: int,
    unread_only: bool = False,
    limit: int = 50
) -> List[Notification]:
    """
    Get notifications for a user.
    
    Args:
        user_id: ID of the user
        unread_only: If True, only return unread notifications
        limit: Maximum number of notifications to return
        
    Returns:
        List of Notification objects
    """
    query = select(Notification).where(
        and_(
            Notification.user_id == user_id,
            Notification.sent_to_webapp == True
        )
    )
    
    if unread_only:
        query = query.where(Notification.read == False)
    
    query = query.order_by(Notification.created_at.desc()).limit(limit)
    
    result = await db.execute(query)
    return result.scalars().all()


async def mark_notification_as_read(
    db: AsyncSession,
    notification_id: int,
    user_id: int
) -> bool:
    """
    Mark a notification as read.
    
    Args:
        notification_id: ID of the notification
        user_id: ID of the user (for security check)
        
    Returns:
        True if successful, False otherwise
    """
    result = await db.execute(
        update(Notification)
        .where(
            and_(
                Notification.id == notification_id,
                Notification.user_id == user_id
            )
        )
        .values(read=True, read_at=datetime.utcnow())
    )
    
    await db.commit()
    return result.rowcount > 0


async def mark_all_notifications_as_read(
    db: AsyncSession,
    user_id: int
) -> int:
    """
    Mark all notifications as read for a user.
    
    Args:
        user_id: ID of the user
        
    Returns:
        Number of notifications marked as read
    """
    result = await db.execute(
        update(Notification)
        .where(
            and_(
                Notification.user_id == user_id,
                Notification.read == False
            )
        )
        .values(read=True, read_at=datetime.utcnow())
    )
    
    await db.commit()
    return result.rowcount


async def get_unread_count(
    db: AsyncSession,
    user_id: int
) -> int:
    """
    Get count of unread notifications for a user.
    
    Args:
        user_id: ID of the user
        
    Returns:
        Count of unread notifications
    """
    result = await db.execute(
        select(func.count()).select_from(Notification).where(
            and_(
                Notification.user_id == user_id,
                Notification.sent_to_webapp.is_(True),
                Notification.read.is_(False)
            )
        )
    )

    return int(result.scalar_one() or 0)


async def delete_notification(
    db: AsyncSession,
    notification_id: int,
    user_id: int
) -> bool:
    """
    Delete a notification.
    
    Args:
        notification_id: ID of the notification
        user_id: ID of the user (for security check)
        
    Returns:
        True if successful, False otherwise
    """
    result = await db.execute(
        select(Notification).where(
            and_(
                Notification.id == notification_id,
                Notification.user_id == user_id
            )
        )
    )
    
    notification = result.scalar_one_or_none()
    if notification:
        await db.delete(notification)
        await db.commit()
        return True
    
    return False


async def delete_read_notifications(
    db: AsyncSession,
    user_id: int
) -> int:
    """
    Delete all notifications for a user (clear history).
    
    Args:
        user_id: ID of the user
        
    Returns:
        Number of notifications deleted
    """
    result = await db.execute(
        select(Notification).where(
            Notification.user_id == user_id
        )
    )
    
    notifications = result.scalars().all()
    count = len(notifications)
    
    for notification in notifications:
        await db.delete(notification)
    
    await db.commit()
    return count


async def create_ticket_notification(
    db: AsyncSession,
    ticket_id: int,
    type: str,
    title: str,
    message: str
) -> Optional[Notification]:
    """
    Create a notification for a ticket event.
    
    Args:
        ticket_id: ID of the ticket
        type: Type of notification
        title: Notification title
        message: Notification message
        
    Returns:
        Created Notification object or None if ticket not found
    """
    result = await db.execute(
        select(Ticket).where(Ticket.id == ticket_id)
    )
    ticket = result.scalar_one_or_none()
    
    if not ticket:
        return None
    
    return await create_notification(
        db=db,
        user_id=ticket.user_id,
        type=type,
        title=title,
        message=message,
        ticket_id=ticket_id
    )


async def send_general_notification_to_users(
    db: AsyncSession,
    user_ids: List[int],
    title: str,
    message: str,
    sent_to_webapp: bool = True,
    sent_to_bot: bool = False
) -> int:
    """
    Send a general notification to multiple users.
    
    Args:
        user_ids: List of user IDs to notify
        title: Notification title
        message: Notification message
        sent_to_webapp: Whether to show in webapp
        sent_to_bot: Whether to send via bot
        
    Returns:
        Number of notifications created
    """
    count = 0
    for user_id in user_ids:
        await create_notification(
            db=db,
            user_id=user_id,
            type='general',
            title=title,
            message=message,
            sent_to_webapp=sent_to_webapp,
            sent_to_bot=sent_to_bot
        )
        count += 1
    
    return count


async def send_notification_to_all_users(
    db: AsyncSession,
    title: str,
    message: str,
    sent_to_webapp: bool = True,
    sent_to_bot: bool = False
) -> int:
    """
    Send a notification to all users.
    
    Args:
        title: Notification title
        message: Notification message
        sent_to_webapp: Whether to show in webapp
        sent_to_bot: Whether to send via bot
        
    Returns:
        Number of notifications created
    """
    result = await db.execute(select(User.id))
    user_ids = [row[0] for row in result.all()]
    
    return await send_general_notification_to_users(
        db=db,
        user_ids=user_ids,
        title=title,
        message=message,
        sent_to_webapp=sent_to_webapp,
        sent_to_bot=sent_to_bot
    )


async def process_pending_bot_notifications(db: AsyncSession, bot):
    """
    Process notifications that should be sent via Telegram bot.
    Sends Telegram messages for all notifications with sent_to_bot=True
    and bot_message_sent=False.
    
    Args:
        db: Database session
        bot: Telegram Bot instance
        
    Returns:
        Number of messages sent
    """
    from aiogram import Bot
    
    # Get notifications that need to be sent via bot
    result = await db.execute(
        select(Notification).where(
            Notification.sent_to_bot == True,
            Notification.bot_message_sent == False
        ).join(User, User.id == Notification.user_id)
    )
    notifications = result.scalars().all()
    
    sent_count = 0
    for notif in notifications:
        # Get user info
        user_result = await db.execute(
            select(User).where(User.id == notif.user_id)
        )
        user = user_result.scalar_one_or_none()
        
        if user and user.chat_id:
            try:
                # Format message (no emojis)
                message_text = f"*{notif.title}*\n\n{notif.message}"
                
                # Send message
                sent_msg = await bot.send_message(
                    chat_id=user.chat_id,
                    text=message_text,
                    parse_mode='Markdown'
                )
                
                # Mark as sent
                notif.bot_message_sent = True
                notif.bot_message_id = sent_msg.message_id
                sent_count += 1
                
            except Exception as e:
                print(f"[NOTIF] Error sending bot notification to user {user.id}: {e}")
        else:
            # Mark as "sent" even if user not found to avoid retry loops
            notif.bot_message_sent = True
    
    await db.commit()
    return sent_count

