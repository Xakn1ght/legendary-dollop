# ASTROBYTE — Test run

One checklist. Replaces the old SMOKE_CHECKLIST.md and FINAL_TEST_CHECKLIST.md.

**Test accounts:** Paşanim `8148909121` (admin + referrer) · Rakai `8120318706` (buyer)

`[cmd]` = type a command here · `[phone]` = do it on your phone

---

## The two rules

**1. Found something wrong? Write it in `TESTING_FINDINGS.md` and keep going.**
Only stop if the step did not produce what the next step needs. "Ugly but it
worked" is a note, not a stop. Do not start fixing mid-run.

**2. Save before every phone phase. Never redo phone work.**

```
.venv/bin/python scripts/checkpoint.py save phase3
```

Hit a real blocker? Fix it, then go back one step instead of starting over:

```
.venv/bin/python scripts/checkpoint.py load phase3
```

Only start from Phase 0 again if you changed the database structure (a new
migration).

---

## Before you start

- [ ] Turn on test mode — add to `config/.env`:  `TEST_PANEL_PREFIX=qa`
- [ ] Restart the bots: `systemctl restart astrobyte-userbot astrobyte-adminbot`
- [ ] Every VPN account you make now gets named `qa...` so it can be cleaned up

Remember to remove that line when you finish testing.

---

## Phase 0 — Fresh start `[cmd]`

Only needed for a full clean run. Skip it if you are continuing.

- [ ] 0.1 Back up first: `.venv/bin/python scripts/backup_db.py`
- [ ] 0.2 Stop the bots: `systemctl stop astrobyte-userbot astrobyte-adminbot`
- [ ] 0.3 Wipe: `PYTHONPATH=src .venv/bin/python scripts/reset_db.py --confirm`
- [ ] 0.4 Mark migrations current: `PYTHONPATH=src .venv/bin/alembic -c config/alembic.ini stamp head`
- [ ] 0.5 Start the bots again
- [ ] 0.6 **Save point:** `.venv/bin/python scripts/checkpoint.py save fresh`

---

## Phase 1 — Automatic checks `[cmd]`

These need no phone. Run them first — they are fast and catch a lot.

- [ ] 1.1 All 44 test files pass:
      `for t in tests/test_*.py; do PYTHONPATH=src .venv/bin/python $t || echo "FAILED $t"; done`
- [ ] 1.2 API answers: `PYTHONPATH=src .venv/bin/python scripts/smoke_dashboard.py 8148909121` — all 200
- [ ] 1.3 Whole money loop: `PYTHONPATH=src:. .venv/bin/python scripts/smoke_full_loop.py` — all pass
- [ ] 1.4 Auto-renewal, real traffic: `.venv/bin/python scripts/test_renewal_burn.py` — 10/10 pass
- [ ] 1.5 Background jobs are running: `journalctl -u astrobyte-userbot --since '15 min ago' | grep -i job`

---

## Phase 2 — Accounts and invites `[phone]`

- [ ] **Save point first:** `.venv/bin/python scripts/checkpoint.py save phase2`
- [ ] 2.1 Paşanim: `/start` → pick language → main menu appears
- [ ] 2.2 Paşanim: Invite button → copy the invite link
- [ ] 2.3 Rakai: open Paşanim's invite link → `/start` → registers, Paşanim gets a "new user" message
- [ ] 2.4 Both: menu button opens the dashboard, no login error. First-run tour shows once, Skip works

---

## Phase 3 — Buying `[phone]`

Rakai buys, Paşanim approves.

- [ ] **Save point first:** `.venv/bin/python scripts/checkpoint.py save phase3`
- [ ] 3.1 Rakai: Buy → 20GB plan → price shows 90,000, no coupon step yet, and the card number is your REAL card
- [ ] 3.2 Rakai: send the receipt photo → "registered" message
- [ ] 3.3 Paşanim admin bot: the receipt arrives with the photo and Approve/Deny buttons
- [ ] 3.4 Approve → Rakai gets the subscription link, the account appears in the VPN panel (named `qa...`), dashboard shows it
- [ ] 3.5 Paşanim: reward message arrives with 4 choices → pick the star
- [ ] 3.6 Paşanim rewards page: 1 star, the First Spark 5% coupon in the wallet, next goal 3 stars
- [ ] 3.7 Paşanim invite screen: 1 active invite, tier and cash-out lines correct

---

## Phase 4 — Spending and refunds `[phone]`

- [ ] **Save point first:** `.venv/bin/python scripts/checkpoint.py save phase4`
- [ ] 4.1 Paşanim buys: the coupon step now appears; picking First Spark takes 5% off
- [ ] 4.2 Submit it → Paşanim Denies from admin → user is told, coupon returns to the wallet, any credit comes back
- [ ] 4.3 Custom plan: pick a GB amount → price follows the curve. Over 300GB should be VIP-only
- [ ] 4.4 Top-up (charge) on Rakai's subscription: **the plans should be the same list as buying** (this changed — there is no separate top-up price list any more) → receipt → approve → panel limit goes up, user gets a message
- [ ] 4.5 Multi-month: 2 and 3 month options should be **hidden for a non-VIP user**
- [ ] 4.6 Support: Rakai opens a ticket → Paşanim replies from admin → messages appear live both ways
- [ ] 4.7 Language switch fa↔en redraws both the bot menus and the dashboard

---

## Phase 5 — VIP `[phone]`

- [ ] **Save point first:** `.venv/bin/python scripts/checkpoint.py save phase5`
- [ ] 5.1 Rakai buys VIP → receipt → approve → VIP turns on
- [ ] 5.2 Rakai now sees VIP discount on normal plans, and the VIP-only plans (350/400/500 GB) appear
- [ ] 5.3 VIP-only plans do **not** also get the VIP discount — they are the perk
- [ ] 5.4 2 and 3 month options are now visible for this VIP user
- [ ] 5.5 Rakai's new support ticket shows as high priority

---

## Phase 6 — Dashboard sweep `[phone]`

- [ ] **Save point first:** `.venv/bin/python scripts/checkpoint.py save phase6`
- [ ] 6.1 Home: usage ring, copy link, QR code, subscription menu
- [ ] 6.2 Rewards page: Persian numbers, season card, ladder 1→50 with locked/done marks
- [ ] 6.3 Wallet: cash-out is blocked with "needs 20 active invites"
- [ ] 6.4 Notifications bell: unread badge from the purchases above, tapping one opens the right page, mark-as-read works
- [ ] 6.5 Theme light/dark and all 5 accent colours; choice sticks after reload
- [ ] 6.6 Arcade: play once → XP goes up, stars and credit do **not**
- [ ] 6.7 Phone check: no heat or lag after 2–3 minutes; nothing hidden behind the Android system bar
- [ ] 6.8 Everything readable in Persian, right-to-left, on a phone-width screen

---

## Phase 7 — Admin panel `[phone]` or desktop

Open the admin panel and check each page loads and its main action works.

- [ ] 7.1 Dashboard · 7.2 Users · 7.3 Subscriptions · 7.4 Receipts
- [ ] 7.5 VIP · 7.6 Coupons · 7.7 Servers · 7.8 Notifications
- [ ] 7.9 Settings · 7.10 Logs · 7.11 Audit · 7.12 Database
- [ ] 7.13 Support inbox: reply to Rakai's ticket, it arrives live
- [ ] 7.14 `.venv/bin/python scripts/verify_admin_panel_features.py`

---

## Phase 8 — Big-number states `[cmd]`

Fakes states that would need dozens of real referrals.

- [ ] **Save point first:** `.venv/bin/python scripts/checkpoint.py save phase8`
- [ ] 8.1 `PYTHONPATH=src .venv/bin/python scripts/phase8_cheatseed_run.py` — it runs the
      cash-out checks itself and prints pass/fail, then removes the fake referrals
- [ ] 8.2 With 40 stars: Champion badge and gold accent appear, free-plan coupons land in the wallet, a free-plan coupon takes a 20GB purchase to zero
- [ ] 8.3 With 20 active invites: cash-out under 200,000 is refused; 250,000 creates a request and reserves the credit
- [ ] 8.4 Admin Denies the cash-out → credit comes back. Then Approve one → marked paid
- [ ] 8.5 **Undo the rest:** the script removes the fake referrals but leaves the 40
      stars and coupons. Load the save point to clear those too:
      `.venv/bin/python scripts/checkpoint.py load phase8`

---

## After the run

- [ ] Delete the test VPN accounts:
      `.venv/bin/python scripts/cleanup_test_panel_users.py` then again with `--delete`
- [ ] Remove `TEST_PANEL_PREFIX` from `config/.env` and restart the bots
- [ ] Go through `TESTING_FINDINGS.md` and decide what to fix
- [ ] Delete save points you no longer need: `.venv/bin/python scripts/checkpoint.py list`

---

## Before letting the public in

- [ ] `config/.env` has real values; 2FA on for the admin panel
- [ ] Migrations at head: `PYTHONPATH=src .venv/bin/alembic -c config/alembic.ini current`
- [ ] Both services start on boot and survive a restart
- [ ] Backups running, and restore tested once for real
- [ ] Decide about the old customer receipts still in the GitHub history
- [ ] Decide on error monitoring
- [ ] Final database wipe so real users start clean
