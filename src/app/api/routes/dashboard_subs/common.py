import base64
import json
from urllib.parse import urlparse

from aiohttp import web

from app.api.deps import _extract_user_id_from_init, _verify_webapp_auth, set_tma_session_cookie
from app.api.schemas import AddSubscriptionRequest, validate_request
from app.core.settings import (
    BOT_TOKEN,
    DASHBOARD_API_BASE_PATH,
    DASHBOARD_SUBSCRIPTION_ALLOWED_DOMAINS,
    DASHBOARD_SUBSCRIPTION_DOMAIN_ENFORCE,
    SUBLINK,
    WEBAPP_SESSION_SECRET,
)
from app.database import crud
from app.database.models import AsyncSessionLocal, Subscription
from app.handlers.user.my_services.utils import map_inbound_to_country
from app.services.pasarguard import pasarguard_api
from app.utils.webapp_verify import create_session_token, verify_init_data, verify_session_token


def _is_dashboard_visible_subscription(s: Subscription) -> bool:
    """
    Dashboard dropdown should include only subscriptions that can actually load.
    Draft/pending purchase rows are not created on PasarGuard yet (no info/links),
    so they must not be shown in the subscription selector.
    """
    st = (getattr(s, "status", None) or "").lower().strip()
    return st not in ("draft", "pending", "cancelled")
