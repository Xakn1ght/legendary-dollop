"""Database URL and user state file path."""

import os

from app.core.paths import data_path

# File paths
USER_STATE_FILE = data_path("user_state.json")
# IMPORTANT: Set DATABASE_URL in .env file for security
# Example: DATABASE_URL=postgresql+asyncpg://user:password@host:port/database
DATABASE_URL = os.environ.get("DATABASE_URL", "")
