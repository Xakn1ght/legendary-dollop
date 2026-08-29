"""Telegram bot tokens and admin identity (from environment)."""

import os

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_BOT_TOKEN = os.environ.get("ADMIN_BOT_TOKEN", "")
# Optional: used to tell admins where the panel moved (e.g., "MyAdminBot" without @)
ADMIN_BOT_USERNAME = os.environ.get("ADMIN_BOT_USERNAME", "")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", None)

# Local Telegram Bot API server. Empty = Telegram's cloud API (default).
# Set to http://127.0.0.1:8081 to use the self-hosted server on this box.
# Switching a bot here also needs a one-time logOut on the cloud API.
TELEGRAM_API_BASE = os.environ.get("TELEGRAM_API_BASE", "").strip()
