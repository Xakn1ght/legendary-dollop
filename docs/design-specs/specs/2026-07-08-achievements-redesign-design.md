# Achievements Redesign — Design

Date: 2026-07-08 · Status: approved (Pasha, "lets proceed and do them") · Lane: USER

## Purpose

Replace the 8 client-side "costume name" achievements (First Launch, Star
Collector, Champion, VIP Member, Task Master, Super Star, Royalty, On Fire —
Pasha: "too cringe") with 10 mission-voice achievements that have measurable
conditions, visible progress, and a real reward: **1GB of traffic each**.

## Non-negotiables (from brainstorm)

- **Server-side with validated claims.** Today achievements are computed in
  the phone; the moment they pay real gigabytes that is cheatable with one
  API call. Conditions are evaluated from the DB at claim time.
- **Paying-customer rule:** reward claims only unlock for users with **≥1
  approved purchase**. Without it, "first arcade run = 1GB" hands ~2,800
  incoming users ~3TB for zero revenue. Achievements still *display* and
  track progress for everyone; the claim button explains the rule.
- **Exposure ceiling:** 10 achievements × 1GB = max 10GB per user, one-time,
  ever. No repeatable rewards.

## The set (fa names are the product; en for the i18n pair)

| # | key | Name (fa) | Unlocks when | Progress |
|---|-----|-----------|--------------|----------|
| 1 | launch | پرتاب | first approved purchase | 0/1 |
| 2 | refuel | سوخت‌گیری | first approved top-up (charge) | 0/1 |
| 3 | starHunter | شکارچی ستاره | ≥1 season star | 0/1 |
| 4 | orbiter | مدارگرد | ≥5 season stars | bar n/5 |
| 5 | supernova | ابرنواختر | ≥20 season stars | bar n/20 |
| 6 | envoy | سفیر کهکشان | ≥5 active referrals | bar n/5 |
| 7 | fleetCommander | ناوگان‌دار | ≥20 active referrals (rhymes with the cash-out gate) | bar n/20 |
| 8 | crew | خدمهٔ ویژه | VIP active | — |
| 9 | arcadePilot | خلبان آرکید | first validated arcade score submit | 0/1 |
| 10 | inOrbit | در مدار | account age ≥90 days AND ≥1 approved purchase | bar days/90 |

Deliberately cut: «اولین پرواز» (opening the app is not an achievement).

## Reward mechanics — reuse the tested coupon rail

- Claiming a completed achievement mints a **`free_gb` RewardCoupon worth
  1GB into the wallet**, using the exact minting pattern the season/reward
  system already uses (same fields, 45-day expiry, `source='achievement'`).
- Checkout already consumes free_gb coupons with a one-per-purchase rule —
  **no new money path, no panel writes at claim time**.
- Claims are audit-logged (`record_audit`).

## Data & API

- **New table `achievement_claims`**: id, user_id FK, achievement_key
  (String(32)), claimed_at, coupon_id FK nullable. Unique (user_id, key).
  One Alembic migration.
- **Server definitions module** (e.g. `src/app/services/achievements.py`):
  a dict of key → async condition/progress evaluator reading purchases,
  charges, stars, referrals, VIP, arcade runs, account age from existing
  repos. Each evaluator returns `(progress, target, done)`.
- **`GET /api/dashboard/achievements`** (webapp auth): all 10 with
  `{key, progress, target, done, claimed, claimable, reward_gb: 1}` +
  `{ paying_customer: bool }` at the top level.
- **`POST /api/dashboard/achievements/claim`** body `{key}`: re-evaluates
  the condition server-side, checks paying-customer rule + unique claim,
  mints the coupon in the same transaction as the claim row, returns the
  coupon summary. Races guarded by the unique constraint.

## Frontend (ProfilePage achievements section rebuild)

- Grid keeps the current visual language (badges), adds: progress bar under
  in-progress items (n/target, Persian digits), a claim state (unclaimed
  done = accented "دریافت ۱ گیگ" chip; claimed = check), and a locked-claims
  note when `paying_customer` is false («با اولین خرید فعال می‌شود»).
- VIP keeps its platinum badge art (`/webapp/static/badges/vip.png`).
- Claim success → toast + the coupon appears in the wallet (tasks page
  vouchers list) with no refresh needed on profile (local state update).
- Old ACHIEVEMENTS array + i18n keys replaced by server-driven list; i18n
  file maps the 10 keys to fa/en names + one-line descriptions.

## Error handling

- `not_eligible`, `already_claimed`, `requires_purchase` FlowError-style
  codes → localized toasts.
- Endpoint failure: section renders with cached/none state, never breaks
  the profile page.

## Testing

- Script test (in-memory SQLite): each evaluator against seeded fixtures;
  claim flow (mints coupon exactly once, unique-claim race, paying-customer
  gate blocks, coupon expiry set).
- Headless probe: profile section renders bars/claim chips (mocked payload),
  fa digits, RTL.

## Out of scope

Repeatable/seasonal achievements, XP integration changes, admin CRUD for
achievement definitions (they live in code), retroactive notifications.
