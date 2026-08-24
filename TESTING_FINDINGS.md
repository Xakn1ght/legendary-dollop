# Testing findings

Anything odd you spot during a test run goes here. **Write it down and keep
testing** — do not stop to fix it unless the step failed to produce the state
the next step needs.

Add a line, then triage after the run. Delete lines once fixed.

Format: `- [ ] where — what happened`

---

## Open

Rescued from the old checklists (found during earlier runs, never triaged):

- [ ] Buy > custom plan — it only asks for GB, never asks for days. The old
      test expected a days question and rejection under 15 days.
- [ ] Charge page — pressing Cancel does nothing; stays on the same "choose a
      subscription" page.
- [ ] Charge page — spacing needs a redesign.
- [ ] Referrals — an existing ("og") user cannot enter a referral code.
- [ ] Support, new ticket — "field required" error even though every field is
      filled. `POST /api/dashboard/tickets` returns 400.
- [ ] Support, live chat — WebSocket fails to connect. It is pointed at
      `wss://game1.astrobytech.com/...` (the arcade domain) instead of
      `dash.astrobytech.com`. Likely the cause of the ticket failure above.

## Fixed

_(move lines here with the date once confirmed fixed)_
