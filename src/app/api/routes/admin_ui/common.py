"""Admin UI settings and upload storage (paths via app.core.paths)."""
import json
import os
import secrets

from aiohttp import web

from app.core.paths import data_path, webapp_path

_SETTINGS_PATH = data_path("admin_ui_settings.json")
_UPLOAD_DIR = os.path.abspath(webapp_path("admin", "uploads"))


def _load_settings() -> dict:
    try:
        if not os.path.exists(_SETTINGS_PATH):
            return {}
        with open(_SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f) or {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_settings(data: dict) -> None:
    try:
        os.makedirs(os.path.dirname(_SETTINGS_PATH), exist_ok=True)
        with open(_SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        return
