# Merging the sales bot into this project

The live sales bot (`@AstroByteSalesBot`, 13.5k lines in one file on the
Pashani box) and this project sell the same thing in two different ways. This
is the plan to end up with one bot.

Decided 2026-08-24 with Pasha. Update this file when a decision changes.

---

## Direction

- **This project is the base.** It has the dashboard, admin panel, rewards,
  seasons and arcade — 65k lines the sales bot has none of. Moving that into a
  13.5k single file would be far worse than the reverse.
- **Sync is one-way: sales bot → here.** Pasha keeps fixing the live bot; those
  changes get pulled over. Nothing is ever pushed back to that server. Two-way
  editing is exactly what made the two drift apart.
- The live bot keeps serving customers untouched until the merged bot is
  proven. Both already share the PasarGuard panel and the SMS claim database,
  so they can run side by side.

## What the merged bot sells

Everything from both sides. Prices are **this project's**, not the live bot's.

| Product | Price | Where it comes from |
|---|---|---|
| Test | free, 250 MB / 10 days | sales bot |
| Pro test | free, 250 MB / 10 days, IR-Tun route only, once per 30 days | sales bot |
| 20 GB | 90,000 | here |
| 40 GB | 180,000 | here |
| 60 GB | 250,000 | here |
| 100 GB | 400,000 | here |
| Custom | 1–300 GB, curve re-anchored to the prices above | both |
| Pro / IR-Tun | per GB: 6,500 up to 10 GB, then 5,000 | sales bot |
| VIP 350 / 400 / 500 GB | 862,500 / 975,000 / 1,187,500 | here |
| VIP membership | 139k month … 899k year | here |

**Known consequence:** the live bot currently charges 85k / 170k / 235k / 380k.
Moving customers to this project's prices is a ~6% rise. Pasha chose this
deliberately.

**Open:** should Pro / IR-Tun per-GB prices also rise? There is no competing
number, so they stay as-is until Pasha says otherwise.

## Referrals — a gate here, a reward there

The two systems share a name and nothing else:

- **Sales bot:** `REQUIRE_REFERRER = True`. You cannot buy unless someone
  referred you. An invite-only gate with an approval status per customer
  (`referrer_status`, `referrer_approved_by`, …).
- **This project:** referrals are a reward. Refer people, earn credit, stars
  and tier percentages. Entirely optional.

**Decision (2026-08-24):** keep the gate AND add the rewards. Still invite-only,
but referring now pays. The 985 already-referred customers carry over as-is.

## Customer data and cutover

The live bot holds real history: **1,237 customers** (985 with a referrer),
**4,593 orders**, **1,486 subscriptions**. Referrer data lives on the customer
record, not a separate table.

A copy sits at `/opt/incoming/bakbot/` and is used only to design the
migration — field mapping, edge cases, weird records. It will be weeks stale by
go-live, so **on cutover day Pasha sends a fresh export and the migration runs
against that**. Nothing is imported into this project's database before then.

The 210 MB of `user_logs/` and 926 MB of dated `backups/` were deleted from the
copy; the rollback `sales_bot.*.py` sources were kept.

## Pro vs VIP — not the same thing

They were built separately and look similar, but:

- **Pro / IR-Tun** is a *route*: a premium network path that works on all
  Iranian operators. Sold per GB. Its own PasarGuard group
  (`PASARGUARD_IR_TUN_GROUP_ID`).
- **VIP** is a *membership*: 139k/month, gives 20% off normal purchases and
  unlocks the big 350/400/500 GB plans.

Both survive. A VIP member buying Pro should get the VIP discount, same as any
other purchase (Pricing Parity Law in CLAUDE.md).

---

## Slices

One at a time. Do not start the next until the previous works.

### Slice 1 — Purchase flow (bot side DONE 2026-08-24)

The sales bot's buying experience, which Pasha says works well.

- [x] 1.1 Merged catalog. `test`, `pro_test` and `pro:<gb>` resolve as VIRTUAL
      products in `core/products.py`, not rows in `PLANS` — `PLANS` is iterated
      raw by the Mini App grid, the charge grid and `core/coupons`, all of
      which would render a free 250 MB tile and a priceless Pro tile.
- [x] 1.2 Free trials: 7-day normal / 30-day Pro allowances counted
      independently, derived from the subscriptions table, instant
      provisioning with no name and no receipt.
- [x] 1.3 Pro routing to `PASARGUARD_IR_TUN_GROUP_ID`, with the panel template
      fast path suppressed so a Pro order cannot land in the normal group.
- [x] 1.4 Two-level Normal/Pro inline menu; the two never share a screen.
- [ ] 1.5 Delivery banners - DEFERRED. Pasha wants them REDESIGNED, not ported;
      do not copy the sales bot's templates.json as-is.
- [x] 1.6 Renewal flow. Mostly already here: the 5 GB eligibility gate,
      carryover capped at 5 GB, and native next_plan booking all existed, and
      the low-traffic/expiry reminder DMs already carry a renew button. Only
      gap was ordering - the subscription's current plan now sits first in the
      renewal keyboard. The sales bot's 10% late-renew discount was
      deliberately NOT ported (Pasha, 2026-08-29): it would have to apply on
      bot, Mini App and charge under the Pricing Parity Law. Its days-left
      warning was skipped too - booking early is the intended use of next_plan
      here, so the warning would be noise.

**Not yet done for slice 1:** the Mini App still shows only the `PLANS` grid —
free trials and Pro are bot-only until the webapp learns the virtual products.
Pro per-GB pricing is 7,000/GB up to 10 GB then 5,500/GB; the step down at
10 GB is deliberate (it pushes buyers past 10 GB).

### Slice 2 — AI support

Port `support_ai.py` (787 lines): Telegram Business chat, corpus retrieval,
intent/risk gates, rate limits. Self-contained and touches no money.

### Slice 3 — Receipt AI

Compare `sms_ai.py` on both sides first — they were kept in sync as twins, so
this may already be mostly done.

### Slice 4 — Usage card images

Pillow-rendered Persian status images (`usage_card.py`).

### Slice 5 — Cutover

Move customers from the live bot to the merged one. Needs its own plan. Must
carry over: customer records, referrer links and approval status, active
subscriptions and their panel names, and order history. Fresh export on the
day, never the stale copy.

---

## Things that must not be lost

- The rewards, referrals, seasons and arcade in this project. That is the whole
  reason this project is the base.
- The sales bot's money safety rules: fail closed, never synthesize receipts or
  approvals, amount-only SMS approvals hard-gated. Already mirrored in
  `CLAUDE.md` here.

## Where the code is

Read-only copy of the sales bot: `/opt/incoming/bakbot/`
Its own notes: `AGENTS.md`, `PROJECT_MEMORY.md`, `HANDOFF.md` in that folder.
