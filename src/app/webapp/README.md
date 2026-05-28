# WebApp Structure (Canonical vs Legacy)

This folder contains all Telegram WebApp / browser UI files served by the embedded aiohttp server (`app/api/main.py`).

## Canonical (LIVE)

### Admin panel
- **Shell**: `app/webapp/admin/index.html` (served at `/admin/*`)
- **Support page**: `app/webapp/admin/support.html` (served at `/admin/support`)
- **Theme**: `app/webapp/admin/admin.css`

### User dashboard
- **Main**: `app/webapp/dashboard/index.html` (served at `/webapp/dashboard`)
- **Support**: `app/webapp/dashboard/support.html` (served at `/webapp/dashboard/support`)
- **Purchase**: `app/webapp/dashboard/purchase.html`

### Arcade
- **Main**: `app/webapp/arcade/index.html` (served at `/webapp/arcade`)

## Legacy (kept for rollback/debug)

Admin v1/v2/v3 legacy files are stored under:
- `app/webapp/admin/legacy/`

The original filenames (like `admin_v1.css`, `index_v2.html`, etc.) still exist as **symlinks** in `app/webapp/admin/` so existing URLs and route file paths keep working.


