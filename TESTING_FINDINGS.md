# Testing findings

Anything odd you spot during a test run goes here. **Write it down and keep
testing** — do not stop to fix it unless the step failed to produce the state
the next step needs.

Add a line, then triage after the run. Delete lines once fixed.

Format: `- [ ] where — what happened`

---

## Open

- [ ] Charge page — spacing needs a redesign. Cosmetic; goes with the
      delivery-banner redesign rather than on its own.

## Fixed / not a bug

Checked 2026-08-29. The list rescued from the old checklists was mostly stale —
five of six had already been fixed or turned out to be by design.

- [x] Support, new ticket — 400 "field required". Fixed: `subject` is optional
      now (`api/schemas/tickets.py`), and the form only sends category,
      message and subscription_id. Verified against the schema.
- [x] Support, live chat — WebSocket pointed at the arcade domain. Fixed: the
      URL is built from `window.location.host`, and the bot opens support with
      `DASHBOARD_PUBLIC_BASE_URL` (`handlers/user/common.py:141`), so it can
      only inherit the dashboard domain now.
- [x] Charge page — Cancel did nothing. Fixed: `cancelOrder` leaves the charge
      flow entirely instead of returning to the choose-a-subscription step.
- [x] Buy > custom plan — never asks for days. **By design**: custom plans are
      GB-only and 1-month (`flows/pricing.py`), so there is no days question to
      ask. The old expectation predates that rule.
- [x] Referrals — an existing user cannot enter a referral code. **By design**:
      referral attribution comes from signup only; the purchase flow
      deliberately never interrupts to ask for a code
      (`purchase/flow_referral_plan.py`), because existing users found it
      confusing.
