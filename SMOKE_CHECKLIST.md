# ASTROBYTE — Pre-Publish Smoke Checklist

_One place to verify everything, back + front. Ordered so each section builds on the
previous one. Test accounts: **Paşanim `8148909121`** (admin + referrer), **Rakai
`8120318706`** (buyer/referee). Run everything from the repo root._

Legend: `[A]` automated — one command, `[M]` manual — needs your phone(s).

---

## 1. Automated backend checks `[A]`

| # | What | Command | Expect |
|---|---|---|---|
| 1.1 | Unit suite (pricing, coupons, season, cashout, flows) | `for t in tests/test_*.py; do PYTHONPATH=src .venv/bin/python $t; done` | every file prints PASS / "tests passed" |
| 1.2 | Dashboard API probes (auth, plans, quote, referrals, rewards, prefs) | `PYTHONPATH=src .venv/bin/python scripts/smoke_dashboard.py 8148909121` | all rows 200 |
| 1.3 | Season config live | `PYTHONPATH=src .venv/bin/python scripts/smoke_dashboard.py 8148909121 /api/dashboard/season` | ladder starts at 1★ "First Spark"; autorenew payloads say `max_plan_gb: 60` |
| 1.4 | **Full money loop** — purchase → receipt → admin-approve → Marzban provision → referral voucher → star redeem → 1★ coupon → coupon spend+restore → charge top-up → cashout gate | `PYTHONPATH=src:. .venv/bin/python scripts/smoke_full_loop.py` | `8/8 passed`; buyer + referrer Telegram accounts each get real DMs |
| 1.5 | Loop cleanup (after phone inspection) | `PYTHONPATH=src:. .venv/bin/python scripts/smoke_full_loop.py --cleanup <marzban_username>` (username printed by 1.4) | marzban_deleted=True |

> 1.4 mutates the real DB + Marzban and DMs the two test accounts — that's the point.


- [ ] 1.1 &nbsp; - [ ] 1.2 &nbsp; - [ ] 1.3 &nbsp; - [ ] 1.4 &nbsp; - [ ] 1.5

---

## 2. User bot — manual on phone (Rakai account) `[M]`

- [ ] 2.1 `/start` → language pick → main keyboard appears (no crash, fa default)
- [ ] 2.2 **Buy**: pick 20GB plan → summary shows price (VIP −20% if VIP) → card number shown is the REAL card (from admin payment settings, not a placeholder)
- [ ] 2.3 Send an actual receipt **photo** → "registered" message → order pending
- [ ] 2.4 **Coupon step** appears after discount step when a spendable coupon exists; picking one changes the payable amount in the summary
- [ ] 2.5 **Custom plan** (`custom:<gb>`): 52GB quote ≈ curve price, min-days guard (no <15d)
- [ ] 2.6 **Charge**: pick service → all 6 presets show (10→38k … 100→300k) → over-5GB warning path (`charge anyway` = 5GB carry) → receipt photo
- [ ] 2.7 **Invite** button: message shows the 4-choice payoff, your % tier, 20-invite cash-out line, season stars, active-invite count
- [ ] 2.8 **Rewards menu**: season stars + next milestone + "My coupons" wallet with expiry dates
- [ ] 2.9 Voucher DM (after 1.4 or a real referred buy): 4 buttons → pick each type once across tests (⭐ / credit / GB / days) → confirmation + balances change
- [ ] 2.10 **Support**: open ticket → send message → reply arrives from admin side (2.14)
- [ ] 2.11 Language toggle fa↔en re-renders menus in place

## 3. Admin bot — manual (Paşanim account) `[M]`

- [ ] 3.1 New purchase receipt lands with photo + Approve/Deny buttons
- [ ] 3.2 **Approve** → buyer gets sub link DM; Marzban panel shows the user; dashboard lists it
- [ ] 3.3 **Deny** a second test order → buyer notified; credit/coupon/discount all restored (check wallet + coupon wallet)
- [ ] 3.4 Charge receipt → Approve → traffic/days bump visible in Marzban + user DM
- [ ] 3.5 Cashout request visible → **Deny** → credit returned to user; **Approve** path marks paid
- [ ] 3.6 Plan editor: change a price → `src/app/core/plans.json` updates → bot + webapp show new price without restart
- [ ] 3.7 Broadcast/announcement sends to test users only (careful before launch)

## 4. Webapp dashboard — manual, inside Telegram `[M]`

- [ ] 4.1 Menu button opens dashboard over HTTPS; auth works (no "Login problem")
- [ ] 4.2 First run: welcome tour (14 steps) → Skip works → never re-appears
- [ ] 4.3 Home: VPN card shows real usage %, copy sub-link + QR work
- [ ] 4.4 **Purchase page**: plan grid → coupon picker (single-select, live price preview) → receipt upload → lands in admin bot (3.1)
- [ ] 4.5 **Charge page**: 4-step stepper, presets correct, custom GB/days quotes
- [ ] 4.6 **Rewards page** (also via bot deep-link button — standalone page): stat tiles Persian, season card "⭐ ۰ از ۳" style, ladder 1→50, coupon wallet, redeem voucher sheet works
- [ ] 4.7 Wallet: cash-out button → below 20 active invites shows the gate message; min amount 200k message when eligible
- [ ] 4.8 Profile: Legend/Champion badge chip + unlocked accent swatches (after owning a pack coupon); accent picks persist
- [ ] 4.9 Shop/support pages: bottom-nav labels in Persian, nav navigation works
- [ ] 4.10 Notifications bell: unread badge, mark-read, polling stops when app minimized
- [ ] 4.11 Theme light/dark toggle; one accent hue per screen (no rainbow)
- [ ] 4.12 Arcade opens, plays, XP-only (no stars/credit from score) — check rewards summary before/after a run
- [ ] 4.13 iPhone: heat/lag acceptable after 2–3 min (glass v47); Android: bottom nav clears system buttons
- [ ] 4.14 EN language end-to-end (switch in profile): no stray Persian/English mixing

## 5. Background jobs `[A]`/`[M]`

- [ ] 5.1 Scheduler registered: `journalctl -u astrobyte-userbot.service --since '10 min ago' | grep -i -E 'scheduler|job'`
- [ ] 5.2 Renewal job: reserved-renewal sub near expiry renews + carries ≤5GB (or force with a short test sub)
- [ ] 5.3 Expiry notifications DM at the configured thresholds
- [ ] 5.4 Season reset: runs every 12h; on season end → stars reset to 0, new season row, coupons expire per their own dates (unit-tested; spot-check journal)

## 6. Ops / launch gate (from PUBLISH_CHECKLIST.md)

- [ ] 6.1 `config/.env` prod values (tokens, Marzban, DB, Redis, ADMIN_2FA_ENABLED=true)
- [ ] 6.2 HTTPS reverse proxy → :8585; `DASHBOARD_PUBLIC_BASE_URL` = real domain; BotFather menu-button URL set
- [ ] 6.3 `PYTHONPATH=src alembic -c config/alembic.ini current` = head
- [ ] 6.4 systemd: `systemctl is-enabled astrobyte-userbot astrobyte-adminbot` = enabled; restart drill: `systemctl restart ...` then `ss -ltnp | grep 8585`, journal free of `TelegramConflictError`
- [ ] 6.5 Backups scheduled (`scripts/backup_db.py` cron) + one restore rehearsal
- [ ] 6.6 Decide git-history scrub (customer receipts still in remote history)
- [ ] 6.7 Reset test data before real users: stop bots → `scripts/reset_db.py --confirm` → alembic stamp head → Redis FLUSHDB → start bots (see memory of exact steps in GUIDE/handoff)
- [ ] 6.8 Error monitoring decision (Sentry or journalctl retention)

---

## Known-good state when everything passes

Purchase money flows only through: plan price → optional credit/discount/one coupon →
receipt → admin approval → Marzban provision. Rewards mint money only from referred
purchases (10/12/15% credit tier, or GB/days/stars). Cash leaves only via cashout:
≥20 active referrals AND ≥200k toman. Play/levels mint nothing.
