# ASTROBYTE — Control-Plane Migration Runbook (Box A)

Status: **READY TO EXECUTE once Box A exists.** Nothing run yet.
Companion to `docs/SECURITY_ISOLATION_PLAN.md`. Target chosen: **fresh empty box**
(NOT the VPN node 178.105.230.205, which stays a VPN node).

## Facts gathered from the current (old) box
- App: Python **3.10+** compatible (current venv 3.14, but code targets 3.10+ →
  rebuild venv on whatever the fresh box ships, e.g. 3.12, no problem).
- DB: **PostgreSQL 18**, database name **`yomastrbot_db`**.
- Redis: local, not internet-facing.
- Must-move runtime state (`src/app/data/`): `admin_sessions.json`,
  `admin_session_state.json`, `admin_ip_whitelist.json`, `admin_ui_settings.json`,
  `allowed_users.json`, `user_state.json`, `job_status.json`, `node_watch.json`,
  `avatars/`, `ticket_uploads/`. (sms_state.json if present — arming flag.)
- React builds ship in-repo (`webapp/admin/react`, `webapp/dashboard/react`) — no
  build needed on Box A if we rsync them; otherwise `cd frontend && vite build`.
- VPN stays put: `MARZBAN_BASE_URL` on Box A points at the node's Marzban.

## What Box A must be
- Hetzner **CX22** (2 vCPU / 4 GB) or larger, **Ubuntu 24.04**, plain — **do NOT**
  run any Marzban/xray installer on it. This box only runs: bot ×2, aiohttp,
  Postgres, Redis, nginx.
- SSH: key-only, non-default port, root or sudo user. The ed25519 key already on
  the old box (`~/.ssh/id_ed25519.pub`) should be added to Box A `authorized_keys`
  so the old box can rsync/ssh to it during cutover.

## Decisions still needed from you
1. Confirm both `dash.astrobytech.com` (dashboard+admin) and
   `game1.astrobytech.com` (arcade) move to Box A. ✅/change
2. Cloudflare: you orange-cloud both domains, set SSL **Full (strict)**, and
   either issue an **Origin Certificate** for Box A or set up a **CF Tunnel**
   (tunnel = origin IP never exposed at all; recommended).
3. Marzban reachability: Box A must reach the node's Marzban API. Prefer a
   private path (WireGuard between boxes) so `:62050` can be firewalled off the
   public internet. ✅/change

## Execution phases (each reversible until Phase 4)

### Phase 1 — Provision Box A (no user impact)
```bash
# ON BOX A (fresh), as root:
apt update && apt -y install python3 python3-venv python3-pip postgresql redis-server nginx git rsync curl
# app user + dirs
useradd -m -s /bin/bash astro || true
install -d -o astro -g astro /opt/astrobyte
# postgres: create role + db (use a NEW strong password; put it in Box A .env)
sudo -u postgres psql -c "CREATE ROLE astro LOGIN PASSWORD '<NEW_DB_PASS>';"
sudo -u postgres psql -c "CREATE DATABASE yomastrbot_db OWNER astro;"
```

### Phase 2 — Ship code + data + DB (from OLD box, no cutover)
```bash
# ON OLD box (dump DB — no creds shown here; uses existing scripts/backup_db.py):
cd /root/5a06b8e65bdb/ASTROBYTE && .venv/bin/python scripts/backup_db.py   # → dump file
# rsync repo (excluding venv/junk) + data + dump to Box A:
rsync -az --delete \
  --exclude '.venv' --exclude '__pycache__' --exclude 'node_modules' \
  --exclude 'frontend/node_modules' --exclude '.git' \
  -e 'ssh -p <BOXA_PORT>' /root/5a06b8e65bdb/ASTROBYTE/ astro@<BOXA_IP>:/opt/astrobyte/
# restore on Box A:
#   psql yomastrbot_db < <dump>    (as the astro role)
```
```bash
# ON BOX A: venv + deps
cd /opt/astrobyte && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
# .env: copy config/.env then EDIT:
#   DATABASE_URL -> local postgres (new pass)
#   MARZBAN_BASE_URL -> node private addr
#   ADMIN_ALLOWED_HOSTS=dash.astrobytech.com   (host gate already in code)
#   KEEP identical: WEBAPP_SESSION_SECRET, ADMIN_PANEL_SECRET_KEY  (else sessions/2FA reset)
#   BOT_TOKEN / ADMIN_BOT_TOKEN unchanged
PYTHONPATH=src .venv/bin/alembic -c config/alembic.ini upgrade head
```

### Phase 3 — Bring up + smoke test on a staging host (still no DNS cutover)
- systemd units (`userbot.service`, `adminbot.service`) copied + enabled.
- Test via Box A IP / a temporary hostname BEFORE moving DNS.
- **Only ONE box may poll each Telegram bot at a time** — do the final bot start
  on Box A at the same moment you stop them on the old box (Phase 4), or Telegram
  409-conflicts. For staging test, use `getUpdates` off / a test token if needed.

### Phase 4 — Cutover (the irreversible-ish moment; low DNS TTL first)
1. Lower CF DNS TTL to 60s a day ahead.
2. Stop `astrobyte-userbot`/`astrobyte-adminbot` on OLD box.
3. Start them on Box A.
4. Point `dash` + `game1` A records → Box A (proxied/orange, or via CF Tunnel).
5. Firewall Box A (SSH-safe — SSH port FIRST), origin locked to Cloudflare.
6. Watch logs + do a full smoke test (login, 2FA, purchase, receipt, support).

### Rollback
- Old box stays fully intact + warm for 24–48h. To revert: stop bots on Box A,
  start on old box, flip A records back. (Because bot polling is exclusive, revert
  is also a stop-here/start-there flip.)

## Post-cutover cleanup (old box)
- Remove dash/game vhosts from old nginx (leave the other ~10 sites alone).
- Decommission the old app's DB/redis data ONLY after Box A is verified.
- Rotate `WEBAPP_SESSION_SECRET`/DB password later if you want a clean break
  (forces re-login; do it deliberately, not during cutover).

## Division of work
- **Me, once you give Box A IP/port/key:** Phases 1–3 (provision, ship, deploy,
  staging test) — all reversible, don't touch the live service. I'll pause before
  Phase 4.
- **You:** create the box, all Cloudflare + DNS, and the go-ahead for the Phase 4
  cutover (bot swap + DNS). I'll run the box-side commands of Phase 4 with you.
