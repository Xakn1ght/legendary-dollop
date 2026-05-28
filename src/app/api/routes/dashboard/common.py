import json
import logging
from datetime import datetime, timedelta

from aiohttp import ClientSession, ClientTimeout, web
from sqlalchemy import and_, delete, desc, func
from sqlalchemy.future import select

from app.api.deps import _extract_user_id_from_init, _verify_webapp_auth, set_tma_session_cookie
from app.api.schemas import (
    DashboardLoginRequest,
    DashboardMarkNotificationReadRequest,
    DashboardPreferencesPatchRequest,
    validate_request,
)
from app.core.paths import webapp_path
from app.core.settings import (
    ADMIN_BOT_TOKEN,
    BOT_TOKEN,
    DASHBOARD_API_BASE_PATH,
    DASHBOARD_WEBAPP_BASE_PATH,
    GAME_REWARDS,
    PAYMENT_CARD_NUMBER,
    SUBLINK,
    VIP_PLANS,
    WEBAPP_SESSION_SECRET,
)
from app.database import crud, notifications_crud
from app.database.models import (
    AsyncSessionLocal,
    Challenge,
    Notification,
    Referral,
    ReferralReward,
    StarRewardTier,
    Subscription,
    Ticket,
    TicketMessage,
    User,
    UserStarRewardClaim,
    VipOrder,
)
from app.handlers.user.my_services.utils import map_inbound_to_country
from app.services.marzban import marzban_api
from app.utils.validation import detect_image_type, validate_image_bytes
from app.utils.webapp_verify import create_session_token, verify_init_data, verify_session_token

logger = logging.getLogger(__name__)
MAX_RECEIPT_BYTES = 8 * 1024 * 1024


def _parse_tier_reward_value(raw: str) -> dict:
    """Parse tier.reward_value into a structured dict for the webapp.

    Supported keys: credit, sub_credit, discount, traffic_gb (ints).
    """
    out = {"credit": 0, "sub_credit": 0, "discount": 0, "traffic_gb": 0}
    parts = [p.strip() for p in str(raw or "").split("|") if p.strip()]
    for p in parts:
        if ":" not in p:
            continue
        k, v = p.split(":", 1)
        k = k.strip()
        v = v.strip()
        if k in {"credit", "sub_credit", "discount", "traffic_gb"}:
            try:
                out[k] = int(v)
            except Exception:
                pass
    return out


def _normalize_sub_id(value: str | int | None) -> str | None:
    if value is None:
        return None
    try:
        s = str(value).strip()
    except Exception:
        return None
    if not s:
        return None
    # Keep it simple: numeric IDs only.
    if not s.isdigit():
        return None
    return s[:32]
