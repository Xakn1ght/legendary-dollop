"""Admin DB explorer API (split from former routes/admin_db.py)."""

from app.api.routes.admin_db.browse import (
    handle_admin_db_capabilities,
    handle_admin_db_table_schema,
    handle_admin_db_tables,
)
from app.api.routes.admin_db.data import (
    handle_admin_db_exec,
    handle_admin_db_query,
    handle_admin_db_table_rows,
)

__all__ = [
    "handle_admin_db_capabilities",
    "handle_admin_db_exec",
    "handle_admin_db_query",
    "handle_admin_db_table_rows",
    "handle_admin_db_table_schema",
    "handle_admin_db_tables",
]
