# ASTROBYTE — Final 0→100 Test Checklist (fresh-DB edition, 2026-07-05)

_Audit result: code healthy. All 18 test files pass, DB schema matches models, alembic at
head, both services live and current (restarted AFTER last commit), health endpoint green
(DB/Marzban/Redis/bot/scheduler), public domains serve, nightly backup timer runs, no
errors in journals. 3 commits not pushed to GitHub yet._

**Test accounts:** Paşanim `8148909121` (admin+referrer) · Rakai `8120318706` (buyer) · Tsuki (spare).
`[A]` = command (run from repo root) · `[M]` = manual on phone.
All commands: `.venv/bin/python`, never bare `python`.

---

## Phase 0 — RESET DB (required for a clean 0→100 run)

Run in this exact order. Do not skip the backup.

- [ ] 0.1 Backup first: `PYTHONPATH=src .venv/bin/python scripts/backup_db.py`
- [ ] 0.2 Stop bots: `sudo systemctl stop astrobyte-userbot astrobyte-adminbot`
- [ ] 0.3 Reset: `PYTHONPATH=src .venv/bin/python scripts/reset_db.py --confirm`
- [ ] 0.4 Stamp migrations: `PYTHONPATH=src .venv/bin/alembic -c config/alembic.ini stamp head`
- [ ] 0.5 Flush Redis via app client (redis-cli fails WRONGPASS):

```bash
PYTHONPATH=src .venv/bin/python - <<'EOF'
from dotenv import load_dotenv; load_dotenv('config/.env')
import asyncio
from app.core.redis_config import get_redis_client
async def m():
    r = await get_redis_client(); await r.flushdb(); print("redis flushed")
asyncio.run(m())
EOF
```

- [ d] 0.6 Delete leftover Marzban test users in the panel: `qssfqqq6`, `z358hdwt`, `j6pzq6i0` (+ any from earlier smoke runs)
- [ d] 0.7 Start bots: `sudo systemctl start astrobyte-userbot astrobyte-adminbot`
- [ d] 0.8 Verify single instances: `ps -eo cmd | grep -E '/python -m app\.(main|admin_main)$'` → exactly 2 lines
- [ d] 0.9 Health: `curl -s http://127.0.0.1:8585/health` → all checks ok

## Phase 1 — Automated baseline `[A]`

- [ d] 1.1 Unit suite: `for t in tests/test_*.py; do PYTHONPATH=src .venv/bin/python $t; done` → every file PASS (18 files)
- [ d] 1.2 After registering both accounts (Phase 2): `PYTHONPATH=src:. .venv/bin/python scripts/smoke_dashboard.py 8148909121` → all 200
      ⚠ this probe toggles your theme pref — flip it back in the webapp after
- [ d] 1.3 Full money loop: `PYTHONPATH=src:. .venv/bin/python scripts/smoke_full_loop.py` → 10/10 PASS (sends real DMs, provisions + leaves a Marzban test user — delete it after)

## Phase 2 — Accounts & referral `[M]`

- [ d] 2.1 Paşanim: `/start` → language pick → main keyboard
- [ d] 2.2 Paşanim: Invite → copy link. Rakai: `/start` via that link → Paşanim gets "new user joined" DM
- [ d] 2.3 Both: menu button opens dashboard, no login problem; first-run tour shows once, Skip works
- [ d] 2.4 OG-user path: third account (Tsuki) starts WITHOUT a link → webapp Tasks page → "enter friend's code" box → enter Paşanim's code → applied, invite count +1 (this was smoke item 3.5, now built)

## Phase 3 — Purchase, bot UI `[M]` — NOTE: flows now use INLINE buttons (commit `35d2385`, deployed but never manually tested — judge the UX)

- [ d] 3.1 Rakai bot: Buy → 20GB plan → summary 90,000 → real card number shown → typed text still works as alternative to buttons
- [ d] 3.2 Send receipt photo → "registered"; stale old inline keyboards answer "expired"
- [d ] 3.3 Paşanim admin bot: ONE message with photo+caption+Approve/Deny → Approve → Rakai gets sub link DM; user in Marzban panel; dashboard home shows sub with usage ring
- [ d] 3.4 Voucher DM to Paşanim, 4 choices → pick ⭐ star → rewards page: 1★, First Spark 5% coupon in wallet, next milestone 3★
- [d ] 3.5 Deny path: Paşanim buys with coupon → admin Deny → coupon back to active, credit refunded
- [ d] 3.6 Custom plan: GB-only (by design, 35d fixed); 52GB quote ≈222k; webapp custom-quote matches bot
- [ d] 3.7 Mid-flow cancel + /start reset work; main-menu reply keyboard stays visible during flows (decide if you like it)

## Phase 4 — React purchase/charge pages `[M]` (NEW since last smoke — full redo)

- [d ] 4.1 Webapp purchase page: plans grid, VIP prices hidden (no VIP yet), coupon picker only when coupon owned, custom plan slider, receipt upload with progress %, submit → pending
- [d ] 4.2 Webapp charge page: pick sub → 6 presets (10GB=38k … 100GB=300k, +35d each) → >5GB left triggers "charge anyway (5GB carry)" warning → receipt → admin approve → Marzban limit/expire bump + DM
- [d ] 4.3 Cancel button on charge page now exits to dashboard (old bug: stayed on page)
- [ d] 4.4 Pending order guard: reopen purchase page with an order pending → resumes/blocks sanely
- [ d] 4.5 Kill the page mid-flow → ghost order cleaned by cleanup job (or cancel works)

## Phase 5 — Support + tickets `[M]`

- [ ] 5.1 Rakai creates ticket (form submits — old 400 fixed) → live WS chat both ways
- [ ] 5.2 Photo attachments BOTH directions (user dashboard ↔ admin panel), lightbox, 📷 list preview
- [ ] 5.3 Telegram DESKTOP: support page WS connects (was 403)
- [ ] 5.4 Android: keyboard doesn't bury the composer; tap outside dismisses stale lift
- [ ] 5.5 VIP ticket lands high-priority (after Phase 7 VIP)
- [ ] 5.6 Admin bot reply path + admin panel reply path both notify the user

## Phase 6 — Webapp sweep `[M]`

- [ ] 6.1 Home: usage ring, copy link + QR, sub actions menu, manual Refresh (5-min cooldown)
- [ ] 6.2 Rewards/Tasks page: Persian digits, season card "⭐ ۱ از ۳", ladder 1→50 ✅/⏳/🔒
- [ ] 6.3 Wallet: cash-out gate message (needs 20 invites)
- [ ] 6.4 Notifications bell: unread badge, mark-read, polling stops when app hidden
- [ ] 6.5 Theme light/dark + accent persists across devices; pack accents locked until earned
- [ ] 6.6 Arcade: play → XP moves, stars/credit DO NOT; second run same day blocked; leaderboard name + opt-out; round-token anti-cheat = direct score POST without fresh round fails
- [ ] 6.7 Update prompt: bump asset version → in-app "update available" appears
- [ ] 6.8 iPhone heat OK after 2–3 min; Android navbar clear
- [ ] 6.9 Bot deep-link standalone pages: small logo, Persian nav

## Phase 7 — VIP `[M]`

- [ ] 7.1 Rakai: VIP 1-month 99k → receipt → approve → `is_vip` on, −20% badges, VIP-only 150/200GB plans visible
- [ ] 7.2 VIP price shows in bot summary too

## Phase 8 — Cheat-seeds `[A]` (fabricate big states, test, wipe — snippets in SMOKE_CHECKLIST.md Phase 6)

- [ ] 8.1 Grant 40★ → Champion badge + gold accent + free-plan/autorenew/pack coupons; free_plan zeroes a 20GB checkout
- [ ] 8.2 Seed 20 active referrals + 500k credit → cash-out 100k → "min 200k" · 250k → request → Deny → credit back → 250k → Approve → paid
- [ ] 8.3 Wipe seeds (snippet 6.3) → invite count back to real

## Phase 9 — Jobs & ops `[A]`

- [ ] 9.1 `journalctl -u astrobyte-userbot --since '-15 min' | grep -iE 'scheduler|job'` — renewal 60s, low-data 10min
- [ ] 9.2 Panel shield: `grep USER_INFO` on journal → sparse misses; dashboard warm loads fast
- [ ] 9.3 Auto-renew: reserved-renewal sub → shrink limit in panel → renews in ~2–3 min, ≤5GB carry
- [ ] 9.4 Season reset logged each 12h; arcade monthly-prize job registered (fires on the 1st)
- [ ] 9.5 Watchdog: `/errors` command in admin bot answers; disk-alert wired
- [ ] 9.6 Backup timer: `systemctl list-timers | grep astrobyte-backup` + fresh dir in `backups/auto/` (14 kept)
- [ ] 9.7 RESTORE REHEARSAL (never done): restore latest auto backup into a scratch DB, confirm tables/counts

## Phase 10 — SMS auto-approve (optional live arm — currently DISARMED, correct)

- [ ] 10.1 Add user bot (@khgfakgfbabot) as admin of AstroReceipts channel
- [ ] 10.2 Restart userbot → `echo '{"enabled": true}' > src/app/data/sms_state.json` (or SMS_AUTO_APPROVE=1)
- [ ] 10.3 Real small purchase → real card SMS → order auto-approves ONCE (bakbot must not double-approve — shared claim DB)
- [ ] 10.4 Ambiguity path: two same-amount pending orders → stays manual + AI hint DM
- [ ] 10.5 Not testing now? leave disarmed — it's off by default and safe

## Phase 11 — Launch gate

- [ ] 11.1 Push: `git push origin rewards-pricing-rework` (3 commits ahead + 1 local lint fix uncommitted) → PR → main. 
- [ ] 11.2 BotFather menu-button URL = https://dash.astrobytech.com/webapp/dashboard (verify what's set)
- [ ] 11.3 FINAL DB reset (repeat Phase 0) so real users start at zero; delete every Marzban test user
- [ ] 11.4 Post-launch watch: `journalctl -u astrobyte-userbot -f | grep USER_INFO` (cache misses sparse), renewal lag, panel CPU; if panel strains raise `USER_INFO_CACHE_TTL` in `services/marzban.py`
- [ ] 11.5 Old smoke leftovers cleaned: test tickets, test subs, seed users

---

## Known state (audit 2026-07-05)

- Working tree: ONE uncommitted 2-file import-sort lint fix (`models/__init__.py`, `models/_subscription.py`) — behavior identical, fold into next commit.
- Ruff baseline ≈1480 pre-existing errors repo-wide — ignore, only lint files you touch. E711/E712 in `repos/subscription.py` are correct SQLAlchemy idioms, do NOT "fix".
- SMS twin `../bakbot/sms_autoapprove.py` verified functionally identical (docstrings differ — fine).
- `subscription_links` table is app-created (not alembic) — intentional.
- Smoke items 3.4 (charge cancel), 3.5 (OG ref code), 3.6 (ticket 400) all FIXED since; 3.3 custom-days is by design (GB-only).
