# ASTROBYTE — Server Isolation & IP-Hardening Plan

Status: **DRAFT for review — nothing below has been applied.**
Author: admin lane, 2026-07-06. Review, then we execute phase by phase.

---

## 0. Threat model (what we're actually defending against)

This is a paid VPN service for Iranian users. The realistic adversaries:

1. **A state censor** that actively scans for VPN infrastructure (Marzban/xray/reality ports) and blocks the IPs it finds. If it finds *this* box it blocks the VPN **and** everything else on the IP.
2. **An opportunistic attacker** who finds the raw origin IP and either DDoSes it (bypassing Cloudflare) or pivots through one of the ~10 unrelated apps co-hosted here into Astrobyte's money + user data.
3. **Anyone trying to deanonymize your customers** — the crown jewels are the Postgres rows mapping Telegram identity → subscription. That data must never share an IP with the ports a censor is hunting.

**Goal:** the control plane (bot + dashboard + admin + user DB) becomes hard to locate and useless-if-located; the VPN plane stays reachable by clients but carries **no customer identity**.

---

## 1. Current state (verified on the box 2026-07-06)

- **No host firewall.** `ufw` inactive; no nftables/iptables rules. Every listening port is open to the whole internet.
- **Origin not locked to Cloudflare.** `dash.astrobytech.com` is CF-proxied, but nginx answers any IP directly → CF's WAF/DDoS is bypassable the moment the raw IP leaks.
- **`game1.astrobytech.com` DNS points straight at the box** (grey-cloud). This is the current live IP leak — one `dig` reveals the IP, which also deanonymizes the CF-fronted dash (same IP).
- **Co-location:** userbot + adminbot + aiohttp (`:8585`) + **PostgreSQL** + Redis + **Marzban (`:62050`)** + xray + ~10 unrelated apps all on ONE IP.
- **Good news:** Postgres (`5432`) and Redis (`6379`) are **not** internet-facing (localhost-bound). The DB is co-located but not directly exposed.
- **SSH is on port `52217`** (NOT 22). ← any firewall rule MUST allow this first or we lock ourselves out.

### Internet-facing ports found

| Port | Process | Verdict |
|---|---|---|
| 80 / 443 | haproxy | keep (CF-locked) |
| 10002–10004 | nginx | keep (CF-locked; internal) |
| 62050 | python = **Marzban panel** | firewall — VPN control plane, prime censor target |
| 631 | cupsd (snap CUPS printing) | **close** — never needs the internet |
| 21115–21119 | hbbs/hbbr = **RustDesk** relay | restrict to your IP / VPN, or close |
| 8123 | python3 (other app) | CF-only or close |
| 8790 | node (other app) | CF-only or close |
| 4416 | python (other app) | CF-only or close |
| 52217 | **sshd** | keep — allowlist your admin IP |

(8123/8790/4416/RustDesk/CUPS are your *other* projects — closing them is a shared-box decision, listed so you can decide.)

---

## 2. Target architecture

Two planes, two IPs. This split is the highest-value change — more than "dedicated vs shared."

```
                      Cloudflare (orange cloud, WAF, TLS Full-strict)
                                   │  (only CF IPs allowed to origin)
                                   ▼
┌───────────────────────────── BOX A — CONTROL PLANE (new/dedicated) ─────────────────────────────┐
│  userbot + adminbot + aiohttp :8585 + PostgreSQL (USER DB) + Redis                               │
│  Domains: dash.astrobytech.com, game1.astrobytech.com  (both CF-proxied)                         │
│  Firewall: deny all in; allow SSH(52217, your IP), 80/443 (CF ranges only)                       │
│  Holds ALL customer identity (Telegram id ↔ subscription). IP is hidden + CF-locked.             │
└──────────────────────────────────────────────┬───────────────────────────────────────────────────┘
                                                │  outbound HTTPS to Marzban API (firewalled to Box A)
                                                ▼
┌───────────────────────────── BOX B — VPN PLANE (can stay where it is) ─────────────────────────┐
│  Marzban panel + xray/reality nodes.  Clients connect here directly (unavoidable).               │
│  Holds only marzban usernames it provisions — NO Telegram identity, NO payments.                 │
│  If a censor finds this IP: they block VPN (recoverable) but learn nothing about WHO your users   │
│  are and can't reach the dashboard/DB.                                                            │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
```

Why this works: the Telegram-identity↔username mapping lives only in **your** Postgres (moves to Box A). Marzban only knows the opaque usernames it was told to create. So Box B being discoverable (which is unavoidable for a VPN) leaks no customer identity.

**Dedicated for Box A: recommended** (money + PII), but isolating it from the *VPN plane* matters more than isolating it from your other pashanimx apps. If Box A also hosts your other apps, co-tenancy blast-radius returns — so a clean dedicated box for Astrobyte's control plane is the defensible choice.

---

## 3. Migration plan (phased, each phase reversible)

### Phase 1 — Provision Box A (no cutover yet)
- New VPS, minimal OS. SSH on a non-default port, key-only, allowlist your admin IP.
- Install: Python venv, PostgreSQL 18, Redis, nginx. Clone repo, `.venv`, `config/.env`.
- Restore a fresh `pg_dump` from the current DB (`scripts/backup_db.py`).
- `.env` on Box A: `DATABASE_URL` → local Postgres; `MARZBAN_BASE_URL` → Box B (private/firewalled); keep the SAME `WEBAPP_SESSION_SECRET` and `ADMIN_PANEL_SECRET_KEY` so sessions/2FA survive; `ADMIN_ALLOWED_HOSTS=dash.astrobytech.com` (host gate already shipped).
- Bring up both bots on Box A, smoke-test against a staging hostname before touching DNS.

### Phase 2 — Cloudflare + DNS cutover
- Put **both** dash and game1 behind Cloudflare (orange cloud). Kill game1's direct A record — this closes the current live leak.
- Cloudflare SSL mode **Full (strict)**; issue an origin cert for Box A.
- Point dash + game1 A records at Box A's IP (proxied).
- Verify the app end-to-end through CF.

### Phase 3 — Lock the origin
- Firewall Box A (see §4) — 80/443 only from Cloudflare IP ranges, SSH from your IP.
- nginx: `allow <CF ranges>; deny all;` on the app vhosts (or Authenticated Origin Pulls / mTLS).
- Confirm a direct `curl https://<BoxA-IP>` is refused; only CF gets through.

### Phase 4 — Decommission control plane from the old box
- Stop `astrobyte-userbot` / `astrobyte-adminbot` on the old box.
- Remove the dash/game vhosts from the old nginx (leave your other sites alone).
- Old box keeps only the VPN plane (Box B role) if that's where Marzban stays.

### Rollback at any phase
- DNS TTL low (60s) during migration; flip A records back to the old box to revert.
- Old box stays fully intact until Phase 4 is verified for 24–48h.

---

## 4. Hardening — applies to whichever box (DRAFT commands, NOT run)

> ⚠️ **SSH is on 52217. The `ufw allow 52217` line MUST go in and be confirmed
> BEFORE `ufw enable`, or you lose access.** Ideally restrict it to your IP.

```bash
# ---- Box A (control plane) — review every line first ----
ufw default deny incoming
ufw default allow outgoing
ufw allow from <YOUR_ADMIN_IP> to any port 52217 proto tcp   # SSH — do NOT skip
# 80/443 only from Cloudflare (script pulls the official CF ranges):
for ip in $(curl -s https://www.cloudflare.com/ips-v4); do ufw allow from $ip to any port 80,443 proto tcp; done
for ip in $(curl -s https://www.cloudflare.com/ips-v6); do ufw allow from $ip to any port 80,443 proto tcp; done
ufw enable    # only after the SSH rule is confirmed present

# ---- Box B (VPN plane) ----
# allow VPN client ports (reality/xray) as your inbound configs require
# allow Marzban API port ONLY from Box A's IP:
ufw allow from <BOX_A_IP> to any port 62050 proto tcp
# SSH allowlisted to your IP; everything else denied
```

Also, regardless of box:
- **CUPS (`:631`)** — `snap stop cups` / disable, or bind localhost. No reason to be public.
- **RustDesk (`21115–21119`)** — restrict to your admin IP or a private tunnel.
- **Marzban `:62050`** — never public; CF-tunnel it or firewall to Box A only.
- **Cloudflare**: Bot Fight Mode, a rate-limit rule on `/api/admin/login` and `/api/dashboard/*`, and (optional) Geo rules.

---

## 5. App-level changes needed (small — most already done)

- ✅ Admin host gate shipped (`ADMIN_ALLOWED_HOSTS`, 404s admin off game1).
- `DATABASE_URL` → Box A local Postgres.
- `MARZBAN_BASE_URL` → Box B private address.
- Keep `WEBAPP_SESSION_SECRET` + `ADMIN_PANEL_SECRET_KEY` identical across the move (else all sessions/2FA reset).
- `DASHBOARD_PUBLIC_BASE_URL` / `GAME_PUBLIC_BASE_URL` unchanged (still dash/game domains).
- Move `scripts/backup_db.py` output **off-box**, encrypted (the DB is the PII — its backups are too).

---

## 6. Things only you can do (not code)

- Provision Box A; decide dedicated vs shared-with-other-apps (recommend dedicated).
- Cloudflare dashboard: orange-cloud all domains, Full-strict TLS, WAF/rate-limit, origin cert.
- DNS record changes + TTL lowering for cutover.
- Decide the fate of the other services on the current box (CUPS, RustDesk, salesbot, aureon, the 8123/8790/4416 apps).

---

## 7. Honest caveats

- **Certificate Transparency is already public.** Every LE cert (dash, game1, all pashanimx domains) is on crt.sh forever; you can't un-publish the domain names. That's fine *if* the IP behind them is CF-hidden and the origin is locked — knowing the domain then reveals nothing reachable.
- **Historical DNS** (SecurityTrails etc.) may already have archived the current IP for these domains. Moving to Box A gives a *fresh* IP with no history — a real benefit of the move beyond isolation.
- **The VPN nodes are inherently discoverable.** No plan hides them; the strategy is that discovery of them costs you a blockable node, not your users or your control plane.
- Moving is real work with a cutover risk window; the phased plan + low TTL + keeping the old box warm keeps it reversible.
