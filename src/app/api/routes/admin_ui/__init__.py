"""Admin UI JSON handlers (split from former routes/admin_ui.py)."""

from app.api.routes.admin_ui.handlers import (
    handle_admin_ui_get_settings,
    handle_admin_ui_set_settings,
    handle_admin_ui_upload_background,
)

__all__ = [
    "handle_admin_ui_get_settings",
    "handle_admin_ui_set_settings",
    "handle_admin_ui_upload_background",
]
