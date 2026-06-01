# ASSTROO — Final Reward System Map & Build Plan (2026-05-31)

**Master reference.** Supersedes the reward portions of the 2026-05-30 design/plan
docs. Pricing carries over from `2026-05-30-rewards-pricing-design.md`. Built on
`asstroo_star_season_coupon_spec_v2.md` + the ledger
(`2026-05-30-reward-economy-ledger.md`). Reconciled with Pasha's decisions 2026-05-31.

Context: ~800 users. Infra ≈ **15€/mo** (NL 10€/8TB + DE 5€/20TB) + domain 10€/yr.
Fixed cost is tiny; the only real risks are (a) capacity (~28TB) and (b) free users
minting VPN value — both handled below.

---

## The spine: two reward worlds that never cross

```
        ┌──────────────────────────────┐        ┌──────────────────────────────┐
        │   💸 MONETARY WORLD          │        │   🎖️ STATUS WORLD            │
        │   (mints VPN value —          │        │   (costs ≈ 0 — engagement)    │
        │    funded by real revenue)    │        │                               │
        ├──────────────────────────────┤        ├──────────────────────────────┤
        │ • Referral rewards (choice)   │        │ • XP → Levels                 │
        │ • Stars → season coupons      │        │ • Badges / titles / themes    │
        │ • Cashback (per 5 buys)       │        │ • Leaderboard rank            │
        │ • Marketing-action coupons    │        │ • Arcade score (glory only)   │
        │ • VIP Promoter cashout (5%)   │        │                               │
        └──────────────────────────────┘        └──────────────────────────────┘
```

**Iron rule:** Pure play, daily check-in, and leveling give **status & cosmetics
only — never credit, GB, days, or cash.** Monetary value is minted *only* by actions
that bring real money (referrals, purchases) or real reach (marketing actions). This
is what makes the system un-farmable. (Decided 2026-05-31.)

---

## 1. Pricing (carried from 2026-05-30) + custom days (new 2026-06-01)
Plans: 20→90k · 40→180k · 60→250k · 100→400k, **35 days**. Delete junk plan.
Custom GB (aligned curve hitting all anchors): 5000/GB(1–10) → 4000(10–20) →
4500(20–40) → 3500(40–60) → 3750(60–100) → 4000(100+). Range 1–300GB.

**Custom days (Boom+ style). Decided 2026-06-01: protective 0.7 split, min 15 days.**
Two dials: GB (quota = the cost driver) and days (validity window = cheap to provide,
but affects rebuy frequency). 35 days is the anchor so base plans stay the sweet spot:
```python
DAYS_MIN, DAYS_MAX = 15, 90               # no sub-15-day plans (anti-farm)
def custom_price(gb, days):
    factor = 0.7 + 0.3 * (days / 35)      # 35d → ×1.0 ; protective split
    return round_price(custom_gb_price(gb) * factor)
```
Protective 0.7 base = short windows barely cheaper, pushing users toward ~35 days and
protecting rebuy revenue; longer windows still add absolute revenue.
Examples: 100GB/35d=400k · 100GB/15d≈331k · 100GB/90d≈589k · 50GB/60d≈261k.

**Anti-farm rule (required):** cashback ("every 5 purchases") and referral stars
("per purchase") must count by **spend / qualifying plan size, not raw purchase
count** — otherwise cheap short plans could be spammed to farm milestones. Combined
with the 15-day minimum, this closes the loophole.

## 2. Referral rewards — choose ONE per referred ≥20GB purchase
| Choice | Value |
|---|---|
| 10% of total paid | VPN credit |
| 10% of bought GB | bonus GB on a sub |
| 10% of bought days | bonus days |
| Stars | +1 (normal) / +2 (with reserved auto-renew); season stars |
+ **50 XP** to referrer regardless of choice. All revenue-funded. `referral_rewards`
table + existing redeem/notify path. **Locked (2026-06-01):** for non-VIP users the
credit choice is **store credit — usable for direct VPN purchases only, never cash.**
Real cash exists ONLY via the VIP Promoter path. VIP Promoters (20+ active refs) also
see a 5% **cashout** choice (see §6).

## 3. Star Season → coupon ladder (referral-only, 90-day, resets)
Stars come **only** from the referral star-choice. Seasonal; reset to 0 every 90
days; milestones auto-unlock coupons (45-day expiry, VPN-only, 1/purchase, no stack,
no cashout). Dedup `star_season:{season}:milestone:{n}:user:{id}`.

| ★ | Reward | ~Revenue to reach | Cost to us |
|---|---|---|---|
| 3 | 10% discount coupon | ~270k | discount on a sale |
| 5 | 20% discount coupon | ~450k | discount on a sale |
| 10 | 10GB free traffic | ~900k | ~1.5k bandwidth |
| 15 | 50% discount coupon | ~1.35M | discount on a sale |
| 20 | Free 20GB/35d plan | ~1.8M | ~3k bandwidth |
| 25 | Free 40GB/35d plan | ~2.25M | ~6k bandwidth |
| 30 | Free auto-renew (≤100GB, once) | ~2.7M | one renewal |
| 40 | VIP Pack (renew+30d support+badge+theme) | ~3.6M | mostly cosmetic |
| 50 | Legend Pack (renew+100GB+60d support+badge+theme) | ~4.5M | mostly cosmetic |
Optional: tiny 1★ "First Referral" badge for instant gratification. Top tiers
(40/50) are aspirational whale prizes — rarely paid, great for hype.

**Recommended pack contents (2026-06-01).** These reward users who brought ~3.6M /
4.5M in referral revenue, so real cost is tiny (one renewal + cosmetics):

*VIP Pack (40★):*
- 1 free auto-renewal, ≤100GB / 35d (headline tangible value, one-time)
- Permanent **VIP badge** + exclusive **VIP dashboard theme** (cosmetic, free)
- 30 days priority support
- "VIP" flair on the leaderboard
- One-time **+20GB bonus** on their next purchase

*Legend Pack (50★) — strictly better, max prestige:*
- 1 free auto-renewal, ≤100GB / 35d
- **+100GB bonus traffic** coupon
- Rare **Legend badge** + animated **Legend theme** (prestige cosmetic)
- 60 days priority support + top leaderboard flair
- **Custom username/color** unlock + early access to new servers/features
- (Recurring perks like a standing discount intentionally avoided — keep cost one-time)

## 4. Cashback (loyalty to payers)
After every 5 eligible purchases: GB-keyed rate {20:7.7%,40:9%,60:10%,100:12%} of
those 5, as VPN credit, rounded to 1,000. **Dedup required** (`cashback_processed`).
Custom GB → nearest band. Revenue-funded; safe.

## 5. XP / Level system (status & cosmetic only)
XP sources (each also grows the business where noted):
| Action | Telegram hook | Business benefit |
|---|---|---|
| Invite friend | deep-link `?start=ref_` | growth (also = stars) |
| Share to Story | `WebApp.shareToStory()` | free viral reach |
| Share app to chat | `savePreparedInlineMessage`+`shareMessage` | reach |
| Join announcement channel | bot `getChatMember` check | broadcast reach |
| Enable bot DMs | `WebApp.requestWriteAccess()` | can market to them |
| Add to home screen | `WebApp.addToHomeScreen()` | retention/DAU |
| Daily check-in | open app | DAU |
| Complete profile / custom username | — | engagement |
| Make a purchase | — | (XP only; money handled elsewhere) |

**Level reward = a cosmetic unlock + badge/title + leaderboard flair. No credit.**
Marketing actions (join channel, share to story, enable DMs) additionally grant a
**small one-time discount coupon** — they bring real reach and are naturally capped
(you can only join once). Reuse XP infra but **neuter the old `LEVEL_REWARDS` credit**
(see §8). Cosmetics unlock directly at levels — no coin economy needed yet.

## 6. VIP Promoter Cashout (gated real money)
20+ active referrals (referred bought ≥20GB) + account ≥30d + no abuse + manual
approval. 5% of eligible referral revenue → pending → monthly admin-approved payout.
Min 100k, max 1M/mo, 7-day hold, ignore refunded/cancelled/self. Stars/coupons NEVER
convert to cash. New tables: `vip_cashout_transactions`, pending-balance.
⚠️ Reconcile with existing `repos/cashout.py` — restrict it to this gated path only.

## 7. Deferred (explicitly NOT now)
- **Coins + mini-shop** (digital cosmetics for coins) — design later; the level
  system unlocks cosmetics directly for now, so coins can layer in without redesign.
- **Real-money resale** (Spotify, gift cards) — separate margin business, later.
- Deep challenge-architecture rebuild; star-economy beyond this map.

## 8. 🔴 Safety fixes that MUST land (from the ledger)
1. **Neuter `LEVEL_REWARDS` credit** (`core/level_config.py`): replace the
   5k→3M-per-level credit with cosmetic/badge unlocks. (Old cumulative ≈ 13.96M — the
   #1 hole.) Levels keep XP thresholds; rewards become status.
2. **Cut arcade credit** (`core/settings/web_game.py`): arcade gives **XP + score/
   leaderboard only — no credit**. (Was 100–4,000/play.)
   - 🔖 **Open tab (Pasha, 2026-06-01):** keep the game able to *pay* later. Two
     lanes: **digital/cosmetic** payouts (coins → themes/badges) are iron-rule-safe —
     do anytime (Phase E). **Real** payouts (credit/GB) would break the iron rule and
     reopen farming — only with a hard monthly cap + anti-farm design, decided later.
3. **Lock cash-out** (`repos/cashout.py`) to the §6 VIP-promoter path only.
4. **Re-rate / retire loyalty 1:1** — with coins deferred and play giving no money,
   loyalty_points lose their role; stop minting them from play, or convert remaining
   to the new model. Confirm during build.
5. Star tiers (`tier_seeder.py`) → replaced by the §3 season ladder; migrate/retire.

### Worst-case after fixes
A non-paying daily player earns: XP, levels, badges, a leaderboard rank — **0 toman,
0 GB, 0 cash.** A top referrer earns coupons/credit/cashout — all funded by the
revenue they brought. ✅ Un-farmable.

---

## Build plan (phased)

**Phase A — Pricing & safety (do first, low risk, closes the holes)**
1. Plans → new prices/35d, delete junk plan.
2. Aligned `custom_gb_price()`.
3. Neuter level credit → cosmetic unlocks; cut arcade to XP-only; lock cashout to §6.
4. Tests for prices + "play mints no money".

**Phase B — Referrals & Star Season (the core give-back)**
5. Referral choice model (10% paid/GB/days or stars) + 50 XP.
6. `star_seasons`, `user_star_progress`, `star_milestone_claims`, `reward_coupons`.
7. Milestone auto-unlock + dedup; 90-day season reset job.
8. Coupon wallet UI + checkout coupon application (1/purchase, no stack, 45d expiry).

**Phase C — Cashback & Marketing/XP**
9. Cashback rebalance + dedup.
10. XP sources incl. Telegram hooks (share-to-story, channel check, requestWriteAccess,
    addToHomeScreen, daily check-in); level cosmetic unlocks; marketing-action coupons.

**Phase D — VIP Promoter Cashout**
11. Eligibility + `vip_cashout_transactions` + admin approval + monthly window + fraud holds.

**Phase E — Deferred (later)** Coins, mini-shop, real-money resale.

## Open items to confirm in-flight
- Does existing `repos/cashout.py` pay real money today? Restrict to §6 before launch.
- Loyalty_points fate (retire vs migrate) once play gives no money.
- Achievements: align the new-9 set to status/cosmetic + cashback flags (no big credit).
