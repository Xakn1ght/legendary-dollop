import json
import logging

from aiohttp import web

from app.api.deps import _extract_user_id_from_init, _verify_webapp_auth
from app.api.schemas import ArcadeSubmitRequest, LeaderboardRequest, validate_request
from app.core.paths import webapp_path
from app.core.settings import BOT_TOKEN
from app.database import crud
from app.database.models import AsyncSessionLocal, User
from app.utils.webapp_verify import verify_init_data

logger = logging.getLogger(__name__)

