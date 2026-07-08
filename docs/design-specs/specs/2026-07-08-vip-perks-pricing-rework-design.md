# VIP Perks & Pricing Rework — Design (2026-07-08)

Decided in chat with Pasha (audience/econ/mechanism/pricing/lifetime answered
explicitly; soft-perk trim delegated). Implemented the same night.

## Audience & goal

VIP is FOR HEAVY USERS (150GB+/month). One-month VIP must be a clear win
(~15–25% cheaper overall vs no VIP) so heavy users convert and renew.

## The offer ("both barrels")

1. **VIP-exclusive plans** (the magnet), ~2.1k toman/GB vs ~3.8k retail:
   - 150 GB / 35d — 320,000
   - 200 GB / 35d — 420,000
   - 300 GB / 35d — 600,000
   - The 20% VIP discount does **not** stack on these (margin control).
   - Non-VIP buyers are rejected on the money path (`QuoteError('vip_only_plan')`
     in `flows/pricing.quote_purchase`) and the plans are hidden from the
     non-VIP shop window (`/api/dashboard/purchase/plans` filters).
2. **20% off everything else** — normal plans and charges, unchanged.
3. Soft perks (pitch trimmed to 4 bullets): exclusive plans · 20% off ·
   priority support & receipt approvals · platinum look/badge.
   Auto-claimer stays as a feature but leaves the pitch; the "2/3-month
   plans at flat rate" perk is retired (redundant vs exclusive plans).

## Membership pricing (lifetime killed)

| Tier | Price (toman) | ≈/month | shown as سود |
|---|---|---|---|
| ۱ ماهه | 139,000 | 139k | — |
| ۳ ماهه | 329,000 | ~110k | ~21% |
| ۶ ماهه | 549,000 | ~91k | ~34% |
| ۱ ساله | 899,000 | ~75k | ~46% |

Lifetime (1.49M) removed — no forever-liability with ~2,800 users incoming.

## Why the math works

150GB/month retail ≈ 567k (100GB plan + 50GB charge). VIP: 320k plan + 139k
membership = 459k → **~19% cheaper**, inside the 15–25% target. At 300GB the
win grows (~26%): the heavier the user, the better VIP pays. Casual buyers
who take VIP for status are margin. Open input: panel bandwidth cost/GB —
if 2.1k/GB is below cost, shift the exclusive-plan ladder up.

## Touched surfaces

- `core/settings/catalog_plans.py` — VIP_PLANS ladder (no lifetime),
  PLANS defaults incl. 3 exclusive plans.
- `core/plans.json` — live catalog override (mirrors the defaults; this file
  WINS over code defaults at boot and via the admin plan editor).
- `services/flows/pricing.py` — vip_only buyer gate + no-stack rule
  (single enforcement point for bot AND webapp).
- `api/routes/dashboard_purchase/plans_user/plans_list.py` — non-VIP
  shop hides vip_only; payload now carries `vip_only`.
- `frontend/.../profileI18n.js` — 4 benefit bullets + FAQ A8, fa/en.
- Bot flow already gated vip_only (`handlers/user/purchase/common.py`).

## Verified

- Money tests green: pricing, checkout_coupon, purchase_service,
  economy_safety, charge_service.
- Live catalog probe: 3 exclusive plans + 4-tier membership, no lifetime.
- Userbot restarted 2026-07-08 01:39 UTC, healthy.
