# Rewards & Pricing — Design / Reconciliation (2026-05-30)

Authoritative design for the rewards + pricing rework. Pairs with the detailed
value reference in `asstroo_rewards_pricing_spec.md` (root). Where the two differ,
**this file wins** — it records decisions made after checking the spec against the
live codebase.

## Goal
Reward loyal users generously *in perception* while protecting margin: rewards are
either free-to-give (XP/stars/badges), store-credit only (spendable on VPN, never
cash), or growth-funded (referrals). No hard cash payouts, no uncapped free GB.

## Codebase reality (verified 2026-05-30)
- Models are a **package**: `src/app/database/models/` (not a single `models.py`).
- Plan prices live in `src/app/core/plans.json` (+ `plans_layout.json`,
  `plans_order.json`, `catalog_plans.py`).
- Loyalty shop already exists: `handlers/user/rewards/loyalty_shop.py`.
- Cashback already exists: `RewardRepository.calculate_and_award_cashback`
  (`database/repos/reward/_points.py`) — **rates differ + no dedup** (see below).
- Star tiers/claims exist (`star_reward_tiers`, `user_star_reward_claims`,
  `expire_star_reward_claims_job`). Stars' **sink** stays this existing system.
- `users` already has `stars, credit, loyalty_points, star_pieces, login_streak,
  last_daily_login, arcade_stars_this_month`.

## Decisions (locked with Pasha)

### 1. Plan prices — UPDATE, keep 35 days
Live `plans.json` is stale (67/120/175/285 @ 35d) + has a junk plan. Set to:
```python
BASE_PLANS = {20: 90_000, 40: 180_000, 60: 250_000, 100: 400_000}
PLAN_DURATION_DAYS = 35   # keep current 35 (goodwill), NOT spec's 30
```
Also: **delete the junk `"aaaaaaaaaaa"` (88,888t / 1GB) plan** from `plans.json`.

### 2. Custom GB pricing — ALIGNED curve (hits all 4 plan anchors)
Replaces the spec's §4 formula (which gave 40GB=170k, undercutting the 180k plan).
Piecewise, monotonic, hits 20/40/60/100 = plan prices exactly:
```python
CUSTOM_MIN_GB, CUSTOM_MAX_GB = 1, 300
def round_price(a): return int(round(a/1000)*1000)
def custom_gb_price(gb):
    if gb < 1 or gb > 300: raise ValueError("Custom GB must be 1..300")
    if gb <= 10:  return round_price(gb * 5_000)              # 10 = 50k
    if gb <= 20:  return round_price(50_000  + (gb-10)*4_000) # 20 = 90k
    if gb <= 40:  return round_price(90_000  + (gb-20)*4_500) # 40 = 180k
    if gb <= 60:  return round_price(180_000 + (gb-40)*3_500) # 60 = 250k
    if gb <= 100: return round_price(250_000 + (gb-60)*3_750) # 100 = 400k
    return round_price(400_000 + (gb-100)*4_000)              # 300 = 1.2M
```
Verified: 1=5k, 10=50k, 20=90k, 40=180k, 60=250k, 80=325k, 100=400k, 150=600k, 300=1.2M.

### 3. Cashback — adopt spec rates + ADD dedup
Rebalance `calculate_and_award_cashback` from current 3–6% to spec rates, keyed by
**GB** (not fragile price/string matching):
```python
CASHBACK_RATES = {20: 0.077, 40: 0.09, 60: 0.10, 100: 0.12}
CASHBACK_MILESTONE = 5  # award after every 5 eligible purchases
# round to nearest 1,000
```
**Critical fix:** current code re-reads "last 5 subs" each call → can double-pay.
Add a `cashback_processed` boolean (or a cashback-batch record) so each purchase is
counted once. Custom-GB purchases use the nearest band or a `default` rate (decide
in plan: simplest = round GB down to nearest of {20,40,60,100}, ≥100 → 0.12).

### 4. Monthly gameplay-credit cap — ADD (new)
Spec caps XP and star-pieces/day but not **credit**. Add a monthly cap so gameplay
can't replace paying:
```python
GAMEPLAY_CREDIT_CAP_PER_MONTH = 30_000   # ≈ 1/3 of cheapest plan; adjustable
```
Applies to arcade score credit + daily/weekly challenge credit. Referral credit and
cashback are NOT capped (they're tied to real revenue). Track per user per
year-month; stop granting gameplay credit once cap hit (still grant XP/stars).

### 5. Achievements — REPLACE with new 9
Swap the 11 seeded achievements for the spec §10 set (Blast Off, First Contact,
Squad Leader, Galactic Empire, Data Voyager, Data Commander, Streak Warrior,
Time Traveler, Perfect Score). Users **keep credit already granted**; old
`user_achievements` rows are archived/ignored (no clawback, no re-grant).
"Active referral" = referred user purchased a ≥20GB plan.

### 6. Streak — play-based, not login (spec §5)
Remove/disable daily **login** streak reward. New streak = "played ≥1 valid arcade
run today" (`daily_game_plays` already has `play_date`/`streak_on_play`). Arcade
streak bonus per spec §7 (+5%/day, cap +25%). Add `play_streak_days` /
`last_played_date` if not already derivable.

### 7. Referral rewards — CHOICE model (from Pasha's flow diagram, 2026-05-30)
Supersedes spec §9's "keep referral logic the same". When a **referred** user buys
**any sub, any amount**, the **referrer** gets a notification to **choose ONE**
reward (self-select what they value):

| Choice | Value | Cost to us | Notes |
|---|---|---|---|
| 10% of total paid | credit = 10% of that purchase price | funded by the sale | e.g. 400k buy → 40k credit |
| 10% of total GB | +10% of purchased GB on a sub | ~146t/GB, trivial | e.g. 100GB → +10GB |
| 10% of total days | +10% of purchased days | trivial | e.g. 35d → +3–4 days |
| 1 star per bought sub | **max 2** | premium currency | max 2 = one sub + one reserved charge |

- Triggers on **every** referred purchase (ongoing affiliate-style, not first-only).
- All credit is store-credit (VPN only, never cash). GB/days bonuses attach to a sub.
- **+50 XP per referral** (spec §9) still applies on top, regardless of choice.
- Reuses existing `referral_rewards` table (`reward_value, traffic_bytes,
  extra_days, credit_amount, spent`) + the existing redeem/choice notification path.

## Carried straight from `asstroo_rewards_pricing_spec.md` (no change)
- Achievements set (new 9, §10), daily/weekly/monthly challenge configs (§13–15),
  loyalty shop with 100pts→5k credit (§17), XP caps (§19), claim-key dedup (§20).
- **Do NOT touch** level-up logic (§6) or do a big challenge-architecture rebuild
  (§12, §24) — only add config so values are easy to edit. Leave TODOs.

## ⛔ DEFERRED — needs its own brainstorming session (NOT this phase)
Pasha flagged both of these as needing way more work; do **not** finalize them now.
- **Game / arcade rewards** (spec §7 score tiers, §8 star pieces, arcade streak
  bonus). The numbers in the spec are placeholders only.
- **Star economy rework** (spec §18) — star *sources, sinks, and values* all need a
  rethink. The `1 star per bought sub` referral option above is provisional.

Implication for this phase: where achievements/challenges grant **stars**, keep
granting into the **existing** star system unchanged (don't tune star values yet) —
or hold the star grant behind a TODO if it blocks. Star *pieces* / arcade star
mechanics are out of scope until the deferred session. This keeps Phase 1 shippable
(pricing, custom GB, cashback, referrals, achievements, challenge+loyalty configs,
claim dedup, credit cap) without depending on the unsettled game/star work.

## Build order — PHASE 1 (this session's scope, mapped to real files)
1. `plans.json` — new prices, 35d, delete junk plan; add price test.
2. New `core/pricing.py` (or extend `catalog_plans.py`) — `custom_gb_price()` + tests.
3. New `core/rewards_config.py` — central config: ACHIEVEMENTS, CASHBACK_RATES,
   challenge dicts, loyalty shop, caps. (Arcade/star-piece config NOT here yet.)
4. Streak tracking only: disable login-streak *grant*; derive **play-streak** from
   `daily_game_plays` (counting play-days is reward-agnostic, so it's safe now).
5. Referral CHOICE model (decision §7) + **+50 XP** per referral, via existing
   `referral_rewards` + notification path.
6. Achievements: reseed to new set + migration to archive old rows. Star grants on
   achievements flow into the **existing** star system unchanged (no tuning).
7. Cashback: rebalance rates + `cashback_processed` dedup.
8. Challenge configs (no overbuild) + loyalty shop values.
9. Gameplay-credit monthly cap — applies to **challenge** credit now; arcade hook
   left as a TODO for the deferred session.
10. Claim-key/anti-duplicate checks across all grants.
11. Tests: price, custom GB, referral choices, cashback (+dedup), achievements, caps.

## Build order — DEFERRED (separate brainstorming, see ⛔ section)
- Arcade score→reward tiers, arcade streak bonus, star pieces, arcade daily caps.
- Star economy rework (sources/sinks/values), then wire arcade credit into the cap.

## Open items for the plan
- Exact dedup mechanism: `cashback_processed` column on subscriptions/receipts vs a
  `cashback_batches` table — pick during planning.
- Where claim-key dedup lives: reuse `reward_history` (source/source_id) vs new
  `reward_claims` table with unique `claim_key`.
- Loyalty-shop "free plan"/"vip"/"priority_support" fulfillment paths.
