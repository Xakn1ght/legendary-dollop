# Star Ladder Simplification — Design

_2026-07-06 · Approved by Pasha in brainstorming session. Replaces the top of the
Star Season ladder defined in `2026-05-31-final-reward-system-map.md` §star-season._

## Problem

The 40★/50★ milestones mint bundle coupons (`vip_pack`, `legend_pack`): free
auto-renewal + bonus GB + priority-support days + badge + theme in one object.
Owner verdict: confusing to users ("stupid"), scary financially, and the 30★
`free_autorenew` milestone confuses even the owner. General money anxiety.

## Economics (why this design is safe)

At $1 ≈ 175k toman: 3 servers ($20/mo) ≈ 3.5M toman for ~50TB/mo → traffic cost
≈ **70 toman/GB**, retail ≈ 4,500 toman/GB (~64×). Whole infra ≈ 41 sales of the
20GB plan per month; user base ≈ 2,000.

Therefore: VPN-value prizes (GB, plans, VIP time) cost ~1–2% of their perceived
value. The only reward class that costs face value is **cash credit** (via
cashout). Design rule: **the ladder never mints credit.** Cash exposure of the
entire new ladder: zero. Biggest single prize (free 60GB plan) costs ~4.2k toman
of traffic while reading as a 250k prize.

## New ladder (`STAR_SEASON_MILESTONES` in `src/app/core/rewards_config.py`)

| Stars | Name | coupon_type | payload |
|---|---|---|---|
| 1 | First Spark | `discount_percent` | 5% |
| 3 | Starter Discount | `discount_percent` | 10% |
| 5 | Better Discount | `discount_percent` | 20% |
| 10 | Free Traffic Boost | `free_gb` | 10 GB |
| 15 | Half Price | `discount_percent` | 50% |
| 20 | Free 20GB Plan | `free_plan` | 20 GB / 35 d |
| 25 | Free 40GB Plan | `free_plan` | 40 GB / 35 d |
| 40 | Season Champion | `free_plan` | 60 GB / 35 d, + `"badge": "Champion", "theme": "champion"` |
| 50 | Season Legend | `vip_days` (new) | 30 days VIP, + `"badge": "Legend", "theme": "legend"` |

(`badge` is the display string, `theme` the accent key — same conventions the
old pack payloads used, so prefs storage and the unlock UI stay compatible.)

Removed entirely: milestone **30★** (`free_autorenew`), coupon types
`vip_pack` and `legend_pack`. Milestones 1–25 unchanged. Nine milestones total;
every prize is one plain thing.

## Badge / theme grants move to the milestone claim

Today badge+theme unlock happens inside pack-coupon grant logic
(`apply_coupon_pack_grants`). New model: a milestone entry may carry optional
`"badge"` and `"theme"` keys (40★ and 50★ do). At claim time the season engine
grants them directly into user prefs (`unlocked_themes`, `badge`) — the same
storage the packs used, so the profile/accent unlock UI keeps working unchanged.
Coupons themselves are pure value (free_plan / vip_days), never bundles.

## New coupon type: `vip_days`

- Payload: `{"days": 30}`.
- Redeemed **from the wallet directly** (not at checkout): one confirm dialog →
  `vip_until = max(now, vip_until) + 30d` → coupon consumed. Reuses the existing
  VIP activation helper (same field admin VIP approval sets).
- Surfaces: dashboard wallet/tasks coupon list gets a "فعال‌سازی" action for this
  type; bot rewards menu labels it "🎖 یک ماه VIP".
- Not spendable at checkout; checkout coupon picker filters it out.
- If the user is already VIP, days stack on top (extends expiry).

## Badge assets

Owner picked: **Champion = gold hexagonal rocket-shield** (concept #3),
**Legend = magenta phoenix-comet in ring** (concept #1). Production steps:
regenerate each as a single centered emblem on transparent background (~256px
PNG), save to `src/app/webapp/static/badges/champion.png` and `legend.png`.
Shown at: profile hero chip (replaces text-only chip), tasks-page ladder
milestone nodes (40★/50★), and the bot rewards screen as emoji-prefixed text
(🥇/☄️ — no photo messages; keeps the bot flow simple). Accent themes
`champion`/`legend` in `tokens.css` are untouched.

## Code touchpoints

- `src/app/core/rewards_config.py` — ladder table above; comment updates.
- `src/app/database/repos/reward/_season.py` — milestone claim: strip pack
  logic, add badge/theme grant from milestone keys, mint `vip_days` coupons.
- `src/app/services/flows/purchase.py`, `services/flows/pricing.py`,
  `services/subscription_processing.py` — remove `vip_pack`/`legend_pack`
  branches (checkout math and provisioning bonus-GB paths); `free_autorenew`
  RENEWAL-APPLY code stays (wallet coupons from the old 30★ must keep working
  until they expire; only minting stops).
- New wallet redemption endpoint/handler for `vip_days` (dashboard API +
  bot callback), calling the shared VIP activation helper.
- `src/app/handlers/user/rewards/menu.py` — coupon label for `vip_days`;
  remove pack labels.
- Dashboard React (`TasksPage`, `ProfilePage`, purchase coupon filter) —
  render new types, badge images, drop pack references (`applyUnlocks` reads
  prefs, which still work; only the season-coupon fallback scan changes).
- Season API serializer — already generic over payload; verify only.

## Migration / rollout

Final DB reset happens before launch, so no data migration. Sequence: config +
code swap now → test wallets holding pack coupons lose them at the reset (test
data, accepted). Old `free_autorenew` coupons remain honored by the unchanged
renewal path until natural expiry (45 d). No alembic migration needed (coupon
type is a string column; no schema change).

## Testing

- Update `tests/test_season_engine.py` (ladder shape: 9 milestones, no 30★,
  40★ = free_plan 60GB, 50★ = vip_days) and `tests/test_season_api.py`.
- New `tests/test_vip_days_coupon.py`: claim at 50★ mints coupon; redeem sets
  `vip_until` +30 d; stacking when already VIP; coupon consumed exactly once;
  not offered at checkout.
- `tests/test_economy_safety.py` extended: assert no ladder milestone mints
  credit/cash (iron-rule guard for this design).
- `tests/test_checkout_coupon.py` — confirm `vip_days` filtered from checkout.

## Out of scope

Star **earning** rules (still referral-only, 1–2★ per qualifying purchase),
season length/reset mechanics, promoter credit cut, cashout gates — all
unchanged. VIP membership pricing/perks unchanged (separate track).
