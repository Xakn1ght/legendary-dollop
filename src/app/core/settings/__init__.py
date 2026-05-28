"""Application configuration: environment variables and JSON files under ``app/core/``.

Import ``app.core.settings`` runs side effects in this order: dotenv load, then JSON overrides
(``plans.json``, ``job_schedules.json``, ``load_support_settings()``, etc.), matching the former
monolithic ``settings.py`` behavior.
"""

import app.core.settings.bootstrap  # noqa: F401  # loads dotenv via import side effect
from app.core.settings.bootstrap import CORE_DIR, SETTINGS_PACKAGE_DIR, logger
from app.core.settings.bot_behavior import *
from app.core.settings.bots import *
from app.core.settings.catalog_plans import *
from app.core.settings.external import *
from app.core.settings.payment_ui import *
from app.core.settings.persistence import *
from app.core.settings.redis_settings import *
from app.core.settings.security import *
from app.core.settings.support_system import *
from app.core.settings.web_game import *
