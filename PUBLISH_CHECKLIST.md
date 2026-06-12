# ASTROBYTE — Publish Checklist

_Grounded in a repo scan on 2026-06-11 (branch `rewards-pricing-rework`). Items marked
**[verify]** are decisions/values only you can supply. This is prioritized: do P0 before
letting any real user in._

---

## P0 — Blockers (security, money, config, deploy)

### Secrets & git hygiene
- [x] ~~Live admin session tokens are committed to git.~~ **Done 2026-06-12** (commit `cc38e92`):
      `.gitignore` paths fixed (`src/` prefix), all `src/app/data/*.json` + `src/app/webapp/admin/uploads/`
      untracked (kept on disk), `ADMIN_PANEL_SECRET_KEY` rotated in `config/.env`,
      `admin_sessions.json` cleared — leaked tokens are now unverifiable; admin must re-login.
- [x] Receipts covered by the corrected ignore — `git add -A` can no longer commit them. **Done 2026-06-12.**
- [x] `config/.env` confirmed not tracked.
- [ ] **[decide] Old commits still contain the receipts + session JSONs** and are pushed to
      `github.com/Xakn1ght/legendary-dollop`. Tokens are dead (key rotated), but ~60 customer
      payment receipts remain in remote history. Scrubbing requires `git filter-repo` + force-push
      (rewrites all history) — or, if the repo is private and stays private, accept the risk.
      If the repo was ever public, scrub.

### Payment configuration (real money path)
- [x] Real card is configured via `src/app/core/payment_settings.json` (admin-set; overrides
      the env default). **Verified 2026-06-12.**
- [x] ~~Placeholder card hardcoded in user-facing strings.~~ **Done 2026-06-12** (commit `cc38e92`):
      `bot_i18n.py` `charge_request_registered` now takes a `{card}` slot, formatted with the
      live `PAYMENT_CARD_NUMBER`/`HOLDER` in `handlers/user/charge/package_confirm.py`.
      `confirmation.py` was already fixed in `b038304`.

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
- [x] ~~Wallet cash-out is a stub.~~ **Stale — implemented in the flows rework** (`980e3a8`):
      `cashout.py` now calls `app.services.flows.cashout.create_cashout` (VIP-Promoter gate,
      shared eligibility rules, `cashout_requests` table). Covered by `tests/test_cashout_service.py`.
- [ ] **[verify]** Level cosmetics (titles/badges) unrendered — `src/app/core/level_config.py:41`
      TODO(cosmetics-phase). Cosmetic only; fine to defer, just confirm nothing looks broken.
- [x] ~~Commit the uncommitted files.~~ **Done 2026-06-12**: tree committed in 3 logical commits
      (security `cc38e92`, dashboard perf `cd9490c`, docs `98dafac`). Only local scratch
      (`previews/`, `.impeccable/`, a duplicate spec md) remains untracked.

### Open dashboard issue (see `src/app/webapp/dashboard/HANDOFF.md`)
- [ ] Confirm on your iPhone that the **heat/lag is acceptable** after the latest changes
      (glass.css v39). Last resort if still warm: trim blur radii (documented in HANDOFF).
- [ ] Resolve the **"glass strip above the VPN card"** — last fix (rim/inner-glow) is unverified.
      Next suspect: magma `blob-1` parked at the card top. A 2–3s screen recording pins it.

### Quality gates
- [x] Test suite green: **all 11 test files pass** (run 2026-06-12 with
      `PYTHONPATH=src .venv/bin/python tests/<file>`).
- [ ] Smoke-test the full happy path end-to-end on a staging bot: start → buy plan → submit
      receipt → admin approve → subscription provisions in Marzban → dashboard shows it →
      charge/top-up → support ticket round-trip.
- [ ] Verify Telegram WebApp `initData` auth (`_verify_webapp_auth`) works against the prod
      bot token (it's the gateway for every dashboard API call).

---

## P2 — Operational polish (can follow shortly after launch)

- [x] ~~Replace stray `print(...)` debug calls in API routes.~~ **Done 2026-06-12** (`533c7fe`):
      send_notification, settings_vip/*, admin_auth login/2FA now use `logging` with levels.
      (Intentional console output in `setup_password.py` / password-migration banner kept.)
- [x] Rate limiting + banned-user middleware confirmed registered in `main.py:205-208`
      (RateLimit, Validation, BannedUser, ErrorHandling all on the dispatcher).
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
