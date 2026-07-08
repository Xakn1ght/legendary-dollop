# Earnings ("درآمد من") Card — Design

Date: 2026-07-08 · Status: approved (Pasha, "lets proceed and do them") · Lane: USER

## Purpose

Make referral earnings feel like real money. Users who clear the existing
cash-out gate (20 active referrals + 200k toman) get a visible mini-bank on
the Tasks/rewards page; users below the gate see exactly how far they are.
Completes the page's funnel: invite → earn → get paid.

## Decisions (settled in brainstorm)

- Gate unchanged: **20 active referrals AND ≥200,000 toman** to withdraw.
- Payouts stay **manual** (admin approves, transfers to card; deny → refund).
  The existing cash-out flow service is reused untouched.
- Lives **inside the Tasks/rewards page** as its own card between
  دعوت دوستان and the voucher/redeem card — Approach A (dedicated card).
- **Card number saved once** on the user, masked in UI, editable any time.
- **One credit pool** — no separate "earnings wallet"; withdrawable balance
  IS the existing credit balance.
- Economy seal intact: money still only enters via purchases; referral cuts
  remain the only minting path. This feature adds *visibility*, not money.

## UX

One card, two faces, RTL-first, one accent, calm surfaces (money moves here).

**Pre-gate face** (active referrals < 20):
- Title «درآمد من» + subtitle one-liner.
- Progress bar «۷ از ۲۰ دعوت فعال» (active referrals / 20).
- Earned-so-far number (total referral credit earned, toman).
- One explanatory line: reaching 20 makes earnings withdrawable.
- No withdraw button (nothing disabled/confusing — just the goal).

**Post-gate face** (active referrals ≥ 20):
- Withdrawable balance, big tabular digits (user credit, toman).
- «برداشت» primary button — enabled when credit ≥ 200k, otherwise disabled
  with «حداقل ۲۰۰ هزار تومان».
- Saved card row: masked ‎`•••• •••• •••• ۱۲۳۴` + edit (bottom sheet with a
  16-digit input, numeric keyboard, client+server validation).
- Last 3 payout requests with status chips: در انتظار / پرداخت شد / رد شد.
- Withdraw opens the existing cash-out request flow, prefilled with the
  saved card; the request amount is the full withdrawable balance unless the
  flow already supports amounts (reuse whatever the flow service does today).

Both faces render from ONE endpoint payload; no client-side gate math.

## Backend

- **Migration**: `users.payout_card` (String(20), nullable). Stored
  normalized (digits only, 16 chars). Full number appears in the admin
  payout-approval view exactly where admins already see card numbers today.
- **`GET /api/dashboard/earnings`** (webapp auth): returns
  `{ ok, active_referrals, gate: 20, earned_total_toman, credit_toman,
     min_cashout_toman: 200000, unlocked: bool, card_masked: str|null,
     recent_payouts: [{id, amount_toman, status, created_at}] (≤3) }`.
  Payout rows come from the existing cashout-request table; zero new tables.
- **`POST /api/dashboard/earnings/card`** (webapp auth): body
  `{ card: "16 digits" }`; server strips whitespace, validates `^\d{16}$`,
  saves, audit-logs (`record_audit`), returns masked value.
- **Withdraw** uses the existing dashboard cash-out endpoint/flow-service.
  If the current flow takes a card number per-request, prefill from
  `payout_card`; no changes to approve/deny/refund logic.
- Rate limit: earnings GET falls under default; card POST gets a modest
  per-IP limit via the existing rate-limiter table if trivial.

## Error handling

- Card validation errors → 400 `validation_error` (fa toast in UI).
- Withdraw below minimum is prevented client-side AND already enforced in
  the flow service (`FlowError`) — surface its code as a toast.
- Endpoint failures render the card in a quiet skeleton/hidden state; the
  Tasks page must not break if earnings can't load.

## Testing

- Unit-style script test (in-memory SQLite, like tests/test_cashout_service.py):
  gate math (19 vs 20 active), masked card, payload shape, card validation.
- Headless screenshot probe of both faces (mock the endpoint for the
  post-gate face on the test account).

## Out of scope

Auto-payouts, payout scheduling, changing gate numbers, multi-card support,
separating earnings from the credit pool.
