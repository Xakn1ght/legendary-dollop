# Reward Economy Ledger — Live System Audit (2026-05-30)

Every currency, every faucet (earn), every sink (spend), pulled from the **live
code**, with worst-case payout math in Tomans. This is the budgeting tool: tune
faucets until the worst-case free-rider costs less than you'll tolerate.

Server cost anchor: **1,500,000 t/month** (10TB cap). Bandwidth ≈ **146 t/GB used**.

---

## 🚨 Headline finding (read this first)

**The system as built can be farmed for ~14 MILLION toman of store-credit by ONE
free user in ~4–6 months, playing the arcade daily and paying nothing — and that
credit may be cashable to real money.** That's ~9× your monthly server bill, per
freeloader. The reward *values* aren't the main risk; **three uncapped faucets +
one dangerous sink** are. Fix those before tuning anything else.

The killer chain:
```
play arcade daily ──► earn XP ──► LEVEL UP ──► each level pays huge credit
        │                                         (L20 total ≈ 13.96M t)
        ├──► direct arcade credit (≤5,000/day ≈ 150k/mo)
        ├──► star pieces ──► STARS ──► star tiers (FREE plans + lifetime VIP)
        └──► loyalty points ──► convert 1:1 ──► credit
                                                   │
                                          credit ──► CASH OUT (real payout?)
```

---

## Currencies
`credit` (Toman, store) · `xp` (→ levels) · `stars` (→ tiers) · `star_pieces`
(10 = 1 star) · `loyalty_points` (→ credit 1:1) · `traffic`/`days` (sub bonuses).

---

## FAUCETS — where value is created (live values + file)

### 💰 Credit
| Source | Payout | Cap | Where | Risk |
|---|---|---|---|---|
| **Level-ups** | **L2=5k, L5=50k, L10=300k, L20=3M per level; cumulative L1→20 ≈ 13.96M** | ❌ none | `core/level_config.py` | 🔴🔴🔴 |
| **Arcade play** | 100–4,000/play ×(1+streak≤0.25) → **≤5,000/day** | 1 play/day | `core/settings/web_game.py`, `repos/reward/_game.py` | 🔴🔴 ~150k/mo |
| **Achievements** | 500–50,000 one-time; total ≈ **122,500** | one-time each | seed `models/__init__.py:219+` | 🟡 |
| **Star tiers** | 15k–100k credit + **free 10/20/40/60/100GB plans** + VIP | per tier once | `database/tier_seeder.py` | 🔴 free plans |
| **Cashback** | 3–6% live (spec 7.7–12%) per 5 purchases | per 5 buys | `repos/reward/_points.py` | 🟢 tied to spend |
| **Referral** | **10% of referee's paid** + 10% GB + 10% days, per purchase | none | `reward_config` (10/10/10), `redeem_reward.py` | 🟢 revenue-funded |
| **Gifts** | user→user transfer | — | `repos/reward/_gifts.py` | 🟢 |

### 📈 XP (drives the level faucet above — so XP = credit by proxy)
Arcade 10–200/play · purchase 100 · achievement 200 · challenge 300 · referral 50 ·
streak 50/day · usage 25/GB. **19,000 XP total reaches L20.** Daily arcade alone
(~120–200 XP/day) hits L20 in **~100–160 days**. `core/level_config.py:XP_SOURCES`.

### ⭐ Stars
Arcade pieces (10 pieces=1 star, **cap 6/mo**) · achievements (1–3) · challenges ·
referral (1/sub, max 2). `_game.py`, `_achievements.py`, `redeem_reward.py`.
→ **Sink:** star tiers (3★=15% off … 50★=free 100GB+lifetime VIP+100k).

### ✨ Loyalty points
Arcade (credit//1000) · achievements · weekly challenges (100,150) · **level-ups
(50–30,000/level, total ≈ 139,600 to L20)** · gifts · job. → convert **1:1 to credit**.

---

## SINKS — where value leaves the system
| Sink | Converts | File | Note |
|---|---|---|---|
| **Cash-out** | credit → **pending payout (real money?)** | `repos/cashout.py` | 🔴 turns ALL credit into cash liability — must confirm what approval pays |
| Loyalty shop | loyalty → credit **1:1**, or → free plans/stars/VIP | `handlers/user/rewards/loyalty_shop.py` | 1:1 makes loyalty ≈ credit |
| Convert loyalty | loyalty → credit | `wallet/convert_loyalty.py` | same |
| Star tiers | stars → credit/plans/VIP | `tier_seeder.py` | free plans |
| Credit at checkout | credit → discount on purchase | purchase flow | 🟢 the *intended* sink |

---

## WORST-CASE: dedicated free-rider, 1 year, pays nothing, plays daily
| Source | Year-1 extraction |
|---|---|
| Arcade credit (~150k/mo) | ~1,800,000 |
| Level-ups (hits L20 in ~4–5 mo) | **~13,960,000** |
| Loyalty from levels (→credit 1:1) | ~139,600 |
| Achievements (one-time) | ~122,500 |
| Star tiers (≥50★ from 6★/mo) | free 100GB + **lifetime VIP** + ~330k+ credit |
| **TOTAL store-credit** | **≈ 16,000,000+ t** + lifetime VIP + free plans |

If cash-out pays real money, that's **~16M toman of real liability from one user who
never paid you** — vs your 1.5M/mo server. A dozen such users = bankruptcy.

## WORST-CASE: paying customer (healthy side)
A 100k/mo customer earns back: ~10% referral (only if they refer) + cashback
(~6–12% per 5 buys) + modest arcade. That part is **fine** — it's funded by their
spend. The problem is purely the **unpaid** farming paths above.

---

## Danger ranking & recommended fix order
1. 🔴🔴🔴 **Level-up credit (13.96M).** Single biggest hole. Either: make level
   rewards cosmetic (badge/title, no credit), OR cap credit/level hard (e.g. ≤5k),
   OR gate level rewards behind having paid. *(Spec says "don't touch level-up yet" —
   the ledger says this must change first.)*
2. 🔴🔴 **Cash-out.** Confirm what admin-approval actually pays. If real money →
   remove it or restrict to referral-earned credit only. Credit must stay store-only.
3. 🔴 **Arcade credit (~150k/mo).** Cut per-play credit hard (spec's 50–800 is saner
   than live 100–4,000) and add the monthly gameplay-credit cap (design doc decision §4).
4. 🔴 **Star-tier free plans + lifetime VIP.** Stars come 6/mo free from arcade →
   tiers hand out free plans/VIP. Either slow star earning, raise tier thresholds, or
   make high tiers discounts not free plans.
5. 🟡 **Loyalty 1:1 + convert + cashout** = loyalty is just cash. Re-rate loyalty
   (design doc leans 50:1) so it's a perk, not currency.
6. 🟢 Cashback & referral are fine (revenue-funded) — keep generous.

## What to confirm with Pasha
- Does cash-out pay **real money**, or is it just internal credit movement?
- Are levels currently **live** (granting that credit) or dormant?
- Appetite: max acceptable monthly give-away to a non-paying active user?
