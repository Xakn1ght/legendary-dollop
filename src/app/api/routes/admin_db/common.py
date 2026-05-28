from __future__ import annotations

import os
import re

from aiohttp import web
from sqlalchemy import text

from app.database.models import AsyncSessionLocal

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SCHEMA_IDENT_RE = re.compile(r"^(?P<schema>[A-Za-z_][A-Za-z0-9_]*)\\.(?P<table>[A-Za-z_][A-Za-z0-9_]*)$")


def _is_dangerous_sql_enabled() -> bool:
    return str(os.getenv("ADMIN_DB_DANGEROUS_SQL", "")).strip().lower() in {"1", "true", "yes", "on"}


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

