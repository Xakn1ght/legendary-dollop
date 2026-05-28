"""Redis connection parameters from environment."""

import os

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD", None)
REDIS_DB = int(os.environ.get("REDIS_DB", 0))
# Separate Redis logical DB for aiogram FSM (avoids clashing with pickled cache keys on db 0).
REDIS_FSM_DB = int(os.environ.get("REDIS_FSM_DB", "1"))
