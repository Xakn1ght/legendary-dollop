"""Offline acceptance tests for the SMS auto-approve GLUE (bakbot-parity sweep).

Covers the five live bakbot incidents ported 2026-07-14:
  1. split payment       -> veto-only fields defer a foreign same-amount deposit;
                            the true owner's later order wins via card
  2. garbage screenshot  -> unreadable orders NEVER amount-approve (any sweep),
                            one admin DM per deposit+order pair
  3. card agreement      -> receipt card == SMS source card approves INSTANTLY
                            even with disjoint refs
  4. multi-deposit       -> several same-amount deposits: evidence picks the
                            owner (never pool order); no evidence = defer all
  5. failed AI read      -> no read-marker stamp, global backoff, later retry

All Telegram/DB/AI I/O is monkeypatched; deposits live in a temp file.

Run: PYTHONPATH=src python tests/test_sms_glue.py
"""
import asyncio
import copy
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from app.services import sms_ai, sms_autoapprove, sms_ingest  # noqa: E402

TMP = tempfile.mkdtemp(prefix="smsglue-")
APPROVALS: list = []
NOTICES: list = []
AI_CALLS: list = []
CANDS_BASE: list = []
AI_RESULTS: dict = {}  # image path -> fields dict | None


def _sms(amount_rial, card, tracking, retrieval=None):
    ret = f" با شماره بازیابی {retrieval}" if retrieval else ""
    return (f"مبلغ:+{amount_rial:,}\nمانده:1,000\n"
            f"بابت :انتقال از کارت 621986190872{card} به کارت 6221061103953057"
            f"{ret} با شماره پیگیری {tracking}")


def _img(name):
    path = os.path.join(TMP, name)
    with open(path, "wb") as f:
        f.write(b"png-bytes")
    return path


class _FakeSessionCtx:
    async def __aenter__(self):
        return None

    async def __aexit__(self, *a):
        return False


async def _fake_candidates(_session):
    return sms_ingest._apply_ai_cache(copy.deepcopy(CANDS_BASE))


async def _fake_approve(_bot, _session, typed_id, dep):
    APPROVALS.append((typed_id, dep["dedup_id"]))
    return True


async def _fake_notify(_bot, text):
    NOTICES.append(text)


async def _fake_extract(blob, mime="image/jpeg"):
    AI_CALLS.append(mime)
    # keyed by current single unread image content marker — the tests set
    # AI_RESULTS['next'] before each sweep that should trigger a read
    return AI_RESULTS.get("next")


async def _fake_hint(*a, **kw):
    return None


def _reset(deposits=(), cands=(), grace=600):
    APPROVALS.clear()
    NOTICES.clear()
    AI_CALLS.clear()
    CANDS_BASE[:] = list(cands)
    sms_ingest._ai_read_cache.clear()
    sms_ingest._ai_fail_until = 0.0
    sms_ingest.SMS_VETO_GRACE_SEC = grace
    with open(sms_ingest._DEPOSITS_FILE, "w", encoding="utf-8") as f:
        import json
        json.dump(list(deposits), f, ensure_ascii=False)


def _deposits():
    return sms_ingest._load_deposits()


def _dep(text, ts=None):
    d = sms_autoapprove.parse_bank_sms(text)
    assert d, f"fixture SMS failed to parse: {text[:40]}"
    d["ts"] = int(ts if ts is not None else time.time())
    d["matched"] = None
    return d


async def _sweep():
    await sms_ingest._sweep(bot=None)


def setup_module():
    sms_ingest._DEPOSITS_FILE = os.path.join(TMP, "deposits.json")
    sms_ingest._STATE_FILE = os.path.join(TMP, "state.json")
    sms_ingest.sms_enabled = lambda: True
    sms_ingest.AsyncSessionLocal = _FakeSessionCtx
    sms_ingest._candidates = _fake_candidates
    sms_ingest._approve = _fake_approve
    sms_ingest._notify_admin = _fake_notify
    sms_ai.ai_available = lambda: True
    sms_ai.extract_receipt_fields = _fake_extract
    sms_ai.match_hint = _fake_hint


NOW = int(time.time())


def test_unreadable_gate():
    """Acceptance 1 (item 2): settings screenshot + same-amount deposit ->
    NO approval, ONE admin DM, deposit stays available — every sweep."""
    cand = {"order_id": "sub:1", "amount": 85000, "receipt_ts": NOW, "image": _img("garbage.png")}
    _reset(deposits=[_dep(_sms(850_000, "3264", "248125"))], cands=[cand])
    AI_RESULTS["next"] = {"success": False, "amount": None, "amount_unit": None,
                          "source_card_last4": None, "dest_card_last4": None,
                          "ref_numbers": [], "time_text": None}
    asyncio.run(_sweep())
    assert APPROVALS == [], APPROVALS
    assert len([n for n in NOTICES if "قابل" in n or "سفارش" in n]) == 1, NOTICES
    assert _deposits()[0].get("matched") is None
    assert sms_ingest._ai_read_cache["sub:1"] == {"receipt_unreadable": True}

    # Second + third sweep (even with the veto grace at zero = "deferred-retry
    # sweep"): still blocked, still exactly one DM for the pair.
    sms_ingest.SMS_VETO_GRACE_SEC = 0
    asyncio.run(_sweep())
    asyncio.run(_sweep())
    assert APPROVALS == [], APPROVALS
    assert len(NOTICES) == 1, NOTICES
    assert _deposits()[0].get("matched") is None


def test_card_agreement_instant():
    """Acceptance 3 (item 3): receipt card == SMS source card, refs disjoint
    -> INSTANT approve (no deferral)."""
    cand = {"order_id": "sub:2", "amount": 85000, "receipt_ts": NOW, "image": None}
    _reset(deposits=[_dep(_sms(850_000, "3264", "111", retrieval="222"))], cands=[cand])
    sms_ingest._ai_read_cache["sub:2"] = {"receipt_last4": "3264", "refs": ["999888"]}
    asyncio.run(_sweep())
    assert APPROVALS == [("sub:2", "111")], APPROVALS
    # And the contradiction helper itself agrees (defense in depth).
    dep = _dep(_sms(850_000, "3264", "111", retrieval="222"))
    cand_view = {"refs": ["999888"], "receipt_last4": "3264"}
    assert sms_ingest._evidence_contradiction(dep, cand_view) is None


def test_split_payment_veto_then_true_owner():
    """Acceptance 2 (item 1): amount-mismatched receipt keeps veto-only fields;
    a foreign same-amount deposit defers; the payer's own later order wins by
    card instantly."""
    victim = {"order_id": "sub:3", "amount": 85000, "receipt_ts": NOW, "image": None}
    _reset(deposits=[_dep(_sms(850_000, "2222", "333"))], cands=[victim])
    # Veto-only evidence from the mismatched (80k of 85k) receipt: payer 1111.
    sms_ingest._ai_read_cache["sub:3"] = {
        "receipt_mismatch_card_last4": "1111", "receipt_mismatch_refs": ["555"]}
    asyncio.run(_sweep())
    assert APPROVALS == [], APPROVALS
    d = _deposits()[0]
    assert d.get("veto_since") and d.get("veto_order") == "sub:3", d
    # Veto-only card must never positively join: even a deposit whose card
    # EQUALS the veto card is not an instant approve (it defers via rule
    # order — no trusted evidence at all -> no contradiction -> approve is
    # allowed only for the amount-only path; the veto card equal is neutral).
    assert sms_ingest._evidence_contradiction(
        {"source_last4": "1111"}, {"veto_card_last4": "1111"}) is None

    # The true owner's order appears (trusted card = the deposit's payer).
    owner = {"order_id": "sub:4", "amount": 85000, "receipt_ts": NOW, "image": None}
    CANDS_BASE.append(owner)
    sms_ingest._ai_read_cache["sub:4"] = {"receipt_last4": "2222", "refs": []}
    asyncio.run(_sweep())
    assert APPROVALS == [("sub:4", "333")], APPROVALS
    assert _deposits()[0].get("matched") == "sub:4"


def test_multi_deposit_card_picks_owner():
    """Acceptance 4 (item 4): two pooled same-amount deposits; the new order's
    receipt card matches the SECOND -> second wins, first stays available."""
    d_first = _dep(_sms(850_000, "5555", "701"), ts=NOW - 600)   # pooled earlier
    d_second = _dep(_sms(850_000, "6666", "702"), ts=NOW - 60)
    cand = {"order_id": "sub:5", "amount": 85000, "receipt_ts": NOW, "image": None}
    _reset(deposits=[d_first, d_second], cands=[cand])
    sms_ingest._ai_read_cache["sub:5"] = {"receipt_last4": "6666", "refs": []}
    asyncio.run(_sweep())
    assert APPROVALS == [("sub:5", "702")], APPROVALS
    deps = {d["dedup_id"]: d for d in _deposits()}
    assert deps["702"].get("matched") == "sub:5"
    assert deps["701"].get("matched") is None, "first deposit must stay for its own order"


def test_multi_deposit_no_evidence_defers_all():
    """Item 4 tail: several amount-only candidates, no decisive evidence ->
    ALL deferred; after the grace the sweep resolves (first wins)."""
    d1 = _dep(_sms(850_000, "7777", "801"), ts=NOW - 300)
    d2 = _dep(_sms(850_000, "8888", "802"), ts=NOW - 200)
    cand = {"order_id": "sub:6", "amount": 85000, "receipt_ts": NOW, "image": None}
    _reset(deposits=[d1, d2], cands=[cand], grace=600)
    # Trusted read: amount agreed but no card/refs extracted -> no evidence.
    sms_ingest._ai_read_cache["sub:6"] = {"receipt_last4": None, "refs": []}
    asyncio.run(_sweep())
    assert APPROVALS == [], APPROVALS
    deps = {d["dedup_id"]: d for d in _deposits()}
    assert deps["801"].get("veto_since") and deps["802"].get("veto_since"), deps
    # Grace expiry -> the sweep may resolve it (no better owner appeared).
    sms_ingest.SMS_VETO_GRACE_SEC = 0
    asyncio.run(_sweep())
    assert APPROVALS == [("sub:6", "801")], APPROVALS
    deps = {d["dedup_id"]: d for d in _deposits()}
    assert deps["802"].get("matched") is None


def test_failed_ai_read_backoff():
    """Acceptance 5 (item 5): AI 429 -> order NOT marked read; reads are
    skipped during the backoff and retried after it."""
    cand = {"order_id": "sub:7", "amount": 85000, "receipt_ts": NOW, "image": _img("ok.png")}
    _reset(deposits=[_dep(_sms(850_000, "3264", "901"))], cands=[cand])
    AI_RESULTS["next"] = None  # quota 429 / network failure
    asyncio.run(_sweep())
    # Parity with bakbot: the deterministic amount-only approve still proceeds,
    # but the order is NOT stamped as read and the backoff is armed.
    assert "sub:7" not in sms_ingest._ai_read_cache, sms_ingest._ai_read_cache
    assert sms_ingest._ai_fail_until > time.time(), "fail backoff must be armed"
    assert len(AI_CALLS) == 1

    # During the backoff: a new order's read is skipped entirely.
    cand2 = {"order_id": "sub:8", "amount": 17000, "receipt_ts": NOW, "image": _img("ok2.png")}
    CANDS_BASE[:] = [cand2]
    with open(sms_ingest._DEPOSITS_FILE, "w", encoding="utf-8") as f:
        import json
        json.dump([_dep(_sms(170_000, "1234", "902"))], f, ensure_ascii=False)
    asyncio.run(_sweep())
    assert len(AI_CALLS) == 1, "read must be skipped during the backoff"

    # Backoff over -> the read is retried and (succeeding now) stamps evidence.
    sms_ingest._ai_fail_until = 0.0
    AI_RESULTS["next"] = {"success": True, "amount": 17000, "amount_unit": "toman",
                          "source_card_last4": "1234", "dest_card_last4": None,
                          "ref_numbers": ["77"], "time_text": None}
    with open(sms_ingest._DEPOSITS_FILE, "w", encoding="utf-8") as f:
        import json
        json.dump([_dep(_sms(170_000, "1234", "903"))], f, ensure_ascii=False)
    APPROVALS.clear()
    asyncio.run(_sweep())
    assert len(AI_CALLS) == 2, "read must be retried after the backoff"
    assert sms_ingest._ai_read_cache.get("sub:8") == {"receipt_last4": "1234", "refs": ["77"]}
    assert APPROVALS == [("sub:8", "903")], APPROVALS


def test_ref_join_stays_instant():
    """Ref joins are never gated, deferred or vetoed."""
    cand = {"order_id": "sub:9", "amount": 85000, "receipt_ts": NOW, "image": None}
    _reset(deposits=[_dep(_sms(850_000, "0000", "555", retrieval="178324819389"))], cands=[cand])
    sms_ingest._ai_read_cache["sub:9"] = {"receipt_last4": "9999", "refs": ["178324819389"]}
    asyncio.run(_sweep())
    # Card DIFFERS (0000 vs 9999) but the ref join is definitive.
    assert APPROVALS == [("sub:9", "555")], APPROVALS


def test_bin_prefix_card_read_dropped_no_false_veto():
    """Acceptance 6 (item 8, NEW 2026-07-18): the AI reader returns the BANK
    PREFIX (6104) as 'last-4' on an RTL receipt. The guard drops the card at
    the cache choke point: no bogus contradiction, the legit amount-only
    match approves instantly instead of sitting out a 10-minute veto."""
    cand = {"order_id": "sub:10", "amount": 85000, "receipt_ts": NOW, "image": _img("rtl.png")}
    _reset(deposits=[_dep(_sms(850_000, "3264", "601"))], cands=[cand])
    AI_RESULTS["next"] = {"success": True, "amount": 850_000, "amount_unit": "rial",
                          "source_card_last4": "6104",  # Mellat BIN — a misread
                          "dest_card_last4": None, "ref_numbers": [], "time_text": None}
    asyncio.run(_sweep())
    assert APPROVALS == [("sub:10", "601")], APPROVALS
    assert NOTICES == [], NOTICES
    d = _deposits()[0]
    assert d.get("matched") == "sub:10" and not d.get("veto_since"), d
    # The bogus card must not survive as trusted OR veto evidence.
    assert sms_ingest._ai_read_cache["sub:10"] == {"receipt_last4": None, "refs": []}


def test_bin_prefix_never_survives_as_veto_evidence():
    """Item 8 tail: on an amount-MISMATCHED receipt the misread BIN card is
    dropped from the veto-only fields too (refs stay), so it can never block
    a foreign pairing on fabricated card evidence."""
    cand = {"order_id": "sub:11", "amount": 85000, "receipt_ts": NOW, "image": _img("rtl2.png")}
    _reset(deposits=[_dep(_sms(850_000, "3264", "602"))], cands=[cand])
    AI_RESULTS["next"] = {"success": True, "amount": 800_000, "amount_unit": "rial",  # 80k != 85k
                          "source_card_last4": "6037",  # BIN misread
                          "dest_card_last4": None, "ref_numbers": ["444555"], "time_text": None}
    asyncio.run(_sweep())
    assert sms_ingest._ai_read_cache["sub:11"] == {
        "receipt_mismatch_card_last4": None, "receipt_mismatch_refs": ["444555"]}, \
        sms_ingest._ai_read_cache
    # Deposit refs (602) vs veto refs (444555): still a ref contradiction ->
    # deferred — the guard removes only the fabricated CARD evidence.
    assert APPROVALS == [], APPROVALS
    assert _deposits()[0].get("veto_since"), _deposits()[0]


def test_reused_tracking_pools_second_real_payment():
    """Bank tracking numbers repeat. A same-tracking SMS with a DIFFERENT
    amount is a second real payment: it must be pooled (not dropped as a
    replay), must not amount-approve, and must not consume the first one."""
    first = _dep(_sms(850_000, "3264", "248125"))
    _reset(deposits=[dict(first, claim_id=first["dedup_id"])],
           cands=[{"order_id": "sub:1", "amount": 85000, "receipt_ts": NOW},
                  {"order_id": "sub:2", "amount": 120000, "receipt_ts": NOW}])
    sms_ingest.sms_autoapprove = sms_autoapprove

    asyncio.run(sms_ingest.handle_incoming_sms(None, _sms(1_200_000, "3264", "248125")))
    deps = _deposits()
    assert len(deps) == 2, [d.get("amount") for d in deps]

    second = deps[1]
    assert second.get("tracking_collision") == 1, second
    assert second["dedup_id"] == first["dedup_id"]
    assert second["claim_id"].startswith("sms2:"), second["claim_id"]
    assert second["claim_id"] != deps[0]["claim_id"]

    # amount-only uniqueness is NOT enough for a reused tracking number
    # (the untouched first deposit approving sub:1 is normal and expected)
    assert "sub:2" not in [a[0] for a in APPROVALS], APPROVALS
    assert any("پیگیری تکراری" in n for n in NOTICES), NOTICES
    assert second.get("matched") is None

    # an exact replay of either one is still dropped
    asyncio.run(sms_ingest.handle_incoming_sms(None, _sms(1_200_000, "3264", "248125")))
    assert len(_deposits()) == 2


def test_reused_tracking_approves_on_card_evidence():
    """The same collided deposit DOES approve once the receipt proves the
    payer — and marking it matched leaves its same-tracking twin alone."""
    first = _dep(_sms(850_000, "3264", "248125"))
    second = _dep(_sms(1_200_000, "3264", "248125"))
    second["tracking_collision"] = 1
    second["claim_id"] = sms_autoapprove.deposit_fingerprint(second)
    _reset(deposits=[dict(first, claim_id=first["dedup_id"]), second],
           cands=[{"order_id": "sub:2", "amount": 120000, "receipt_ts": NOW, "image": None}])
    sms_ingest._ai_read_cache["sub:2"] = {"receipt_last4": "3264"}
    asyncio.run(_sweep())
    assert [a[0] for a in APPROVALS] == ["sub:2"], APPROVALS

    deps = _deposits()
    assert deps[1].get("matched") == "sub:2"
    assert deps[0].get("matched") is None, "approving one consumed its twin"


if __name__ == "__main__":
    setup_module()
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("PASS", fn.__name__)
    print(f"\nAll {len(fns)} SMS-glue acceptance tests passed.")
