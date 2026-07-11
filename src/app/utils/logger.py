import logging
import logging.handlers
import os
import sys
import traceback
from contextlib import asynccontextmanager
from functools import wraps
from typing import Any, Dict, Optional

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

def setup_logging(log_level: str = "INFO", log_file: str = "logs/bot.log"):
    """Setup clean, organised logging.

    Console (stdout)  -> WARNING+  — only things that need attention
    File (rotating)   -> INFO+     — full operational detail for debugging
    Error file        -> ERROR+    — quick view of problems
    """
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    # ---- Formatters -------------------------------------------------------
    # Console: short and easy to scan
    console_fmt = logging.Formatter(
        "%(asctime)s  %(levelname)-5s  %(message)s",
        datefmt="%H:%M:%S",
    )
    # File: full detail but trimmed logger name
    file_fmt = logging.Formatter(
        "%(asctime)s  %(levelname)-5s  [%(name)s]  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # ---- Handlers ---------------------------------------------------------
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_fmt)
    console_handler.setLevel(logging.WARNING)  # <-- console only shows warnings+

    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8",
    )
    file_handler.setFormatter(file_fmt)
    file_handler.setLevel(logging.INFO)

    error_handler = logging.handlers.RotatingFileHandler(
        log_file.replace(".log", "_error.log"),
        maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8",
    )
    error_handler.setFormatter(file_fmt)
    error_handler.setLevel(logging.ERROR)

    # ---- Root logger ------------------------------------------------------
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)  # let handlers decide what to keep
    if root.hasHandlers():
        root.handlers.clear()
    root.addHandler(console_handler)
    root.addHandler(file_handler)
    root.addHandler(error_handler)

    # ---- Silence noisy third-party libs -----------------------------------
    for noisy in (
        "aiogram", "aiohttp.access", "aiohttp.server", "aiohttp.web",
        "aiohttp.web_protocol", "sqlalchemy.engine",
        "apscheduler.scheduler", "apscheduler.executors",
        "apscheduler.executors.default",
        "asyncio", "charset_normalizer",
    ):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    # ---- Filter scanner noise on public ports -----------------------------
    class _ScannerNoiseFilter(logging.Filter):
        """Drop BadHttpMessage / PRI-Upgrade / random HTTP probes."""
        _noise = ("BadHttpMessage", "Pause on PRI/Upgrade", "CONNECT")

        def filter(self, record):
            try:
                if record.exc_info and record.exc_info[0]:
                    if record.exc_info[0].__name__ == "BadHttpMessage":
                        return False
                msg = record.getMessage()
                return not any(n in msg for n in self._noise)
            except Exception:
                return True

    for name in ("aiohttp.access", "aiohttp.server", "aiohttp.web_protocol"):
        logging.getLogger(name).addFilter(_ScannerNoiseFilter())

    # ---- Capture unhandled exceptions -------------------------------------
    def _excepthook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        root.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_tb))

    sys.excepthook = _excepthook


# ---------------------------------------------------------------------------
# BotLogger — lightweight structured logger
# ---------------------------------------------------------------------------

class BotLogger:
    """Structured logger for bot operations."""

    def __init__(self, name: str):
        self.logger = logging.getLogger(name)

    def _fmt(self, message: str, context: dict) -> str:
        if not context:
            return message
        # compact key=value instead of bulky JSON
        pairs = "  ".join(f"{k}={v}" for k, v in context.items() if v is not None)
        return f"{message}  ({pairs})" if pairs else message

    # public API
    def debug(self, message: str, **ctx):
        self.logger.debug(self._fmt(message, ctx))

    def info(self, message: str, **ctx):
        self.logger.info(self._fmt(message, ctx))

    def warning(self, message: str, **ctx):
        self.logger.warning(self._fmt(message, ctx))

    def error(self, message: str, **ctx):
        self.logger.error(self._fmt(message, ctx))

    def critical(self, message: str, **ctx):
        self.logger.critical(self._fmt(message, ctx))


# Global instance
bot_logger = BotLogger("BOT")


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------

def log_user_action(action: str, user_id: Optional[int] = None, chat_id: Optional[int] = None, **kw):
    """Log a user action (DEBUG level — file only, never console)."""
    bot_logger.debug(f"action: {action}", user_id=user_id, chat_id=chat_id, **kw)


def log_error(error: Exception, context: Optional[Dict[str, Any]] = None, user_id: Optional[int] = None):
    """Log an error with stack trace."""
    ctx = {
        "error": f"{type(error).__name__}: {error}",
        "user_id": user_id,
        **(context or {}),
    }
    bot_logger.error(f"Error: {error}", **ctx)
    # full traceback goes to file at DEBUG so it's there when needed
    bot_logger.debug(f"Traceback:\n{traceback.format_exc()}")


def log_performance(operation: str, duration: float, **kw):
    """Log performance (DEBUG — only visible in file)."""
    bot_logger.debug(f"perf: {operation} {duration*1000:.0f}ms", **kw)


def log_database_operation(operation: str, table: str, success: bool, duration: float = None, **kw):
    """Log a database operation."""
    ms = f"{duration*1000:.0f}ms" if duration else ""
    if success:
        bot_logger.debug(f"db {operation} {table} OK {ms}", **kw)
    else:
        bot_logger.error(f"db {operation} {table} FAIL {ms}", **kw)


def log_api_call(service: str, endpoint: str, success: bool, duration: float = None, **kw):
    """Log an external API call."""
    ms = f"{duration*1000:.0f}ms" if duration else ""
    if success:
        bot_logger.debug(f"api {service} {endpoint} OK {ms}", **kw)
    else:
        bot_logger.error(f"api {service} {endpoint} FAIL {ms}", **kw)


def log_job_execution(job_name: str, success: bool, duration: float = None, **kw):
    """Log background job execution."""
    ms = f"{duration*1000:.0f}ms" if duration else ""
    if success:
        bot_logger.debug(f"job {job_name} OK {ms}", **kw)
    else:
        bot_logger.error(f"job {job_name} FAIL {ms}", **kw)


# ---------------------------------------------------------------------------
# Rate-limit / spam logging
# ---------------------------------------------------------------------------

def log_rate_limit_violation(user_id: int, action: str, limit: int, window: int):
    bot_logger.warning(f"Rate-limit hit", user_id=user_id, action=action, limit=limit, window=window)


def log_spam_detection(user_id: int, message_count: int, window: int):
    bot_logger.warning(f"Spam detected", user_id=user_id, messages=message_count, window=window)


# ---------------------------------------------------------------------------
# Decorators
# ---------------------------------------------------------------------------

def handle_errors(func):
    """Decorator: catch + log errors in async handlers."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            log_error(e, {"function": func.__name__})
            raise
    return wrapper


def handle_sync_errors(func):
    """Decorator: catch + log errors in sync functions."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            log_error(e, {"function": func.__name__})
            raise
    return wrapper


@asynccontextmanager
async def error_context(operation: str, user_id: Optional[int] = None, **context):
    """Context manager for error handling with automatic logging."""
    try:
        yield
    except Exception as e:
        log_error(e, {"operation": operation, "user_id": user_id, **context})
        raise


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class DatabaseError(Exception):
    """Custom database error."""
    pass

class ValidationError(Exception):
    """Custom validation error."""
    pass

class PasarGuardError(Exception):
    """Custom PasarGuard API error."""
    pass


def safe_database_operation(func):
    """Decorator for safe database operations with automatic rollback."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        session = None
        for arg in args:
            if hasattr(arg, 'commit') and hasattr(arg, 'rollback'):
                session = arg
                break
        if not session:
            for value in kwargs.values():
                if hasattr(value, 'commit') and hasattr(value, 'rollback'):
                    session = value
                    break
        try:
            result = await func(*args, **kwargs)
            if session:
                await session.commit()
            return result
        except Exception as e:
            if session:
                await session.rollback()
            log_error(e, {"operation": "database", "function": func.__name__})
            raise DatabaseError(f"Database operation failed: {e}")
    return wrapper
