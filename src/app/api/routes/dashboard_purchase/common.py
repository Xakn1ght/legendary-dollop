"""
Web-based purchase API endpoints.
Handles plan selection, order creation, and receipt upload from the webapp.
"""

import base64
import json
import logging
import os
import random
import re
import string
from datetime import datetime

from aiohttp import web
from sqlalchemy.future import select

from app.api.deps import _verify_webapp_auth, set_tma_session_cookie
from app.api.schemas import CancelOrderRequest, StartPurchaseRequest, SubmitReceiptRequest, validate_request
from app.core.settings import (
    ADMIN_ID,
    BOT_TOKEN,
    GLOBAL_PURCHASE_DISCOUNTS,
    PAYMENT_CARD_HOLDER,
    PAYMENT_CARD_NUMBER,
    PLANS,
    VIP_PURCHASE_DISCOUNT_ENABLED,
    VIP_PURCHASE_DISCOUNT_PERCENT,
)
from app.database import crud
from app.database.models import AsyncSessionLocal, Referral, Subscription, User
from app.services.marzban import marzban_api
from app.utils.validation import detect_image_type, validate_image_bytes

logger = logging.getLogger(__name__)
MAX_RECEIPT_BYTES = 8 * 1024 * 1024

