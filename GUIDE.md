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

# See what's on GitHub vs local
git status   # shows "ahead by N commits" if unpushed

# Undo changes to a file (before committing)
git checkout -- src/app/some_file.py

# Go back to what's on GitHub (nuclear — discards all local changes)
git reset --hard origin/main
```

> The `.env` file is in `.gitignore` — it is never pushed to GitHub. Keep a separate backup of it.

---

## Backups & restore

### Snapshot (full project backup)

```bash
# Create a snapshot before risky changes
bash scripts/backup_snapshot.sh my-label

# List all snapshots
bash scripts/list_snapshots.sh

# Restore latest snapshot
RESTORE_OK=yes bash scripts/restore_snapshot.sh backups/LATEST.tar.gz

# Restore a specific snapshot
RESTORE_OK=yes bash scripts/restore_snapshot.sh backups/snapshot-20260528-my-label.tar.gz
```

Snapshots live in `backups/`. The 25 most recent are kept automatically.

### Git as a restore point

Every push to GitHub is a permanent restore point.

```bash
# See all commits (most recent first)
git log --oneline

# Restore all files to a specific commit (non-destructive — leaves history intact)
git checkout abc1234 -- .

# Hard reset to a specific commit (destructive — rewrites history)
git reset --hard abc1234

# Hard reset to whatever is on GitHub right now
git reset --hard origin/main
```

### Recommended before any big change

```bash
# 1. Snapshot (local safety net)
bash scripts/backup_snapshot.sh before-my-change

# 2. Commit current state if anything is uncommitted
git add -A && git commit -m "checkpoint before my-change"

# 3. Push (permanent GitHub restore point)
git push
```

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

## How the system works

### Two bots, one web server

- **User bot** (`main.py`) — the bot your customers talk to. It also starts the embedded aiohttp web server on port 8585 that serves the dashboard, admin panel, and arcade game.
- **Admin bot** (`admin_main.py`) — a separate bot only you can use. Handles approvals, broadcasts, stats, system commands.
- Both bots share the same PostgreSQL database and Redis instance.

### Purchase flow (what happens when someone buys)

```
User picks plan in dashboard
  → POST /api/dashboard/purchase/start   (creates a draft order in DB)
  → User submits receipt photo
  → POST /api/dashboard/purchase/submit-receipt  (saves image, notifies admin bot)
  → Admin sees request in admin bot
  → Admin approves
  → POST /api/admin/receipts/{id}/approve
      → Creates Marzban user via marzban.py
      → Saves subscription to DB (status: active)
      → Sends sub link to user via Telegram
```

### Charge (top-up) flow

```
User selects subscription → picks GB/days package
  → POST /api/dashboard/charge/start
  → User submits receipt
  → Admin approves
  → POST /api/admin/charges/{id}/approve
      → Adds traffic/days to existing Marzban user
```

### Marzban integration

`services/marzban.py` is the only file that talks to Marzban. It uses JWT auth with a lock to prevent concurrent logins. Every call that creates/modifies a VPN user goes through here.

If Marzban is down: the health check will show it, approvals will fail gracefully, and errors are logged. Nothing else breaks.

### Notifications

Notifications to users go through an async queue (`notification_queue` in `main.py`). Nothing sends directly — everything is queued and a worker coroutine drains it. This prevents Telegram rate limiting.

### Redis

Used for:
- **FSM state** — Telegram conversation state (which step the user is at in a purchase flow etc.)
- **Caching** — user lookups, subscription data (`cached_crud.py`)
- **Session storage** — dashboard web sessions

If Redis goes down, the bot will keep running but FSM-based conversations (purchase, support ticket creation) will break until Redis is back.

---

## Frontend (webapp)

The dashboard and admin panel are static HTML/CSS/JS files served by the aiohttp web server. No build step — edit the files and refresh.

```
src/app/webapp/
├── dashboard/           ← User dashboard (Telegram Mini App)
│   ├── index.html       ← Home page (subscriptions, VPN card)
│   ├── purchase.html    ← Buy a plan
│   ├── charge.html      ← Top up data
│   ├── support.html     ← Support tickets
│   ├── shop.html        ← Rewards shop + VIP
│   ├── tasks.html       ← Rewards / challenges / achievements
│   ├── profile.html     ← User profile
│   ├── css/
│   │   ├── tokens.css   ← Design tokens (colors, spacing, shadows, accents)
│   │   ├── glass.css    ← Liquid glass system (loads last, overrides everything)
│   │   └── *.css        ← One CSS file per page
│   ├── js/
│   │   ├── head-boot.js ← Runs first: security check, theme, Telegram setup
│   │   ├── index-main.js← Home page JS
│   │   └── *.js         ← One JS file per page (where needed)
│   ├── ui.js            ← Shared UI utilities (toasts, sheets, haptics)
│   └── lang.js          ← Language / i18n system (fa/en, syncs to backend)
├── admin/               ← Admin panel SPA
│   ├── index.html       ← Main admin panel
│   └── support.html     ← Admin support view
└── arcade/              ← AstroBugz HTML5 game
    ├── index.html        ← Game launcher
    └── astrobugz/        ← Compiled Construct2 game files
```

### How pages load

Each dashboard page is both a **standalone page** (accessed directly) and a **shell-injectable page** (loaded into `index.html` via JS for soft navigation). This is why some CSS/JS lives inside the `.content` div — the shell extracts that div and re-injects it.

- **Head scripts** (`head-boot.js`): runs before anything renders. Applies theme, checks Telegram auth, sets up expand/fullscreen.
- **Page CSS**: imported via `@import url("tokens.css")` at the top of each CSS file.
- **`glass.css`**: always loaded last on every page. Overrides base styles with the liquid glass look using `!important`.

### CSS load order (important)

```
tokens.css  →  [page].css  →  glass.css
```

Don't fight `glass.css`. To override something, either edit `glass.css` directly or put your rule after it with `!important`.

### Cache busting

When you change a CSS or JS file and users aren't seeing the update, bump the version query string in the HTML:

```html
<!-- Change v=22 to v=23 -->
<link rel="stylesheet" href="/webapp/dashboard/css/glass.css?v=23">
<script src="/webapp/dashboard/js/index-main.js?v=15"></script>
```

### Adding a new dashboard page

1. Create `src/app/webapp/dashboard/mypage.html`
2. Head must include (in this order):
   ```html
   <script src="/webapp/dashboard/lang.js"></script>
   <script src="https://telegram.org/js/telegram-web-app.js"></script>
   <script src="/webapp/dashboard/js/head-boot.js"></script>
   <script src="/webapp/dashboard/ui.js" defer></script>
   ```
3. Create `src/app/webapp/dashboard/css/mypage.css` with `@import url("./tokens.css");` at the top
4. Add `<link rel="stylesheet" href="/webapp/dashboard/css/mypage.css">` and `glass.css` last
5. Register the route in `src/app/api/route_registry/dashboard_web/handlers.py` and `register.py`
6. Add a nav item in `index.html` bottom nav if needed

### i18n (Persian / English)

All user-facing text in the dashboard should support both languages. Use the translation system:

```javascript
// In page JS, use t('key') to get translated text
el.textContent = t('myKey');
```

Add the key to both `'fa'` and `'en'` objects inside `lang.js`.

---

## Common tasks

### Add a subscription plan
Edit `src/app/core/plans.json`.

### Change charge packages
Edit `src/app/core/charge_packages.json` or `src/app/core/settings/catalog_plans.py`.

### Add a Telegram command (user bot)

1. Create a handler file in `src/app/handlers/user/`
2. Define a `router = Router()` and decorate your functions with `@router.message(Command("mycommand"))`
3. Import and include the router in `src/app/main.py`:
   ```python
   from app.handlers.user import mymodule
   dp.include_router(mymodule.router)
   ```

### Add a Telegram command (admin bot)

Same pattern but in `src/app/handlers/admin/` and registered in `src/app/admin_main.py`.

### Add an API route

1. Create handler in `src/app/api/routes/<domain>/myroute.py`
2. Define an async function: `async def handle_my_route(request: web.Request):`
3. Register it in `src/app/api/route_registry/<domain>/register.py`:
   ```python
   app.router.add_post("/api/my/endpoint", handle_my_route)
   ```

### Change a job schedule
Edit `JOB_SCHEDULES` in `src/app/core/settings/bot_behavior.py`.

### Change a DB model
1. Edit the relevant file in `src/app/database/models/`
2. Create a migration: `alembic revision --autogenerate -m "description"`
3. Apply it: `alembic upgrade head`
4. Restart services

### Generate a new admin panel password
```bash
python scripts/root/generate_admin_password.py
# Copy the hash into config/.env → ADMIN_PANEL_PASSWORD_HASH
systemctl restart userbot.service
```

### Clear Redis cache
```bash
redis-cli -h 127.0.0.1 FLUSHDB
systemctl restart userbot.service
```

### Force-refresh a user's subscription from Marzban
Use the admin bot → find user → "Sync from Marzban", or via admin panel → Subscriptions → Sync.

### Check what's using port 8585
```bash
ss -tlnp | grep 8585
```

### Update Python packages
```bash
cd /root/5a06b8e65bdb/ASTROBYTE
source .venv/bin/activate
pip install -r config/requirements.txt --upgrade
# Test before restarting
PYTHONPATH=src python -c "import app.main; print('OK')"
systemctl restart userbot.service adminbot.service
```

---

## Reward system — how it works

Users earn **stars** through referrals, achievements, and the arcade game. Stars accumulate and unlock **star reward tiers** (milestones) that grant discounts, credit, or extra days.

- **Star pieces**: 10 pieces = 1 star. Arcade game gives pieces.
- **Monthly star cap**: users can earn max 6 stars/month from the arcade to prevent farming.
- **Daily cap**: max 3 stars/day from any source.
- **XP**: earned from most actions. XP → levels → loyalty point/credit rewards at each level.
- **Loyalty points**: spendable in the rewards shop.
- **Achievements**: one-time milestones (5 referrals, 50GB used, etc.).
- **Challenges**: daily/weekly goals that reset automatically.

Configuration: `src/app/core/settings/bot_behavior.py` (caps, rates), DB table `reward_config` (cashback %s).

---

## Admin panel — what each section does

Access: your `DASHBOARD_PUBLIC_BASE_URL/admin`

| Section | What it does |
|---|---|
| **Dashboard** | Overview stats — users, revenue, active subs |
| **Users** | Search, view, edit any user. Adjust credit/stars/ban |
| **Subscriptions** | View all subs, sync with Marzban, extend/delete |
| **Receipts** | Approve or deny pending purchase receipts |
| **Charges** | Approve or deny pending top-up receipts |
| **VIP** | Approve VIP membership orders |
| **Tickets** | Support ticket queue. Assign, reply, close |
| **Broadcast** | Send a message to all users or a filtered subset |
| **Financial** | Revenue charts, cashout requests |
| **Reward settings** | Configure star tier rewards |
| **DB Explorer** | Run raw SQL queries — be careful |
| **System** | View logs, restart services, run admin commands |
| **Settings** | IP whitelist, payment info, job schedules |

---

## Logs — reading them

```bash
# Live stream
journalctl -u userbot.service -f

# Last 100 lines
journalctl -u userbot.service -n 100

# Since last restart
journalctl -u userbot.service -b

# Search for errors
journalctl -u userbot.service | grep ERROR

# Log files (also written to disk)
tail -f /root/5a06b8e65bdb/ASTROBYTE/logs/bot.log
tail -f /root/5a06b8e65bdb/ASTROBYTE/logs/bot_error.log
tail -f /root/5a06b8e65bdb/ASTROBYTE/logs/admin_bot.log
```

Common log patterns:
- `[MARZBAN]` — Marzban API calls
- `[STAR_MANAGER]` — star additions/deductions
- `[RENEWAL]` — auto-renewal job
- `ERROR` — something went wrong (check the traceback below it)

---

## Project structure (quick reference)

```
ASTROBYTE/
├── src/app/
│   ├── main.py                  ← user bot entry + web server
│   ├── admin_main.py            ← admin bot entry
│   ├── api/routes/              ← web API handlers (~180 files)
│   ├── handlers/
│   │   ├── admin/               ← admin Telegram handlers
│   │   └── user/                ← user Telegram handlers
│   ├── database/
│   │   ├── models/              ← SQLAlchemy models (split by domain)
│   │   ├── crud.py              ← flat function exports (used everywhere)
│   │   ├── cached_crud.py       ← Redis-cached wrappers
│   │   └── repos/               ← domain repositories
│   ├── jobs/                    ← background jobs (APScheduler)
│   ├── services/marzban.py      ← Marzban VPN API client ⚠️
│   ├── core/settings/           ← all config, loaded from config/.env
│   ├── utils/                   ← logging, i18n, middleware, helpers
│   └── webapp/                  ← frontend HTML/CSS/JS
│       ├── admin/               ← admin panel SPA
│       ├── arcade/              ← AstroBugz game
│       └── dashboard/           ← user dashboard SPA
├── alembic/versions/            ← DB migration files
├── config/
│   ├── .env                     ← secrets (never committed)
│   ├── .env.example             ← template
│   └── requirements.txt
├── scripts/                     ← backup, restore, maintenance
├── backups/                     ← snapshot archives (never committed)
├── GUIDE.md                     ← this file
└── README.md                    ← project overview
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

## Moving to a new server

1. On new server, install Python 3.10+, PostgreSQL, Redis
2. Clone from GitHub: `git clone git@github.com:Xakn1ght/legendary-dollop.git ASTROBYTE`
3. Copy `config/.env` from old server (never in git)
4. Set up venv and install deps:
   ```bash
   python -m venv .venv && source .venv/bin/activate
   pip install -r config/requirements.txt && pip install -e .
   ```
5. Run migrations: `PYTHONPATH=src alembic -c config/alembic.ini upgrade head`
6. Copy service files and enable: `cp *.service /etc/systemd/system/ && systemctl enable userbot adminbot`
7. Restore DB from backup if needed: `python scripts/backup_db.py` (run on old server first)
8. Add new server's SSH key to GitHub (see `ssh-keygen -t ed25519` instructions)

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

---

## Troubleshooting

### Bot not responding
```bash
systemctl status userbot.service
journalctl -u userbot.service -n 50
```

### Web dashboard not loading
```bash
curl http://localhost:8585/health
ss -tlnp | grep 8585   # confirm server is up
```

### Dashboard shows "Access Restricted"
The page is being opened outside of Telegram (e.g. directly in a browser). This is expected — the dashboard only works inside the Telegram Mini App. Use `?auth=...` token flow for testing outside Telegram.

### Database connection error
```bash
systemctl status postgresql
python scripts/root/test_postgresql_connection.py
```

### Users not seeing CSS/JS changes
Bump the version query string in the relevant HTML file:
```html
<link rel="stylesheet" href="/webapp/dashboard/css/glass.css?v=23">
```

### Redis errors
```bash
systemctl status redis-server
redis-cli ping   # should return PONG
```

### Marzban API failing
```bash
curl http://localhost:8585/health   # check marzban status
# If down, fix Marzban first — the bot queues nothing, approvals will fail
```

### A user's subscription isn't activating
1. Check logs for `[MARZBAN]` errors
2. Check the subscription's status in DB via admin panel → DB Explorer:
   ```sql
   SELECT * FROM subscriptions WHERE user_id = <id> ORDER BY created_at DESC LIMIT 5;
   ```
3. Try re-approving from admin panel

### After any crash or weird state
```bash
systemctl restart userbot.service adminbot.service
journalctl -u userbot.service -n 100
```

### Port 8585 already in use after crash
```bash
# Find what's holding the port
ss -tlnp | grep 8585
# Kill it by PID, then restart
kill <PID>
systemctl start userbot.service
```
