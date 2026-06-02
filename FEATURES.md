# AstroBytes — Features & Snapshot (2026-06-02)

Plain-English list of everything the app does right now, plus a short chart of the
rewards rework we just finished. Two Telegram bots (user + admin) and two web apps
(user dashboard + admin panel), all in one server.

---

## What the app does (features available now)

### VPN / buying a plan
- User picks a plan in the bot or the web app, sends a payment receipt photo.
- Admin approves, the VPN account is created (via Marzban), and the link is sent back.
- Plans: 20GB / 40GB / 60GB / 100GB at 35 days (90k / 180k / 250k / 400k Toman).
- Custom plan: pick your own GB (1–300) and days (15–90); price follows a set curve.

### Top-up (charge)
- Add more GB or days to an existing VPN account.
- Preset packages, admin approves, traffic/days added automatically.

### Referrals
- Everyone gets a referral code.
- When a friend you invited buys a plan, you pick ONE reward: 10% store credit,
  10% bonus GB, 10% bonus days, or season stars. You also always get +50 XP.

### Star Season + coupons (NEW)
- Stars now come ONLY from referrals, and reset every 90 days (a "season").
- Hitting star milestones (3, 5, 10, 15, 20, 25, 30, 40, 50) auto-unlocks coupons.
- Coupons live in your wallet (bot + web app), last 45 days, one per purchase, no stacking.
- Spendable at checkout now (both bot and web app):
  - % discount coupon (capped to a 100GB plan's price)
  - bonus-GB coupon (extra traffic added to the plan you buy)
- Bigger coupons (free plan, free renewal, VIP/Legend packs) are earned and shown,
  but not spendable yet — turned on later.

### Rewards that are status-only (no money)
- XP and Levels: leveling up gives titles/cosmetics, never money/GB/credit.
- Arcade game "AstroBugz": gives score, XP and leaderboard rank only — no money.
- Badges, themes, leaderboard rank.

### Cashback & VIP promoter (revenue-funded)
- Cashback to repeat buyers (revenue-funded, safe).
- Cash-out (real money) is locked to VIP promoters with 20+ active referrals only.

### Support / tickets
- Open a ticket (connection / money / other), chat with admin in real time.
- Text, photo, voice, document. Admin can invite you to a live chat.
- Admin can broadcast announcements.

### VIP membership
- Paid VIP (1M/3M/6M/1Y/lifetime): purchase discount + perks.

### Admin panel (web)
- User management, subscription/charge approval, tickets, broadcast, stats,
  financial analysis, reward settings, DB explorer, logs. Password + 2FA + IP allowlist.

### User dashboard (web)
- Your subscriptions, buy/charge, support, rewards (season + coupons), profile,
  referrals, wallet, VIP. Opens inside Telegram.

### Other
- Persian + English. Low-data / expiry / expired notifications. Loyalty shop exists
  but can no longer hand out credit or free plans (cosmetic/VIP items only).

---

## Short chart — what we did in the rewards rework

| Area | Before | After (now) |
|---|---|---|
| Pricing | old prices + a junk plan | 20/40/60/100 @ 35d; protective custom GB/days curve |
| Stars | earned from play, never reset | referral-only, seasonal (90-day reset) |
| Star prizes | old ladder paid out credit/free plans | season ladder unlocks coupons (45-day) |
| Coupons | didn't exist | earned, shown, and spendable at checkout (bot + web) |
| Play / levels / arcade | could mint money/credit | status & cosmetics only — zero money |
| Old tier ladder | live, farmable for ~16M/free user | retired (turned off, can't pay out) |
| Loyalty shop | traded points for credit/free plans | credit/free-plan items removed |
| Cash-out | loosely available | locked to VIP promoters (20+ active referrals) |

### Coupon checkout rules (what's enforced)
- One coupon per purchase, no stacking.
- % discount capped to a 100GB plan's price (can't over-discount a huge custom plan).
- Bonus-GB added at the moment the VPN account is created (works for both
  pay-by-credit and pay-by-receipt orders).
- Coupon is marked used when the order is placed, and given back if the order is
  cancelled or fails.

### Still to do later (on purpose)
- Big "whale" coupons (free plan / free renewal / VIP & Legend packs) — earned and
  shown, but not spendable yet.
- A redesign of what the arcade game rewards (currently score-only).

All of the above is LIVE in production and merged into `main`.
