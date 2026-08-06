from __future__ import annotations

import base64
import datetime as _dt
import decimal
import os
import re
import uuid

from aiohttp import web


def _json_safe(value):
    """Coerce a DB cell into something json.dumps can handle.

    Raw rows carry datetime/Decimal/UUID/bytes/memoryview values that aiohttp's
    json_response can't serialize → uncaught TypeError = 500 on nearly every
    real table (audit fix). Everything JSON-native passes through untouched.
    """
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, (_dt.datetime, _dt.date, _dt.time)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        try:
            return bytes(value).decode("utf-8")
        except Exception:
            return base64.b64encode(bytes(value)).decode("ascii")
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    return str(value)

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SCHEMA_IDENT_RE = re.compile(r"^(?P<schema>[A-Za-z_][A-Za-z0-9_]*)\.(?P<table>[A-Za-z_][A-Za-z0-9_]*)$")


def _is_dangerous_sql_enabled() -> bool:
    return str(os.getenv("ADMIN_DB_DANGEROUS_SQL", "")).strip().lower() in {"1", "true", "yes", "on"}


def _is_sql_runner_enabled() -> bool:
    """Kill switch for the free-text SQL runner (query AND exec). Default OFF."""
    from app.core.settings.security import ADMIN_DB_SQL_ENABLED

    return bool(ADMIN_DB_SQL_ENABLED)


def _sql_disabled_response() -> web.Response:
    """404 as if the endpoint does not exist — no hint that a flag would enable it."""
    return web.json_response({"ok": False, "error": "disabled"}, status=404)


def _validate_table_name(name: str) -> tuple[str, str | None]:
    """
    Accept:
      - table
      - schema.table
    Return (table, schema) where schema may be None.
    """
    name = (name or "").strip()
    if not name:
        raise ValueError("missing_table")
    m = _SCHEMA_IDENT_RE.match(name)
    if m:
        return m.group("table"), m.group("schema")
    if _IDENT_RE.match(name):
        return name, None
    raise ValueError("invalid_table")


def _is_read_only_sql(sql: str) -> bool:
    s = (sql or "").strip().lower()
    if not s:
        return False
    if ";" in s:
        return False
    # Very conservative: allow SELECT and WITH ... SELECT only
    if s.startswith("select"):
        return True
    if s.startswith("with"):
        # This is naive, but still blocks obvious writes
        return True
    if s.startswith("explain"):
        # allow EXPLAIN (no ANALYZE) by default
        return "analyze" not in s
    return False

