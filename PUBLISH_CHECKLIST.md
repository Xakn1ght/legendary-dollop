# ASTROBYTE — Publish Checklist

_Grounded in a repo scan on 2026-06-11 (branch `rewards-pricing-rework`). Items marked
**[verify]** are decisions/values only you can supply. This is prioritized: do P0 before
letting any real user in._

---

## P0 — Blockers (security, money, config, deploy)

### Secrets & git hygiene
- [ ] **Live admin session tokens are committed to git.** `src/app/data/admin_sessions.json`
      is tracked (confirmed via `git ls-files`). The `.gitignore` rules are wrong: they say
      `app/data/*.json` and `app/webapp/admin/uploads/`, but the real paths are
      `src/app/data/…` and `src/app/webapp/admin/uploads/`, so nothing matches.
  - Fix `.gitignore` → `src/app/data/*.json` and `src/app/webapp/admin/uploads/`.
  - `git rm --cached src/app/data/*.json` (keep the files locally, stop tracking them).
  - **Rotate** anything that leaked: admin session secret, `ADMIN_PANEL_SECRET_KEY`,
    and force re-login (sessions invalidated).
- [ ] User-uploaded **payment receipts** (`src/app/webapp/admin/uploads/receipts/*.jpg`) are
      sitting untracked in the tree — make sure the corrected ignore covers them so a
      `git add -A` never commits customer receipts.
- [ ] Confirm `config/.env` is **not** tracked (the `.env` rules look OK) and never committed.

### Payment configuration (real money path)
- [ ] Set real `PAYMENT_CARD_NUMBER` / `PAYMENT_CARD_HOLDER` in `.env`. Default is the
      placeholder `6037-xxxx-xxxx-xxxx`.
- [ ] **[verify]** The placeholder card number is **hardcoded** in user-facing strings, not
      read from config, in at least: `src/app/utils/bot_i18n.py:101`,
      `src/app/handlers/user/purchase/confirmation.py:102` & `:134`. Make these use
      `PAYMENT_CARD_NUMBER` (from `core/settings/payment_ui.py`) or users will be told to pay
      a fake card.

### Environment / credentials (fill every value in `config/.env`)
- [ ] `BOT_TOKEN`, `ADMIN_BOT_TOKEN`, `ADMIN_ID`, `ADMIN_USERNAME`
- [ ] `MARZBAN_BASE_URL` / `MARZBAN_USERNAME` / `MARZBAN_PASSWORD` (and confirm panel reachable)
- [ ] `DATABASE_URL` (asyncpg), `REDIS_HOST/PORT/PASSWORD/DB`
- [ ] `ADMIN_PANEL_PASSWORD_HASH` (Argon2), `ADMIN_PANEL_SECRET_KEY` (32+ random), `ADMIN_2FA_ENABLED=true`
- [ ] `DASHBOARD_PUBLIC_BASE_URL` / `GAME_PUBLIC_BASE_URL` = real HTTPS domain

### Deployment / infra
- [ ] Provision PostgreSQL + Redis; run `PYTHONPATH=src alembic -c config/alembic.ini upgrade head`.
- [ ] HTTPS reverse proxy (nginx/caddy) in front of the aiohttp server on `:8585`; Telegram
      Mini Apps **require** HTTPS for the dashboard/game URLs.
- [ ] Install + enable systemd units (`userbot.service`, `adminbot.service`); confirm both
      restart on failure and start on boot.
- [ ] Set the bot's Mini App / menu-button URL to `DASHBOARD_PUBLIC_BASE_URL` in BotFather.
- [ ] Confirm `GAME_WEBAPP_HOST` is bound correctly behind the proxy (defaults to `0.0.0.0`).
- [ ] Backups: schedule `scripts/backup_db.py` / `scripts/backup_snapshot.sh`. **Never** run
      `scripts/reset_db.py` against prod.

---

## P1 — Before users rely on it (features, correctness, the open bug)

### Unfinished features — ship, finish, or hide
- [ ] **[verify] Wallet cash-out is a stub.** `src/app/api/routes/dashboard/wallet/cashout.py:19`
      — TODO(phase-d): 5% rate, caps, holds, ≥20GB rule not implemented. Either finish it or
      hide the cash-out entry point so users can't hit a half-built money flow.
- [ ] **[verify]** Level cosmetics (titles/badges) unrendered — `src/app/core/level_config.py:41`
      TODO(cosmetics-phase). Cosmetic only; fine to defer, just confirm nothing looks broken.
- [ ] Commit / open a PR for the **35 uncommitted files** in the working tree (this session's
      dashboard perf work + the rewards-pricing rework). Don't publish from a dirty tree.

### Open dashboard issue (see `src/app/webapp/dashboard/HANDOFF.md`)
- [ ] Confirm on your iPhone that the **heat/lag is acceptable** after the latest changes
      (glass.css v39). Last resort if still warm: trim blur radii (documented in HANDOFF).
- [ ] Resolve the **"glass strip above the VPN card"** — last fix (rim/inner-glow) is unverified.
      Next suspect: magma `blob-1` parked at the card top. A 2–3s screen recording pins it.

### Quality gates
- [ ] Run the test suite green: `PYTHONPATH=src python tests/test_pricing.py` (and the other 6
      in `tests/`: economy_safety, checkout_coupon, season_*, loyalty_retired).
- [ ] Smoke-test the full happy path end-to-end on a staging bot: start → buy plan → submit
      receipt → admin approve → subscription provisions in Marzban → dashboard shows it →
      charge/top-up → support ticket round-trip.
- [ ] Verify Telegram WebApp `initData` auth (`_verify_webapp_auth`) works against the prod
      bot token (it's the gateway for every dashboard API call).

---

## P2 — Operational polish (can follow shortly after launch)

- [ ] Replace stray `print(...)` debug calls in API routes with the logger
      (e.g. `api/routes/admin/messaging/send_notification.py`, `settings_vip/*`) so prod logs
      are consistent and capturable.
- [ ] Decide on error monitoring (Sentry or at minimum `journalctl` log shipping/retention).
- [ ] Review rate limiting + banned-user middleware are enabled in the prod path
      (`utils/error_middleware.py`, `utils/banned_user_middleware.py`).
- [ ] Review `admin_ip_whitelist.json` — lock the admin panel to known IPs if desired.
- [ ] Load/spot-check the scheduled jobs run in prod (renewals, expiry notifications, season
      reset) — `src/app/jobs/`.
- [ ] After launch, set a cadence for DB backups verification (restore a snapshot to confirm).

---

## Notes
- No build step for the frontend; remember to bump `?v=` query strings in `index.html` when
  shipping CSS/JS or the Telegram WebView serves stale cached assets.
- Performance optimizations are global (un-gated) in the v20 block at the end of `glass.css` —
  don't reintroduce `@media (max-width:768px)` gates around them.
- This list is from a targeted scan, not an exhaustive audit. The `[verify]` items especially
  need your product judgment.
