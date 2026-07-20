# Notification Center Rework — Design

Date: 2026-07-20
Status: approved by Pasha (chat), pending spec review
Scope: user-facing notifications only (admin-bot alerts like node_watch stay as they are)

## Goal

One notification system instead of two loosely-glued ones. A notification is stored once,
delivered everywhere it should be (dashboard center + optional bot DM), updates the open
Mini App instantly, and the center gets a cleaner structure within the existing glass/tokens
design language. Persian-first, both languages, no emojis anywhere.

## Current state (mapped 2026-07-20)

- `notifications` table (`src/app/database/models/_ticket.py`) with free-string `type`,
  16 distinct values written today from ~20 scattered call sites.
- Dashboard bell polls `GET /api/dashboard/notifications` (adaptive 5-30s, paused when hidden).
- Bot DMs are sent ad-hoc at most of the same call sites, with separate wording; several
  set `sent_to_bot=True` but never stamp `bot_message_sent`, so a bot-enabled admin
  broadcast can replay old DMs (latent bug).
- An in-process `notification_queue` worker in `main.py` is dead code (nothing enqueues).
- Job alerts (low data, expiry) are bot-only and never appear in the center.
- `get_unread_count` loads full rows; `clear-history` deletes unread items too.
- Mixed English/Persian titles; emoji debt at several call sites.

## Design

### 1. Single write path: `services/notify.py`

New module owning the full lifecycle:

```
async def notify(session, user_id, type_: NotificationType, ctx: dict) -> Notification
```

- Renders title/body from the template catalog (fa + en stored; user language picked at
  render time for the DM, dashboard rows store both via `title`/`message` in the user's
  language and the catalog key for re-render).
- Writes the `notifications` row (one insert, `sent_to_webapp` per catalog policy).
- Sends the bot DM when the catalog says so, stamps `bot_message_sent` + `bot_message_id`
  in the same transaction scope, with the existing user-bot resolution and error swallowing
  (DM failure never blocks the row).
- Pushes to open WebSocket sessions (section 3).
- All current call sites migrate to `notify()`; direct `bot.send_message` for notification
  purposes is removed at those sites. The admin broadcast path uses the same function
  (type `general`), which fixes the replay bug by construction.

### 2. Typed catalog: `core/notification_catalog.py`

Enum `NotificationType` covering today's 16 types plus the job alerts becoming rows:
`low_data`, `data_finished`, `expiry_soon`, `expired`.

Per type the catalog defines:
- `category`: money | service | rewards | support | system
- `icon`: SVG name the frontend maps (no emojis)
- `deeplink`: dashboard route (charge -> charge page, purchase/service -> services,
  rewards/challenge -> tasks page, ticket -> support chat with ticket id, system -> none)
- `dm`: whether a bot DM is sent (money events, ticket replies, account status: yes;
  most informational ones: dashboard-only)
- fa/en title + body templates (str.format with ctx keys; validated in tests)

No DB schema change: `type` remains the key; category/icon/deeplink are computed
server-side into the API/WS payload. Existing rows keep working (unknown legacy types
fall back to category=system, no deeplink).

### 3. Live delivery over the existing WebSocket

- Reuse the support-chat WS infrastructure: a per-user dashboard channel
  (`ws/notifications` or a message kind on the existing session socket — implementation
  picks whichever the current WS auth/session plumbing makes cheaper).
- `notify()` publishes `{notification: {...}, unread_count: n}` to that user's open sessions.
- Frontend: on WS message, prepend to list + set badge; polling drops to a slow fallback
  (60s) used only when the socket is down; `unread-count` endpoint gets used on reconnect.
- `get_unread_count` becomes a real `SELECT COUNT(*)`.

### 4. The center UI (React shell, same design language)

- Same Sheet, glass/tokens, tier-world theming; new co-located CSS module for the
  notification list (migrating the `.notification-item` family out of index.css with a
  pointer comment, per the styling convention).
- Structure: grouped by day (Today / Yesterday / date), category icon per row, unread
  accent bar, timestamp in Persian digits for fa, tap = mark-read + deeplink navigation
  (soft nav within the shell; support deep-link keeps the existing hard-nav).
- Header actions: mark-all-read (kept), clear-history (fixed: deletes READ items only).
- Empty state kept. RTL-first, `fmt` for numerals, min 16px fonts, transform-only animation.

### 5. Cleanups riding along

- Delete the dead `notification_queue` worker + its handler parameters in `main.py`.
- Delete dead CRUD helpers (`create_ticket_notification`, `delete_notification`) and
  rename/fix `delete_read_notifications` behavior to match its name.
- `check_low_data_job` writes rows through `notify()` (throttle keys unchanged).
- Update `src/app/docs/` notification references (they document a wrong model path today).

## Testing

`tests/test_notify_service.py` (new): template rendering fa/en for every type (asserts
no emojis, all ctx keys used), row+DM policy per type, DM failure does not block row,
broadcast replay regression (old sent_to_bot rows are never re-sent), unread count.
`tests/test_notification_ws.py` (new): push payload on notify, unread_count correctness.
Existing suites (tickets, charge, purchase) re-run since their notification calls migrate.

## Rollout (each phase tested + committed + pushed separately)

1. Catalog + `notify()` + tests (nothing calls it yet).
2. Migrate all call sites in 2-3 batches (money flows, tickets/support, admin/user mgmt),
   removing ad-hoc DMs as each batch lands.
3. Jobs start writing rows; dead-code cleanup.
4. WS push + frontend consumption (badge/list live update, polling fallback).
5. Center UI rebuild + CSS module migration + rebuild bundle.

Python changes go live on the next service restart (coordinated with Pasha); static/React
changes serve immediately.

## Out of scope

Per-type user preferences/mute (Profile toggle stays cosmetic for now), admin-side
notification analytics, push when the Mini App is closed (bot DM already covers it).
