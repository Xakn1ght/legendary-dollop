from aiogram import BaseMiddleware
from aiogram.types import Update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.chat_sessions import user_to_admin
from app.database import cached_crud


class BannedUserMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Update, data: dict):
        user_id = None

        # Extract user_id from various update types
        if event.message and event.message.from_user:
            user_id = event.message.from_user.id
            # If the user is in an active chat, allow the message to pass through
            if user_id in user_to_admin:
                return await handler(event, data)
        elif event.edited_message and event.edited_message.from_user:
            user_id = event.edited_message.from_user.id
        elif event.callback_query and event.callback_query.from_user:
            user_id = event.callback_query.from_user.id
            # Allow plead requests to pass through
            if event.callback_query.data.startswith("plead_unban_"):
                return await handler(event, data)
        elif event.inline_query and event.inline_query.from_user:
            user_id = event.inline_query.from_user.id
        
        if user_id is not None:
            session: AsyncSession = data.get('session')
            # The session might not be available for all updates if other middleware fails.
            if session:
                user = await cached_crud.get_user_with_cache(session, user_id)
                if user and user.banned:
                    # User is banned, stop processing further.
                    return
        
        # If user is not banned or we couldn't check, continue to the next handler.
        return await handler(event, data) 