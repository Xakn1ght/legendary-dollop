# Testing

Two ways to test, plus the short list only a human can do.

## 1. The unit suite

No pytest. Every file is a standalone script; in-memory SQLite, no services
needed.

```bash
PYTHONPATH=src .venv/bin/python tests/test_pricing.py      # one file
for f in tests/test_*.py; do PYTHONPATH=src .venv/bin/python "$f" || echo "FAIL $f"; done
```

## 2. The phone simulator — `scripts/phone_sim.py`

Drives the REAL bot the way a thumb does. It builds the same Dispatcher
`main.py` builds (same routers, same middlewares), points it at the real
database, Redis and PasarGuard panel, and feeds it Telegram updates. Nothing
reaches Telegram: a no-network session records what the bot *would* have sent
and prints it as a transcript, so every screen and every button is visible.

```bash
PYTHONPATH=src .venv/bin/python scripts/phone_sim.py                    # every scenario
PYTHONPATH=src .venv/bin/python scripts/phone_sim.py purchase pro       # pick some
PYTHONPATH=src .venv/bin/python scripts/phone_sim.py start --cleanup    # remove QA data after
```

Scenarios: `start`, `purchase`, `freetest`, `pro`, `services`, `renew`,
`support`, `rewards`, `referral`.

It reports handler crashes, buttons that lead nowhere, and any tap slower than
2s. **`freetest` creates a real panel account** — `TEST_PANEL_PREFIX` must be
set (it is, `qa`), and `--cleanup` deletes the account and its rows, which also
restores free-trial eligibility so the next run repeats cleanly.

The QA customer is chat id `999000111`. `INVITE_CODE` at the top of the file is
a real customer's referral code, needed to get past the invite gate.

### What it caught

The 7-second freeze on opening a subscription (a lazily-booted render pool),
the free trial reading as "۰٫۲ گیگ" instead of 250 MB, and the support
assistant emitting emojis against the project rule.

## 3. Mini App rendering

The dashboard can be rendered headless at phone size against *genuine* signed
`initData` — the real auth path, not a bypass. The helper scripts live in the
session scratchpad; the recipe is:

1. sign initData for a user with `BOT_TOKEN` (see `utils/webapp_verify.py`;
   `verify_init_data` must accept your own string before you use it);
2. pass it URL-encoded as a single value in the hash:
   `#tgWebAppData=<encoded>&tgWebAppVersion=7.10&tgWebAppPlatform=ios`.
   Encode it whole — it contains `&`, and unencoded the page parses only the
   first field and the access guard blocks;
3. load `http://127.0.0.1:8585/webapp/dashboard?auth=<token>` with a
   390x844 viewport, then screenshot and collect console errors.

Check per page: HTTP status, console errors, failed requests, and
`scrollWidth - clientWidth` (must be 0 — the page must never scroll sideways).

Note the dashboard scrolls the **body**, not `.content`. A mouse drag does not
scroll a touch page; use a wheel event or a CDP touch swipe or you will
conclude the page is frozen when it is fine.

## 4. What still needs a real phone

Everything above proves behaviour, not feel. A human still has to check:

- how it actually looks in the Telegram client on a real handset;
- the keyboard: iOS zoom on focus, and whether the chat layout jumps when the
  keyboard opens;
- paying a real receipt end to end, including sending the photo;
- installing a delivered config in v2rayNG / Karing and confirming it connects;
- the first-run onboarding tour on a small screen.

## 5. Auto-renewal, with real traffic

```bash
PYTHONPATH=src .venv/bin/python scripts/test_renewal_burn.py
```

Creates a 20 MB account, books a renewal as the panel's native `next_plan`,
burns the traffic through an isolated xray on 127.0.0.1, and waits for the
panel to fire the booked plan by itself. 10/10 passing; the panel fires in
about ten seconds.
