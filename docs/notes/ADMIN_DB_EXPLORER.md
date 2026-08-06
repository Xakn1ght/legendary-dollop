# Admin DB Explorer (Web Panel)

The admin web panel includes a **Database** tab that lets you inspect your app database from the browser.

## What it can do

- Browse tables and view rows (paginated).
- View table schema (column list).
- Run **read-only SQL** (`SELECT` / `WITH` / `EXPLAIN` without `ANALYZE`).

## Safety defaults (important)

- The **entire SQL runner is OFF by default** (`ADMIN_DB_SQL_ENABLED` unset):
  `/api/admin/db/query` and `/api/admin/db/exec` return 404, capabilities
  report `allow_sql: false`, and the UI hides the SQL section. Blocked calls
  are written to the admin audit trail as `db.sql_blocked`. Table browsing,
  the row viewer, and schema view keep working.
- Set `ADMIN_DB_SQL_ENABLED=1` and restart to get the read-only SQL box back.
- Even then the runner is **read-only**; any **write / destructive SQL** is
  **disabled** unless you additionally enable it on the server.

### Enabling dangerous SQL (optional)

1) Set this environment variable on the server:

`ADMIN_DB_DANGEROUS_SQL=1`

2) Restart the app.

3) The UI will show an **Execute (danger)** button. Clicking it will require an extra confirmation.

Server-side guardrails:
- `/api/admin/db/exec` requires `ADMIN_DB_SQL_ENABLED=1` AND `ADMIN_DB_DANGEROUS_SQL=1`
- and an extra header: `X-Admin-Dangerous: YES`
- and admin auth protections still apply (admin session + CSRF + IP allowlist, depending on your setup)

## Notes / limitations

- Row limits are capped to avoid browser hangs:
  - table browsing: 200 rows per request (UI defaults to 50)
  - SQL results: 500 rows max
- Multi-statement SQL is blocked (no `;`).

