# ASTROBYTE — Refactor Plan
*Last updated: 2026-05-28*

---

## Rules (non-negotiable)

- No feature removal. Every handler, route, job must keep working.
- No behavior changes. Users and admins must see identical results.
- Backup before every phase: `bash scripts/backup_snapshot.sh <label>`
- After every phase, verify both entry points import cleanly:
  ```bash
  PYTHONPATH=src .venv/bin/python -c "import app.main; import app.admin_main; print('OK')"
  ```
- No DB model renames without an Alembic migration.

---

## Commands

```bash
# Run
cd /root/5a06b8e65bdb/ASTROBYTE/src
python -m app.main          # user bot + web server (port 8585)
python -m app.admin_main    # admin bot

# Production
systemctl restart userbot.service adminbot.service
journalctl -u userbot.service -f

# Snapshot / restore
bash scripts/backup_snapshot.sh <label>
bash scripts/restore_snapshot.sh backups/<file>.tar.gz

# Lint (install ruff first: .venv/bin/pip install ruff)
.venv/bin/ruff check src/app
.venv/bin/ruff check --fix --select I,F401 src/app   # safe auto-fix only
```

## Manual verification (no test suite)

| Check | Command |
|---|---|
| Both bots import | `PYTHONPATH=src .venv/bin/python -c "import app.main; import app.admin_main; print('OK')"` |
| Health endpoint | `curl http://127.0.0.1:8585/health` |
| Admin login | `python scripts/root/test_login.py` |
| DB connectivity | `python scripts/root/test_postgresql_connection.py` |

---

## Current Project Structure

```
ASTROBYTE/
├── src/app/
│   ├── main.py                  ← user bot entry + webserver (421 lines)
│   ├── admin_main.py            ← admin bot entry (177 lines) — imports handlers/admin directly
│   ├── webserver.py             ← thin shim → api/main.py
│   │
│   ├── api/                     ← aiohttp web layer
│   │   ├── main.py              ← app factory, middleware chain
│   │   ├── deps.py              ← shared auth helpers
│   │   ├── http_middleware.py
│   │   ├── rate_limiter.py
│   │   ├── schemas/             ← Pydantic schemas (10 files)
│   │   ├── route_registry/      ← registers routes into aiohttp (6 sub-packages)
│   │   └── routes/              ← 176 .py files grouped by domain
│   │       ├── admin/           ← users, subs, receipts, tickets, messaging
│   │       ├── admin_auth/      ← login, 2FA, sessions
│   │       ├── admin_db/        ← raw SQL explorer
│   │       ├── admin_ui/        ← UI settings, bg upload
│   │       ├── admin_ws/        ← WebSocket: ticket updates, presence
│   │       ├── dashboard/       ← referrals, star rewards, VIP, wallet
│   │       ├── dashboard_charge/
│   │       ├── dashboard_purchase/
│   │       ├── dashboard_subs/
│   │       ├── dashboard_tickets/
│   │       ├── game/            ← arcade submit, leaderboard
│   │       └── health/
│   │
│   ├── core/settings/           ← 10 config modules (dotenv + overrides)
│   ├── database/
│   │   ├── models.py            ← all SQLAlchemy models (1074 lines) ⚠️
│   │   ├── crud.py              ← flat re-export facade over repos (198 lines)
│   │   ├── cached_crud.py       ← Redis-cached wrappers (469 lines)
│   │   ├── notifications_crud.py
│   │   ├── indexes.py           (750 lines)
│   │   └── repos/               ← UserRepo, SubscriptionRepo, TicketRepo, RewardRepo...
│   │
│   ├── handlers/
│   │   ├── admin/               ← admin Telegram handlers (real code, 134 files)
│   │   └── user/                ← user Telegram handlers
│   │
│   ├── jobs/                    ← 6 APScheduler jobs
│   ├── services/
│   │   ├── marzban.py           ← Marzban VPN API client (542 lines) ⚠️
│   │   └── subscription_processing.py
│   ├── utils/
│   └── webapp/                  ← FRONTEND (HTML/CSS/JS)
│       ├── admin/               ← Admin panel SPA
│       ├── arcade/              ← AstroBugz game
│       ├── dashboard/           ← User dashboard SPA  ← MAIN REFACTOR TARGET
│       ├── profile/             ← Dead: handler redirects to dashboard/profile.html
│       ├── tasks/               ← Standalone tasks page (served separately)
│       └── static/              ← shared SVG assets
│
├── alembic/versions/            ← 5 migrations (all applied)
├── config/.env                  ← secrets ⚠️
├── scripts/                     ← backup, restore, maintenance utilities
└── backups/                     ← snapshot archives
```

---

## Backend Refactor Status

| Phase | Description | Status |
|---|---|---|
| 1 | Delete dead files (legacy zip/HTML, .bak CSS, done migration scripts) | ✅ Done |
| 2 | Flatten `admin_bot/handlers/` shims → `admin_main.py` imports `handlers.admin` directly | ✅ Done |
| 3 | Merge `database/crud.py` into repos | ⛔ Skipped — 90+ callers, no test suite, low benefit |
| 4 | Move `src/app/scripts/` out of app package → `scripts/` | ✅ Done |

---

## Webapp — What's Wrong

### 1. CSS and JS inside `<main class="content">` — intentional, not a bug

`shop.html` and `tasks.html` load page-specific CSS and JS inside the `<main class="content">` div. This looks wrong but is **intentional**: `index.html` uses a shell-loading mechanism (`loadPageIntoShell`) that fetches the page, extracts just the `.content` element, and re-injects it. `<link>` and `<script>` tags inside `.content` travel with the content and get applied in the host page. Moving them to `<head>` would break shell navigation.

`tasks-page.js` is outside `.content` (end of `<body>`) — also intentional: it only runs when the page is opened standalone, not via shell.

**Status: no fix needed.**

---

### 2. Duplicated inline `<head>` boot scripts

`index.html` correctly uses `<script src="/webapp/dashboard/js/head-boot.js">` which handles:
- `?auth=` token stashing
- Telegram security check (blocks non-Telegram access)
- Theme / accent / lang flash prevention
- Telegram `ready()` / `expand()` / fullscreen

Every other page has its own **inline version** of parts of this logic, written separately:

| File | Head lines | What's inline |
|---|---|---|
| `index.html` | 16 | Uses `head-boot.js` ✅ |
| `purchase.html` | ~103 | Theme/lang/accent IIFE, `data-boot` attr, console filter, `?auth=` stash |
| `charge.html` | ~100 | Same as purchase |
| `tasks.html` | ~80 | Theme/lang/accent IIFE, `data-boot` attr, console filter |
| `shop.html` | ~78 | Theme/lang/accent IIFE, `data-boot` attr, console filter |
| `support.html` | ~39 | Minimal inline boot |
| `profile.html` | ~8 | Almost none |

These inline scripts are **duplicated logic** that already lives in `head-boot.js`. If the boot behavior needs to change, it must be changed in 6 places instead of 1.

**Fix:** Replace the inline boot scripts with `<script src="/webapp/dashboard/js/head-boot.js"></script>` on all pages, exactly like `index.html` does. Verify the Telegram console filter (not in head-boot.js) is added there once if needed.

---

### 3. `lang.js` loaded inconsistently

`lang.js` handles cross-device language sync. It's missing from some pages:

| File | Loads lang.js? |
|---|---|
| `index.html` | ❌ No |
| `purchase.html` | ✅ Yes |
| `charge.html` | ✅ Yes |
| `tasks.html` | ✅ Yes |
| `shop.html` | ✅ Yes |
| `support.html` | ❌ No |
| `profile.html` | ❌ No |

If the language is supposed to be consistent across all pages, `lang.js` must load on all of them. Either all load it or none do (if `index-main.js` / `profile-main.js` already handles it).

**Fix:** Audit whether `index.html` and `profile.html` load lang via their JS bundle. Add `lang.js` to any page that doesn't already apply it. Load order: `lang.js` → `head-boot.js` → Telegram SDK → page JS.

---

### 4. Inconsistent font loading

All pages load the same Vazirmatn font from jsDelivr CDN, but inconsistently:

| File | `preconnect` tags? | Extra attributes? |
|---|---|---|
| `index.html` | ❌ No preconnect | None |
| `purchase.html` | ✅ googleapis + gstatic | None |
| `charge.html` | ✅ googleapis + gstatic | None |
| `support.html` | ✅ googleapis + gstatic + jsdelivr | `crossorigin="anonymous" referrerpolicy="no-referrer"` |
| `shop.html` | ✅ googleapis + gstatic | None |
| `tasks.html` | ✅ googleapis + gstatic | None |
| `profile.html` | ❌ No preconnect | None |

The `preconnect` hints to googleapis/gstatic are unnecessary for a jsDelivr-hosted font — those are Google Fonts preconnects, not jsDelivr ones. `support.html` adds `referrerpolicy="no-referrer"` on the font which the others don't have (inconsistent, probably harmless).

**Fix:** Use identical font tag on every page. Remove the wrong googleapis/gstatic preconnect. The jsDelivr link is the one that matters.

---

### 5. Dead file: `webapp/profile/index.html`

The route handler for `/webapp/profile` does an HTTP redirect directly to `/webapp/dashboard/profile.html`. The file `webapp/profile/index.html` (423 lines) is **never served**.

**Fix:** Delete `webapp/profile/index.html` and the entire `webapp/profile/` directory.

---

### 6. Older standalone `webapp/tasks/index.html`

`/webapp/tasks` serves `webapp/tasks/index.html` (423 lines), a separate older version of the tasks page. The current tasks page is `dashboard/tasks.html` (508 lines). These two files are different and both served, but the bot likely only links to one.

**Fix:** Confirm which URL the bot sends users to. If only `dashboard/tasks.html` is used, delete `webapp/tasks/` entirely and remove its route registration.

---

### 7. Missing `lang="en"` on `index.html`

All newer pages have `<html lang="en">`. `index.html` has `<html>` with no lang attribute.

**Fix:** Add `lang="en"` to `index.html`.

---

## Webapp Refactor Order

### Phase W1 — ✅ Cancelled (not a bug)
CSS/JS inside `.content` is intentional shell-loading architecture. No change needed.

---

### Phase W2 — Delete dead `webapp/profile/` directory
`webapp/profile/index.html` is never served (route redirects to dashboard/profile.html).

```bash
bash scripts/backup_snapshot.sh before-delete-profile-dir
rm -rf src/app/webapp/profile/
```

**Verify:** `/webapp/profile` URL still redirects to `/webapp/dashboard/profile.html` (the Python route handler does the redirect, not the file).

---

### Phase W3 — Consolidate head boot scripts
Replace inline boot scripts on purchase, charge, support, shop, tasks, profile with:
```html
<script src="/webapp/dashboard/js/head-boot.js"></script>
```
Do this **one file at a time**. After each file, open the page in Telegram and confirm it loads correctly. If any inline script does something head-boot.js doesn't (e.g. the console filter), add it to head-boot.js first.

**Order:** support → profile → charge → purchase → shop → tasks

---

### Phase W4 — Standardize font tag + add lang.js where missing
Replace all font `<link>` tags with one consistent version across all pages. Add `lang.js` to pages missing it. Add `lang="en"` to `index.html`.

---

### Phase W5 — Audit/delete `webapp/tasks/` standalone page
Check bot source for which URL it sends to tasks. If only `dashboard/tasks.html` is used, delete `webapp/tasks/index.html` and remove its route from `route_registry/dashboard_web/`.

---

## Risky Modules — Do Not Touch

| File | Why |
|---|---|
| `services/marzban.py` | External VPN API, real money, JWT lock |
| `api/routes/admin/receipts/` | Payment approval triggers Marzban user creation |
| `api/routes/admin_auth/` | Argon2 + 2FA — break = admin locked out |
| `jobs/renewal.py` | Auto-renewal charges real users |
| `database/models.py` | Any change needs Alembic migration |
| `main.py` startup sequence | Scheduler + webserver init order is fragile |
| `utils/webapp_verify.py` | Telegram initData HMAC — break = dashboard locked out |

---

## What Will NOT Be Refactored

- `database/crud.py` — 90+ callers, stable facade, no bugs
- `api/routes/` nesting — consistent pattern, flattening = massive churn
- `database/models.py` — any rename needs a migration
- `core/settings/` split — works, intentional
- Arcade game files — compiled Construct2 output, not hand-written
