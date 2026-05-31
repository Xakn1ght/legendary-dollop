<!-- Preserved copy of Pasha's uploaded v2 spec (2026-05-31). Source of truth for
the Star Season + Coupon + VIP Cashout mechanics. The final unified map
(2026-05-31-final-reward-system-map.md) references and reconciles this. -->

# ASSTROO Star Season + Coupon Rewards Spec (v2)

> This is the verbatim spec Pasha provided. See the final map for how it slots into
> the full economy and what was decided around it.

## Core model
Referrals / qualifying actions → user earns SEASON STARS → stars rise during the
active 90-day season → hitting milestones auto-unlocks COUPONS → coupons saved in
wallet, expire in 45 days → season ends → season stars reset to 0 → next season.

Stars are NOT spendable currency, NOT a permanent wallet. They are seasonal
milestone progress. `SEASON_STAR_IS_SPENDABLE=False`, `SEASON_STAR_RESETS=True`.

## Star earning (referrals only)
- Qualifying purchase: referred user buys a ≥20GB plan (`MIN_REFERRAL_STAR_PLAN_GB=20`).
- Normal purchase → +1 season star; purchase with reserved auto-renew → +2 (max 2).
- Stars are ONE of the 4 referral choices (see final map). One choice per purchase.

## Coupons
Saved in wallet, VPN-only, no cashout, expire 45 days, 1 per purchase, no stacking.
`COUPON_EXPIRY_DAYS=45`, `ONLY_ONE_COUPON_PER_PURCHASE=True`, `COUPONS_CAN_STACK=False`.

## Milestone ladder (auto-unlock once per season, dedup by claim_key)
- 3★ 10% discount coupon · 5★ 20% discount · 10★ 10GB free traffic · 15★ 50% discount
- 20★ free 20GB/35d plan · 25★ free 40GB/35d plan · 30★ free auto-renew (≤100GB, once)
- 40★ VIP Pack (free auto-renew + 30d priority support + VIP badge + VIP theme)
- 50★ Legend Pack (free auto-renew + 100GB bonus + 60d priority support + Legend badge + theme)

Claim dedup: `star_season:{season_id}:milestone:{stars}:user:{user_id}`.
Auto-unlock on reaching milestone; never lose an unlocked milestone. Season reset
zeroes stars only — existing coupons keep their own expiry.

## VIP Promoter Cashout (gated, real money)
Only for high-trust promoters: `MIN_ACTIVE_REFERRALS=20`, account age ≥30d, manual
approval, no abuse flags. Active referral = referred user bought ≥20GB plan.
- Rate 5% (vs 10% VPN credit) — cash is lower because it leaves the business.
- Monthly windows, min payout 100k, max 1M/month, 7-day hold after purchase,
  ignore refunded/cancelled/self-referrals.
- Shown as referral Choice 5 only when eligible. Stars/coupons can NEVER convert to cash.

## Deferred
Coins (future shop currency) and XP/levels are separate phases. Mini-shop kept
separate from Star Season.

## Suggested tables
`star_seasons`, `user_star_progress`, `star_milestone_claims`, `reward_coupons`,
`vip_cashout_transactions` (full field lists in original; see final map for the
reconciled schema plan).
