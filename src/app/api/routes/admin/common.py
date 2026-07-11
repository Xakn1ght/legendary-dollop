import ipaddress
import json
from datetime import datetime

from aiogram.types import WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiohttp import web
from sqlalchemy import and_, delete, desc, func
from sqlalchemy.future import select

from app.api.deps import _verify_webapp_auth
from app.api.schemas import (
    AdminBroadcastRequest,
    AdminIPWhitelistRequest,
    AdminSendNotificationRequest,
    AdminTicketReplyRequest,
    AdminToggleUserStatusRequest,
    AdminUpdateChargePackagesRequest,
    AdminUpdatePaymentSettingsRequest,
    AdminUpdatePlansRequest,
    AdminUserUpdateRequest,
    PaginationParams,
    validate_request,
)
from app.core.settings import BOT_TOKEN
from app.database import crud, notifications_crud
from app.database.models import (
    AsyncSessionLocal,
    ChargeRequest,
    Notification,
    Subscription,
    Ticket,
    TicketMessage,
    User,
    VipOrder,
)
from app.services.pasarguard import pasarguard_api
from app.utils.admin_ip_whitelist import load_whitelist, update_whitelist

# WebSocket broadcast (safe import - if fails, just doesn't broadcast)
try:
    from app.api.routes.admin_ws import broadcast_ticket_list_update, broadcast_ticket_update
    WS_ENABLED = True
except ImportError:
    WS_ENABLED = False
    async def broadcast_ticket_update(*args, **kwargs): pass
    async def broadcast_ticket_list_update(*args, **kwargs): pass

# Lightweight admin WS events (receipts live updates, etc.)
try:
    from app.api.routes.admin_ws import broadcast_admin_event
except ImportError:
    async def broadcast_admin_event(*args, **kwargs):  # type: ignore
        return

