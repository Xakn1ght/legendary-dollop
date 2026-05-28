# AstroBytes

Telegram-based VPN subscription platform for Iranian users. Sells and manages VPN plans powered by [Marzban](https://github.com/Gozargah/Marzban), with a full web dashboard, admin panel, gamification system, and support ticketing.

---

## What it does

- Users buy VPN subscriptions via Telegram bot or web dashboard
- Payments are manual card transfers — users submit a receipt photo, admin approves
- On approval, a Marzban VPN user is created and the subscription link is sent
- Users earn stars, XP, loyalty points, and discounts through referrals, daily arcade games, and achievements
- Admin manages everything via a separate Telegram bot and a web panel

---

## Stack

| Layer | Technology |
|---|---|
| Bot framework | [aiogram](https://github.com/aiogram/aiogram) (async) |
| Web server | [aiohttp](https://github.com/aio-libs/aiohttp) (embedded in user bot) |
| Database | PostgreSQL + SQLAlchemy async (`asyncpg`) |
| Migrations | Alembic |
| Cache / FSM | Redis |
| Background jobs | APScheduler |
| VPN panel | Marzban API (external) |
| Auth | Argon2 password hashing, Telegram WebApp `initData` HMAC |
| Language | Python 3.14 |

---

## Project Structure

```
ASTROBYTE/
├── src/app/
│   ├── main.py                  ← User bot entry point + embedded web server
│   ├── admin_main.py            ← Admin bot entry point
│   ├── webserver.py             ← Thin shim → api/main.py
│   │
│   ├── api/                     ← aiohttp web layer
│   │   ├── routes/              ← ~180 route files grouped by domain
│   │   │   ├── admin/           ← User mgmt, subscriptions, receipts, tickets
│   │   │   ├── admin_auth/      ← Login, 2FA, session tokens
│   │   │   ├── admin_db/        ← Raw SQL explorer (admin panel)
│   │   │   ├── admin_ws/        ← WebSocket: real-time ticket updates
│   │   │   ├── dashboard/       ← Referrals, star rewards, VIP, wallet
│   │   │   ├── dashboard_charge/
│   │   │   ├── dashboard_purchase/
│   │   │   ├── dashboard_subs/
│   │   │   ├── dashboard_tickets/
│   │   │   ├── game/            ← Arcade submit, leaderboard
│   │   │   └── health/          ← /health endpoint
│   │   └── route_registry/      ← Registers routes into aiohttp app
│   │
│   ├── core/
│   │   ├── settings/            ← 10 config modules loaded from config/.env
│   │   ├── level_config.py      ← XP → level thresholds
│   │   └── redis_config.py      ← Redis connection pool
│   │
│   ├── database/
│   │   ├── models/              ← SQLAlchemy models split by domain
│   │   │   ├── _user.py         ← User
│   │   │   ├── _subscription.py ← Subscription, Receipt, VipOrder, ChargeRequest...
│   │   │   ├── _referral.py     ← Referral, ReferralReward
│   │   │   ├── _reward.py       ← 17 reward/game/analytics models
│   │   │   ├── _ticket.py       ← Ticket, TicketMessage, Notification
│   │   │   └── __init__.py      ← Re-exports all + init_db()
│   │   ├── crud.py              ← Flat re-export facade (used throughout codebase)
│   │   ├── cached_crud.py       ← Redis-cached wrappers
│   │   ├── notifications_crud.py
│   │   └── repos/               ← Domain repositories
│   │       ├── user.py
│   │       ├── subscription.py
│   │       ├── ticket.py
│   │       ├── analytics.py
│   │       └── reward/          ← Split into 7 modules
│   │           ├── _stars.py
│   │           ├── _tiers.py
│   │           ├── _game.py
│   │           ├── _challenges.py
│   │           ├── _achievements.py
│   │           ├── _points.py
│   │           └── _gifts.py
│   │
│   ├── handlers/
│   │   ├── admin/               ← Admin Telegram handlers
│   │   └── user/                ← User Telegram handlers
│   │
│   ├── jobs/                    ← APScheduler background jobs
│   │   ├── notifications.py     ← Low-data + expiry warnings
│   │   ├── renewal.py           ← Auto-renewal via Marzban
│   │   ├── enhanced_rewards.py  ← Star/XP/challenge processing
│   │   ├── expire_claims.py
│   │   └── cleanup_draft_orders.py
│   │
│   ├── services/
│   │   ├── marzban.py           ← Marzban VPN API client
│   │   └── subscription_processing.py
│   │
│   ├── utils/                   ← Logging, middleware, i18n, Persian utils
│   │
│   └── webapp/                  ← Frontend (HTML/CSS/JS)
│       ├── admin/               ← Admin panel SPA
│       ├── arcade/              ← AstroBugz HTML5 game
│       └── dashboard/           ← User dashboard SPA
│
├── alembic/                     ← DB migrations
├── config/
│   ├── .env                     ← Secrets (not committed)
│   ├── .env.example             ← Template
│   └── requirements.txt
└── scripts/                     ← Backup, restore, maintenance utilities
```

---

## Setup

### 1. Prerequisites

- Python 3.10+
- PostgreSQL
- Redis
- A running [Marzban](https://github.com/Gozargah/Marzban) instance
- Two Telegram bots (one for users, one for admin)

### 2. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r config/requirements.txt
pip install -e .
```

### 3. Configure environment

```bash
cp config/.env.example config/.env
# Edit config/.env with your values
```

Key variables:

```env
BOT_TOKEN=                        # User bot token
ADMIN_BOT_TOKEN=                  # Admin bot token
ADMIN_ID=                         # Your Telegram user ID
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/dbname
REDIS_HOST=localhost
REDIS_PORT=6379
MARZBAN_BASE_URL=https://your-marzban.example.com
MARZBAN_USERNAME=admin
MARZBAN_PASSWORD=
DASHBOARD_PUBLIC_BASE_URL=https://your-domain.com
GAME_WEBAPP_HOST=127.0.0.1
GAME_WEBAPP_PORT=8585
ADMIN_PANEL_PASSWORD_HASH=        # Generate with scripts/root/generate_admin_password.py
ADMIN_PANEL_SECRET_KEY=           # Random 32+ char string
PAYMENT_CARD_NUMBER=
PAYMENT_CARD_HOLDER=
```

### 4. Run database migrations

```bash
PYTHONPATH=src alembic -c config/alembic.ini upgrade head
```

### 5. Run

```bash
# User bot + web server
cd src && python -m app.main

# Admin bot (separate terminal)
cd src && python -m app.admin_main
```

---

## Production (systemd)

```bash
# Copy service files
cp userbot.service adminbot.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable userbot.service adminbot.service
systemctl start userbot.service adminbot.service
```

```bash
# Status / logs
systemctl status userbot.service adminbot.service
journalctl -u userbot.service -f
journalctl -u adminbot.service -f

# Restart after code changes
systemctl restart userbot.service adminbot.service
```

---

## Database Migrations (Alembic)

```bash
# Check current state
PYTHONPATH=src alembic -c config/alembic.ini current

# Create a new migration
PYTHONPATH=src alembic -c config/alembic.ini revision --autogenerate -m "describe change"

# Apply migrations
PYTHONPATH=src alembic -c config/alembic.ini upgrade head

# Rollback one step
PYTHONPATH=src alembic -c config/alembic.ini downgrade -1
```

---

## Snapshots & Backups

```bash
# Create a snapshot (excludes .venv, backups, __pycache__)
bash scripts/backup_snapshot.sh my-label

# List snapshots
bash scripts/list_snapshots.sh

# Restore
RESTORE_OK=yes bash scripts/restore_snapshot.sh backups/LATEST.tar.gz

# Backup database only (pg_dump)
python scripts/backup_db.py
```

Snapshots are stored in `backups/` and the 25 most recent are kept automatically.

---

## Lint

```bash
# Install
.venv/bin/pip install ruff

# Check
.venv/bin/ruff check src/app

# Auto-fix safe issues (import sorting, etc.)
.venv/bin/ruff check --fix --select I,F401 src/app
```

---

## Features

### VPN Subscriptions
- Users pick a plan → pay by card → submit receipt photo
- Admin approves → Marzban user created → link sent to user
- Supports charge (top-up) flow with pre-booking for active subs
- Auto-renewal via background job

### Referral System
- Each user gets a unique referral code
- Referee gets a first-purchase discount; referrer earns credit/traffic/days
- Tracks rewards via `referral_rewards` table

### Gamification
- **Stars** — earned via referrals, achievements, arcade game. Anti-farming via daily caps.
- **XP + Levels** — experience points unlock levels with loyalty/credit rewards
- **Loyalty points** — spendable in the rewards shop
- **Star tiers** — milestone thresholds unlock one-time rewards (discounts, credit, extra days)
- **Achievements** — 11 default achievements across referrals, usage, game streaks, purchases
- **Challenges** — daily/weekly (login, referral, daily game, weekly score)
- **Arcade game** — AstroBugz HTML5 game, daily play limit, score → star pieces → stars

### VIP Membership
- Plans: 1M / 3M / 6M / 1Y / lifetime
- Benefit: 20% discount on all plan purchases

### Support Tickets
- Categories: connection / money / other
- Status flow: pending → open → closed
- Private chat mode: admin invites user to a live Telegram conversation
- Supports text, photo, voice, and document messages
- Real-time WebSocket updates in the admin panel

### Admin Panel (web)
- Full user management (view, edit, ban, credit/stars adjustment)
- Subscription management and manual Marzban sync
- Receipt approval queue
- Ticket management with live updates
- Broadcast to all / filtered users
- Financial analytics and charts
- Raw SQL explorer (DB explorer)
- System commands and log viewer
- IP whitelist, 2FA, session management

### User Dashboard (web)
- Subscription overview with usage stats
- Purchase and charge flows
- Support ticket creation and chat
- Rewards shop, referral stats, wallet, VIP page
- Profile and settings

---

## Background Jobs

| Job | Schedule | What it does |
|---|---|---|
| `check_low_data_job` | Periodic | Notifies users running low on data |
| `renewal_job` | Periodic | Auto-renews eligible subscriptions |
| `update_user_analytics_job` | Daily | Aggregates usage analytics |
| `expire_star_reward_claims_job` | Periodic | Expires unclaimed star rewards |
| `reminder_unclaimed_star_rewards_job` | Periodic | Nudges users to claim rewards |
| `cleanup_draft_orders_job` | Periodic | Purges stale draft orders |

Schedules are configured in `core/settings/bot_behavior.py`.

---

## Languages

Persian (`fa`) is the default. English (`en`) is supported. The bot detects the user's preference and stores it per `chat_id`. The dashboard has a live language switcher that syncs across devices.

---

## Health Check

```bash
curl http://localhost:8585/health
```

Returns status for: database, Redis, Marzban API, bot, scheduler.

---

## Common Tasks

| Task | Where |
|---|---|
| Add a plan | `src/app/core/plans.json` |
| Change charge packages | `src/app/core/charge_packages.json` |
| Add Telegram handler | `src/app/handlers/user/` or `handlers/admin/` |
| Add API route | `src/app/api/routes/` + register in `route_registry/` |
| Change job schedule | `src/app/core/settings/bot_behavior.py` |
| DB model change | `database/models/` + new Alembic migration |
| Generate admin password | `python scripts/root/generate_admin_password.py` |
