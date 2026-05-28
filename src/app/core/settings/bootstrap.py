"""Dotenv load and on-disk paths for JSON collateral (files live in ``app/core/``, not this subpackage)."""

import logging
from pathlib import Path

from dotenv import load_dotenv

from app.core.paths import repo_root

SETTINGS_PACKAGE_DIR = Path(__file__).resolve().parent
# Historical: JSON files sat next to ``settings.py`` in ``app/core/``.
CORE_DIR = SETTINGS_PACKAGE_DIR.parent

try:
    _env_path = repo_root() / "config" / ".env"
    if _env_path.exists():
        load_dotenv(dotenv_path=_env_path)
    else:
        load_dotenv()
except Exception:
    load_dotenv()

logger = logging.getLogger("app.core.settings")
