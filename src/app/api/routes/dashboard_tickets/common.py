import json
import logging
from datetime import datetime

from aiohttp import web
from sqlalchemy import func
from sqlalchemy.future import select

from app.api.deps import _extract_user_id_from_init, _verify_webapp_auth, set_tma_session_cookie
from app.api.schemas import TicketCreateRequest, TicketReplyRequest, validate_request
from app.database import crud
from app.database.models import AsyncSessionLocal, Subscription, Ticket, TicketMessage, User
from app.utils.webapp_verify import create_session_token, verify_init_data, verify_session_token

# WebSocket broadcast (safe import - if fails, just doesn't broadcast)
try:
    from app.api.routes.admin_ws import (
        broadcast_ticket_list_update,
        broadcast_ticket_update,
        broadcast_user_ticket_list_update,
    )
    WS_ENABLED = True
except ImportError:
    WS_ENABLED = False
    async def broadcast_ticket_update(*args, **kwargs): pass
    async def broadcast_ticket_list_update(*args, **kwargs): pass
    async def broadcast_user_ticket_list_update(*args, **kwargs): pass

