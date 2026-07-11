"""
Web-based charge API endpoints.
Handles package selection, charge order creation, and receipt upload for existing subscriptions.
"""

import base64
import json
import logging
import os
import random
import string
from datetime import datetime

from aiohttp import web
from sqlalchemy.future import select

from app.api.deps import _verify_webapp_auth, set_tma_session_cookie
from app.core.settings import ADMIN_ID, BOT_TOKEN, CHARGE_PRESET_PACKAGES, PAYMENT_CARD_HOLDER, PAYMENT_CARD_NUMBER
from app.database import crud
from app.database.models import AsyncSessionLocal, ChargeRequest, Subscription, User
from app.services.pasarguard import pasarguard_api
from app.utils.validation import detect_image_type, validate_image_bytes

logger = logging.getLogger(__name__)
MAX_RECEIPT_BYTES = 8 * 1024 * 1024
GB = 1024 * 1024 * 1024

