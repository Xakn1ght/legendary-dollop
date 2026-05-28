"""Telegram bot tokens and admin identity (from environment)."""

import os

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_BOT_TOKEN = os.environ.get("ADMIN_BOT_TOKEN", "")
# Optional: used to tell admins where the panel moved (e.g., "MyAdminBot" without @)
ADMIN_BOT_USERNAME = os.environ.get("ADMIN_BOT_USERNAME", "")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", None)
