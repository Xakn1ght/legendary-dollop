# Rewards & Pricing — Phase 1 Implementation Plan (2026-05-30)

Implements Phase 1 of `../specs/2026-05-30-rewards-pricing-design.md`.
Detailed reward values: `/asstroo_rewards_pricing_spec.md`. Design doc wins on conflicts.

**Branch:** `rewards-pricing-rework`. Commit after each step (plain messages).
Each step is independently testable; stop and verify before moving on.

**Out of scope (deferred):** arcade score→reward tiers, star pieces, arcade streak
bonus, star-economy rework. Don't touch level-up logic or rebuild challenge architecture.

---

## Step 0 — Safety net
- Confirm clean working state for files we'll touch; git-tag a restore point
  `rewards-phase1-start-<ts>`.
- Locate the test runner (pytest?) and confirm existing reward/pricing tests pass
  before changes, so regressions are attributable.

## Step 1 — Plan prices + cleanup
**Files:** `src/app/core/plans.json`, `src/app/core/settings/catalog_plans.py`
(+ `plans_layout.json`/`plans_order.json` if they duplicate prices).
- Set 20→90,000 · 40→180,000 · 60→250,000 · 100→400,000; keep `days: 35`.
- Delete junk plan `"aaaaaaaaaaa"` (88,888t/1GB).
- Grep for any hardcoded legacy prices (67/120/175/285 or 65/130/190/320) elsewhere;
  replace with the catalog.
**Verify:** load catalog in a shell; assert the 4 prices + 35 days. Buy-flow smoke
check that purchase pages read new prices.

## Step 2 — Aligned custom-GB pricing
**Files:** new `src/app/core/pricing.py` (or extend `catalog_plans.py`).
- Implement `round_price()` + `custom_gb_price(gb)` exactly as in design doc §2
  (piecewise hitting 10/20/40/60/100 anchors; 1–300 GB bounds).
- Wire wherever custom GB is currently priced (recon: `handlers/user/charge/*`,
  `subscription_processing.py` — confirm the real call site; there may be no live
  custom-GB feature yet, in which case expose the function for future use).
**Verify:** unit test the anchor table (1=5k,10=50k,20=90k,40=180k,60=250k,80=325k,
100=400k,150=600k,300=1.2M) + out-of-range raises.

## Step 3 — Central rewards config
**Files:** new `src/app/core/rewards_config.py`.
- Move/define: `ACHIEVEMENTS` (new 9), `CASHBACK_RATES` + `CASHBACK_MILESTONE`,
  `DAILY/WEEKLY/MONTHLY_CHALLENGES`, loyalty-shop values, XP caps,
  `GAMEPLAY_CREDIT_CAP_PER_MONTH = 30_000`, `REFERRAL_BONUS_XP = 50`,
  referral choice percentages. **No arcade/star-piece constants yet.**
- Goal: one editable file so values change without touching logic.
**Verify:** import module; assert constants present and well-typed.

## Step 4 — Play-streak tracking (reward-agnostic)
**Files:** streak grant site (find via `login_streak`/`last_daily_login` usage),
`daily_game_plays` repo.
- Disable the daily **login** streak *grant* (leave column; stop incrementing/rewarding).
- Derive **play-streak** = consecutive days with ≥1 valid arcade run, from
  `daily_game_plays.play_date` (`streak_on_play` already exists — reuse if correct).
- Add `play_streak_days`/`last_played_date` to `users` only if not derivable; prefer
  computing from `daily_game_plays` to avoid migration.
**Verify:** simulate plays across dates; assert streak increments/resets correctly;
assert passive login no longer advances any streak.

## Step 5 — Referral CHOICE model (+50 XP)
**Files:** `api/routes/dashboard/referrals/redeem_reward.py` (redeem exists),
referral-reward creation site (on referred purchase), notification path.
- On a **referred** user's purchase (any sub, any amount): compute the four options
  — 10% of paid (credit), 10% of GB, 10% of days, 1 star/sub (cap 2) — and create a
  pending `referral_rewards` voucher carrying the choice set; notify referrer to pick.
- Reuse existing redeem flow to apply the chosen reward (traffic/days→sub, credit→wallet,
  star→existing star system). All credit = store-credit only.
- Grant **+50 XP** to referrer per referral regardless of choice.
- Triggers on every referred purchase (ongoing), not first-only.
**Verify:** referred purchase → voucher with 4 correct options; redeem each path
applies right value; +50 XP always; double-redeem blocked (Step 10).

## Step 6 — Achievements → new 9
**Files:** `database/repos/reward/_achievements.py`, seed/init path, `models/_reward.py`.
- Reseed to the 9 spec achievements (Blast Off … Perfect Score) with config-driven
  conditions; "active referral" = referred user bought ≥20GB plan.
- Migration: archive/ignore old `user_achievements` rows; users keep credit already
  granted (no clawback, no auto re-grant).
- Star grants on achievements flow into the **existing** star system unchanged.
**Verify:** fresh + existing users; old rows archived; qualifying actions unlock new
ones once; idempotent (Step 10).

## Step 7 — Cashback rebalance + dedup
**Files:** `database/repos/reward/_points.py` (`calculate_and_award_cashback`).
- Switch to GB-keyed `CASHBACK_RATES` {20:.077,40:.09,60:.10,100:.12}; custom-GB →
  round down to nearest band (≥100→.12). Round total to nearest 1,000.
- **Dedup:** add `cashback_processed` (bool) to subscriptions/receipts OR a
  `cashback_batches` record; only count purchases once. Decide mechanism here.
**Verify:** spec examples (5×20=35k, 5×40=81k, mixed=112k); re-running does NOT
re-pay; partial groups (<5) pay nothing.

## Step 8 — Challenge + loyalty-shop configs
**Files:** challenge seed/config, `handlers/user/rewards/loyalty_shop.py`.
- Define daily/weekly/monthly challenge configs from spec (no logic overbuild).
- **Reconcile loyalty shop:** live is ~1:1 (5000 pts→5000 credit); spec is 50:1
  (100 pts→5000 credit). Pick one (design doc leans spec's 100→5k) and reprice all
  items consistently. ⚠️ Decision needed before coding this step.
**Verify:** shop items priced consistently; a weekly challenge's loyalty payout buys
a sensible amount (not a free plan).

## Step 9 — Monthly gameplay-credit cap
**Files:** challenge-reward grant path; per-user-per-month counter.
- Enforce `GAMEPLAY_CREDIT_CAP_PER_MONTH` on **challenge** credit now (arcade credit
  hook = TODO for deferred session). Once capped, still grant XP/stars, not credit.
- Track via a monthly counter (reuse `daily_star_caps` pattern or reward_history sum).
**Verify:** simulate a month of challenge credit; credit stops at cap, XP continues.

## Step 10 — Claim-key / anti-duplicate
**Files:** central helper (new in `rewards_config.py` or a `rewards_claims` util);
all grant sites (achievements, daily/weekly/monthly, cashback, referral).
- Use claim keys per design §20. Decide: reuse `reward_history(source,source_id)` vs
  new `reward_claims` table with unique `claim_key`. Wrap each grant in a
  check-then-claim.
**Verify:** re-trigger each reward type; second attempt is a no-op.

## Step 11 — Tests
**Files:** `tests/` (match existing layout).
- Cover: plan prices, custom GB anchors, referral 4 choices + 50 XP, cashback values
  + dedup, achievement unlock idempotency, gameplay-credit cap, claim-key dedup.
**Verify:** full suite green.

---

## Decisions to resolve in-flight
1. **Cashback dedup mechanism** — `cashback_processed` column vs `cashback_batches`.
2. **Claim dedup home** — extend `reward_history` vs new `reward_claims` table.
3. **Loyalty point value** — keep live 1:1 or adopt spec 50:1 (reprices the whole shop).
4. **Custom-GB live wiring** — does a custom-GB purchase flow exist, or is the function
   forward-looking only?

## Risks
- Price change touches buy/charge/admin flows — grep all price reads (Step 1).
- Loyalty repricing changes existing balances' purchasing power — communicate/migrate.
- Referral "every purchase" commission could surprise at scale — monitor; capped by
  being store-credit + revenue-funded.
