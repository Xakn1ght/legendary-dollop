# AstroBytes — Developer Guide

A practical reference for working on this project day to day.

---

## Running the bots

```bash
# Development (run in separate terminals)
cd /root/5a06b8e65bdb/ASTROBYTE/src
python -m app.main          # user bot + web server (port 8585)
python -m app.admin_main    # admin bot
```

```bash
# Production
systemctl restart userbot.service adminbot.service
systemctl status userbot.service adminbot.service
journalctl -u userbot.service -f      # live logs
journalctl -u adminbot.service -f
```

---

## Git — daily workflow

```bash
# Check what changed
git status
git diff src/app/some_file.py

# Stage + commit + push
git add -A
git commit -m "describe what you did"
git push

# See commit history
git log --oneline

# Undo changes to a file (before committing)
git checkout -- src/app/some_file.py
```

> The `.env` file is in `.gitignore` — it is never pushed to GitHub. Keep a separate backup of it.

---

## Backups & restore

```bash
# Create a snapshot before risky changes
bash scripts/backup_snapshot.sh my-label

# List all snapshots
bash scripts/list_snapshots.sh

# Restore latest snapshot
RESTORE_OK=yes bash scripts/restore_snapshot.sh backups/LATEST.tar.gz

# Restore a specific snapshot
RESTORE_OK=yes bash scripts/restore_snapshot.sh backups/snapshot-20260528-before-change.tar.gz
```

Snapshots are stored in `backups/`. The 25 most recent are kept automatically.

---

## Database migrations (Alembic)

Run these from the project root (`/root/5a06b8e65bdb/ASTROBYTE`).

```bash
# Check current migration state
PYTHONPATH=src alembic -c config/alembic.ini current

# Create a new migration after changing a model
PYTHONPATH=src alembic -c config/alembic.ini revision --autogenerate -m "add column xyz"

# Apply all pending migrations
PYTHONPATH=src alembic -c config/alembic.ini upgrade head

# Roll back one migration
PYTHONPATH=src alembic -c config/alembic.ini downgrade -1
```

> Always run `upgrade head` after pulling new code that includes migrations.

---

## Health check

```bash
curl http://localhost:8585/health
```

Returns status for: database, Redis, Marzban, bot, scheduler.

---

## Common tasks

### Add a subscription plan
Edit `src/app/core/plans.json`.

### Change charge packages
Edit `src/app/core/charge_packages.json` or `src/app/core/settings/catalog_plans.py`.

### Add a Telegram handler (user bot)
Create a file in `src/app/handlers/user/` and register the router in `src/app/main.py`.

### Add a Telegram handler (admin bot)
Create a file in `src/app/handlers/admin/` and register the router in `src/app/admin_main.py`.

### Add an API route
1. Create handler in `src/app/api/routes/<domain>/`
2. Register it in the matching `src/app/api/route_registry/` file

### Change a job schedule
Edit `JOB_SCHEDULES` in `src/app/core/settings/bot_behavior.py`.

### Change a DB model
1. Edit the relevant model file in `src/app/database/models/`
2. Create a migration: `alembic revision --autogenerate -m "description"`
3. Apply it: `alembic upgrade head`
4. Restart services

### Generate a new admin panel password
```bash
python scripts/root/generate_admin_password.py
# Copy the hash into config/.env → ADMIN_PANEL_PASSWORD_HASH
```

---

## Project structure (quick reference)

```
src/app/
├── main.py                  ← user bot entry + web server
├── admin_main.py            ← admin bot entry
├── api/routes/              ← web API handlers (~180 files)
├── handlers/
│   ├── admin/               ← admin Telegram handlers
│   └── user/                ← user Telegram handlers
├── database/
│   ├── models/              ← SQLAlchemy models (split by domain)
│   ├── crud.py              ← flat function exports (used everywhere)
│   ├── cached_crud.py       ← Redis-cached wrappers
│   └── repos/               ← domain repositories
├── jobs/                    ← background jobs (APScheduler)
├── services/marzban.py      ← Marzban VPN API client ⚠️ don't break this
├── core/settings/           ← all config, loaded from config/.env
├── utils/                   ← logging, i18n, middleware, helpers
└── webapp/                  ← frontend HTML/CSS/JS
    ├── admin/               ← admin panel SPA
    ├── arcade/              ← AstroBugz game
    └── dashboard/           ← user dashboard SPA
```

---

## Dangerous files — be careful

| File | Why |
|---|---|
| `services/marzban.py` | Talks to live VPN panel. Breaks = no subscriptions work |
| `api/routes/admin/receipts/` | Payment approval. Breaks = money issues |
| `api/routes/admin_auth/` | Admin login. Breaks = locked out of panel |
| `jobs/renewal.py` | Auto-charges users. Breaks = renewals stop |
| `database/models/` | Any change needs a migration or data breaks |
| `config/.env` | Secrets. Never commit, never share |

---

## Environment variables (config/.env)

| Variable | What it is |
|---|---|
| `BOT_TOKEN` | User bot token (from @BotFather) |
| `ADMIN_BOT_TOKEN` | Admin bot token |
| `ADMIN_ID` | Your Telegram user ID |
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_HOST` / `REDIS_PORT` / `REDIS_PASSWORD` | Redis connection |
| `MARZBAN_BASE_URL` | Your Marzban panel URL |
| `MARZBAN_USERNAME` / `MARZBAN_PASSWORD` | Marzban admin credentials |
| `DASHBOARD_PUBLIC_BASE_URL` | Public URL where the web dashboard is served |
| `GAME_WEBAPP_HOST` / `GAME_WEBAPP_PORT` | Web server bind address (default 8585) |
| `ADMIN_PANEL_PASSWORD_HASH` | Argon2 hash of admin panel password |
| `ADMIN_PANEL_SECRET_KEY` | Random secret for session signing |
| `ADMIN_2FA_ENABLED` | `true` / `false` |
| `PAYMENT_CARD_NUMBER` / `PAYMENT_CARD_HOLDER` | Shown to users during purchase |

---

## Lint

```bash
# Install once
.venv/bin/pip install ruff

# Check for issues
.venv/bin/ruff check src/app

# Auto-fix safe issues (import sorting etc.)
.venv/bin/ruff check --fix --select I,F401 src/app
```

---

## Verify everything works

```bash
# Both bots import without errors
PYTHONPATH=src .venv/bin/python -c "import app.main; import app.admin_main; print('OK')"

# Health check
curl http://localhost:8585/health
```
