"""SMS auto-approve safety tests: evidence veto + unreadable-receipt gate.

Ports of two live bakbot incidents (2026-07-11):
  #2277 — deposit theft via discarded evidence: a split-payment receipt
  amount-mismatched its order, the AI reader threw ALL fields away, and a
  different customer's same-amount deposit stole the order. Fix: mismatched
  fields survive as veto-only evidence; contradicted amount-only pairings
  defer for a grace period (then approve if no better owner appeared).
  #2292 — garbage receipt auto-approved: a non-receipt screenshot's order
  amount-matched a pooled deposit and approved without the receipt ever being
  AI-read. Fix: amount-only winners are AI-read before approval, and an order
  whose read says "not a successful transfer" NEVER auto-approves (admin is
  told once per deposit+order pair; the deposit stays available).

Run: PYTHONPATH=src python tests/test_sms_veto.py
"""
import asyncio
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from app.services import sms_ingest  # noqa: E402

GRACE = sms_ingest.SMS_VETO_GRACE_SEC


def _dep(**kw):
    d = {
        "amount": 850_000, "amount_unit": "rial",  # 85,000 toman
        "source_last4": "3621", "dest_last4": "3057", "dest_card": None,
        "tracking": "432247", "retrieval": None,
        "dedup_id": "432247", "raw": "sms", "ts": 1_000, "matched": None,
    }
    d.update(kw)
    return d


def _cand(oid, **kw):
    c = {"order_id": oid, "amount": 85_000, "receipt_ts": 1_000, "image": None,
         "receipt_last4": None, "refs": [], "veto_card_last4": None, "veto_refs": [],
         "receipt_unreadable": False}
    c.update(kw)
    return c


# ── unit: contradiction rules (spec rule 4) ──────────────────────────────────

def test_contradiction_rules():
    dep = _dep()

    # no evidence at all -> no contradiction
    assert sms_ingest._evidence_contradiction(dep, _cand("sub:1")) is None

    # (a) refs agree -> ref join -> NEVER a contradiction, even with a
    # contradicting card next to it
    assert sms_ingest._evidence_contradiction(
        dep, _cand("sub:1", refs=["432247"], receipt_last4="2269")) is None

    # (b) both have refs, none agree -> contradiction
    assert sms_ingest._evidence_contradiction(dep, _cand("sub:1", refs=["111"])) is not None

    # (c) payer card != receipt card — trusted read
    assert sms_ingest._evidence_contradiction(dep, _cand("sub:1", receipt_last4="2269")) is not None
    # (c) payer card != receipt card — veto-only read (the #2277 case)
    assert sms_ingest._evidence_contradiction(dep, _cand("sub:1", veto_card_last4="2269")) is not None
    # matching card -> fine
    assert sms_ingest._evidence_contradiction(dep, _cand("sub:1", receipt_last4="3621")) is None

    # (d) veto-only refs disagree -> contradiction; agree -> not one
    assert sms_ingest._evidence_contradiction(dep, _cand("sub:1", veto_refs=["999"])) is not None
    assert sms_ingest._evidence_contradiction(dep, _cand("sub:1", veto_refs=["432247"])) is None

    # deposit without a payer card can't card-contradict
    dep_nocard = _dep(source_last4=None)
    assert sms_ingest._evidence_contradiction(dep_nocard, _cand("sub:1", veto_card_last4="2269")) is None

    # SMS without refs can't ref-contradict
    dep_norefs = _dep(tracking=None, retrieval=None, dedup_id="h1")
    assert sms_ingest._evidence_contradiction(dep_norefs, _cand("sub:1", veto_refs=["999"])) is None

    print("PASS test_contradiction_rules")


def test_join_and_evidence_helpers():
    dep = _dep()
    assert sms_ingest._ref_joined(dep, _cand("sub:1", refs=["432247"]))
    assert not sms_ingest._ref_joined(dep, _cand("sub:1", refs=["111"]))
    # veto-only refs are NEVER a positive join
    assert not sms_ingest._ref_joined(dep, _cand("sub:1", veto_refs=["432247"]))

    assert sms_ingest._card_joined(dep, _cand("sub:1", receipt_last4="3621"))
    assert not sms_ingest._card_joined(dep, _cand("sub:1", receipt_last4="2269"))
    # veto-only card is block-only — never a card join
    assert not sms_ingest._card_joined(dep, _cand("sub:1", veto_card_last4="3621"))
    assert not sms_ingest._card_joined(_dep(source_last4=None), _cand("sub:1", receipt_last4="3621"))

    assert not sms_ingest._has_receipt_evidence(_cand("sub:1"))
    for kw in (dict(refs=["1"]), dict(receipt_last4="1234"),
               dict(veto_refs=["1"]), dict(veto_card_last4="1234"),
               dict(receipt_unreadable=True)):
        assert sms_ingest._has_receipt_evidence(_cand("sub:1", **kw)), kw
    print("PASS test_join_and_evidence_helpers")


# ── unit: the real _ai_enrich classification (spec rules 1 + 2) ─────────────

def test_ai_enrich_classification():
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        f.write(b"fake-image-bytes")
        img = f.name

    outcomes = {}

    async def run(oid, ai_result, amount=85_000):
        async def fake_extract(blob, mime="image/jpeg"):
            return ai_result

        orig_extract = sms_ingest.sms_ai.extract_receipt_fields
        orig_avail = sms_ingest.sms_ai.ai_available
        sms_ingest.sms_ai.extract_receipt_fields = fake_extract
        sms_ingest.sms_ai.ai_available = lambda: True
        try:
            learned = await sms_ingest._ai_enrich([_cand(oid, image=img, amount=amount)])
        finally:
            sms_ingest.sms_ai.extract_receipt_fields = orig_extract
            sms_ingest.sms_ai.ai_available = orig_avail
        outcomes[oid] = (learned, sms_ingest._ai_read_cache.get(oid))

    sms_ingest._ai_read_cache.clear()
    sms_ingest._ai_fail_until = 0.0
    try:
        # AI call FAILED -> NOTHING cached (the read marker is only stamped by
        # a completed read) and the global fail backoff is armed, so the order
        # can gain evidence on a later retry (bakbot #2406, item-5 parity —
        # this test previously asserted the old poison-stamp behavior).
        asyncio.run(run("sub:fail", None))
        assert outcomes["sub:fail"] == (False, None), outcomes["sub:fail"]
        assert "sub:fail" not in sms_ingest._ai_read_cache
        import time as _time
        assert sms_ingest._ai_fail_until > _time.time(), "fail backoff must be armed"
        sms_ingest._ai_fail_until = 0.0  # clear the backoff for the cases below

        # model says NOT a successful transfer -> unreadable
        asyncio.run(run("sub:garbage", {"success": False, "amount": None, "amount_unit": None,
                                        "source_card_last4": None, "dest_card_last4": None,
                                        "ref_numbers": [], "time_text": None}))
        assert outcomes["sub:garbage"] == (True, {"receipt_unreadable": True})

        # success but nothing extractable -> unreadable
        asyncio.run(run("sub:empty", {"success": True, "amount": None, "amount_unit": None,
                                      "source_card_last4": None, "dest_card_last4": None,
                                      "ref_numbers": [], "time_text": None}))
        assert outcomes["sub:empty"] == (True, {"receipt_unreadable": True})

        # readable amount that mismatches the order -> veto-only fields
        asyncio.run(run("sub:split", {"success": True, "amount": 800_000, "amount_unit": "rial",
                                      "source_card_last4": "2269", "dest_card_last4": "3057",
                                      "ref_numbers": ["888888"], "time_text": None}))
        assert outcomes["sub:split"] == (True, {"receipt_mismatch_card_last4": "2269",
                                                "receipt_mismatch_refs": ["888888"]})

        # clean read matching the order amount -> trusted fields
        asyncio.run(run("sub:clean", {"success": True, "amount": 850_000, "amount_unit": "rial",
                                      "source_card_last4": "3621", "dest_card_last4": "3057",
                                      "ref_numbers": ["432247"], "time_text": None}))
        assert outcomes["sub:clean"] == (True, {"receipt_last4": "3621", "refs": ["432247"]})
    finally:
        sms_ingest._ai_read_cache.clear()
        os.unlink(img)
    print("PASS test_ai_enrich_classification")


# ── harness: run _sweep with everything impure patched ──────────────────────

class _Harness:
    def __init__(self, deposits, candidates, ai_reads=None):
        self.deposits = deposits          # in-memory pool
        self.candidates = candidates      # list of dicts; cache overlays applied
        self.ai_reads = ai_reads or {}    # order_id -> cache entry on enrich (None = AI failed)
        self.approved = []
        self.notified = []
        self.enriched = []

    def install(self):
        self._orig = {}
        m = sms_ingest

        def keep(name, val):
            self._orig[name] = getattr(m, name)
            setattr(m, name, val)

        keep("_load_deposits", lambda: [dict(d) for d in self.deposits])

        def _save(deps):
            self.deposits[:] = [dict(d) for d in deps]
        keep("_save_deposits", _save)
        keep("_prune", lambda deps: deps)
        keep("sms_enabled", lambda: True)

        async def _cands(session):
            out = []
            for c in self.candidates:
                c = dict(c)
                cached = m._ai_read_cache.get(c["order_id"]) or {}
                c["receipt_last4"] = cached.get("receipt_last4")
                c["refs"] = cached.get("refs") or []
                c["veto_card_last4"] = cached.get("receipt_mismatch_card_last4")
                c["veto_refs"] = cached.get("receipt_mismatch_refs") or []
                c["receipt_unreadable"] = bool(cached.get("receipt_unreadable"))
                out.append(c)
            return out
        keep("_candidates", _cands)

        async def _enrich(cands):
            learned = False
            for c in cands:
                oid = c["order_id"]
                if oid in m._ai_read_cache or not c.get("image"):
                    continue
                # Mirror the real _ai_enrich: a missing ai_reads key models the
                # missing-file degrade ({} stamped); an EXPLICIT None models a
                # FAILED AI read, which stamps nothing (item 5 — the order must
                # stay readable on a later retry).
                entry = self.ai_reads.get(oid, {})
                self.enriched.append(oid)
                if entry is None:
                    continue
                m._ai_read_cache[oid] = entry
                learned = learned or bool(entry)
            return learned
        keep("_ai_enrich", _enrich)

        async def _approve(bot, session, typed_id, dep):
            self.approved.append(typed_id)
            return True
        keep("_approve", _approve)

        async def _notify(bot, text):
            self.notified.append(text)
        keep("_notify_admin", _notify)

        class _S:
            async def __aenter__(self):
                return None

            async def __aexit__(self, *a):
                return False
        keep("AsyncSessionLocal", lambda: _S())

        self._ai_avail = sms_ingest.sms_ai.ai_available
        sms_ingest.sms_ai.ai_available = lambda: True
        m._ai_read_cache.clear()

    def uninstall(self):
        for k, v in self._orig.items():
            setattr(sms_ingest, k, v)
        sms_ingest.sms_ai.ai_available = self._ai_avail
        sms_ingest._ai_read_cache.clear()


def test_incident_2277_replay():
    """Split-payment receipt (veto-only card …2269) vs deposit from card …3621:
    deferred, not approved; the true owner's order appears within the grace
    and wins by card tie-break."""
    dep = _dep()
    h = _Harness(
        deposits=[dep],
        candidates=[_cand("sub:2277", image="/x/2277.png")],
        ai_reads={
            "sub:2277": {"receipt_mismatch_card_last4": "2269",
                         "receipt_mismatch_refs": ["888888"]},
            "sub:2280": {"receipt_last4": "3621", "refs": []},
        },
    )
    h.install()
    try:
        asyncio.run(sms_ingest._sweep(None))    # pre-read -> contradiction -> defer
        assert h.approved == [] and h.enriched == ["sub:2277"]
        assert h.deposits[0].get("veto_since") and h.deposits[0].get("veto_order") == "sub:2277"

        h.candidates.append(_cand("sub:2280", image="/x/2280.png"))
        asyncio.run(sms_ingest._sweep(None))    # ambiguous -> enrich -> card tie-break
        assert h.approved == ["sub:2280"], h.approved
        assert h.deposits[0].get("matched") == "sub:2280"
        assert not h.notified
    finally:
        h.uninstall()
    print("PASS test_incident_2277_replay")


def test_incident_2292_garbage_receipt():
    """Garbage screenshot + same-amount waiting deposit + new order -> NO
    approval, ONE admin notification (deduped), deposit stays available and
    still routes to a proper order that shows up later."""
    dep = _dep(tracking="170170", dedup_id="170170")
    h = _Harness(
        deposits=[dep],
        candidates=[_cand("sub:2292", image="/x/2292.png")],
        ai_reads={
            "sub:2292": {"receipt_unreadable": True},
            "sub:2300": {"receipt_last4": "3621", "refs": []},
        },
    )
    h.install()
    try:
        asyncio.run(sms_ingest._sweep(None))    # pre-read -> unreadable -> blocked + notified
        assert h.approved == [], h.approved
        assert len(h.notified) == 1 and "sub:2292" in h.notified[0]
        assert h.deposits[0].get("unreadable_notified") == "sub:2292"
        assert h.deposits[0].get("matched") is None

        asyncio.run(sms_ingest._sweep(None))    # sweep again: still blocked, NO second DM
        assert h.approved == [] and len(h.notified) == 1

        # the true owner's order appears -> deposit is still available and
        # routes to it via the card tie-break
        h.candidates.append(_cand("sub:2300", image="/x/2300.png"))
        asyncio.run(sms_ingest._sweep(None))
        assert h.approved == ["sub:2300"], h.approved
        assert h.deposits[0].get("matched") == "sub:2300"
        assert len(h.notified) == 1
    finally:
        h.uninstall()
    print("PASS test_incident_2292_garbage_receipt")


def test_veto_grace_expiry_approves():
    """Contradiction with no better owner: after the grace the pairing
    approves (AI misreads happen) — unlike the unreadable hard gate."""
    dep = _dep()
    h = _Harness(deposits=[dep], candidates=[_cand("sub:9", image="/x/9.png")],
                 ai_reads={"sub:9": {"receipt_mismatch_card_last4": "2269",
                                     "receipt_mismatch_refs": []}})
    h.install()
    try:
        asyncio.run(sms_ingest._sweep(None))            # defer starts
        assert h.approved == []
        asyncio.run(sms_ingest._sweep(None))            # still inside grace
        assert h.approved == []
        h.deposits[0]["veto_since"] = h.deposits[0]["veto_since"] - GRACE - 1
        asyncio.run(sms_ingest._sweep(None))            # grace over -> approve
        assert h.approved == ["sub:9"], h.approved
        assert not h.notified
    finally:
        h.uninstall()
    print("PASS test_veto_grace_expiry_approves")


def test_unreadable_never_approves_even_after_grace():
    """The unreadable gate is HARD: grace expiry never unlocks it."""
    dep = _dep()
    h = _Harness(deposits=[dep], candidates=[_cand("sub:9", image="/x/9.png")],
                 ai_reads={"sub:9": {"receipt_unreadable": True}})
    h.install()
    try:
        asyncio.run(sms_ingest._sweep(None))
        assert h.approved == [] and len(h.notified) == 1
        h.deposits[0]["veto_since"] = int(h.deposits[0].get("veto_since") or 1) - GRACE - 100
        for _ in range(3):
            asyncio.run(sms_ingest._sweep(None))
        assert h.approved == [] and len(h.notified) == 1
    finally:
        h.uninstall()
    print("PASS test_unreadable_never_approves_even_after_grace")


def test_ref_join_is_never_vetoed():
    """Refs agree -> instant approve even when the card looks contradictory."""
    dep = _dep()
    h = _Harness(deposits=[dep], candidates=[_cand("sub:5", image="/x/5.png")],
                 ai_reads={"sub:5": {"receipt_last4": "2269",   # contradicting card...
                                     "refs": ["432247"]}})      # ...but the ref MATCHES
    h.install()
    try:
        asyncio.run(sms_ingest._sweep(None))
        assert h.approved == ["sub:5"], h.approved
        assert not h.notified
    finally:
        h.uninstall()
    print("PASS test_ref_join_is_never_vetoed")


def test_card_tiebreak_stays_instant():
    """A trusted-card match is never gated — even if trusted refs disagree
    (spec: ref joins and card tie-breaks stay instant and unchanged)."""
    dep = _dep()
    h = _Harness(deposits=[dep], candidates=[_cand("sub:6", image="/x/6.png")],
                 ai_reads={"sub:6": {"receipt_last4": "3621", "refs": ["999999"]}})
    h.install()
    try:
        sms_ingest._ai_read_cache["sub:6"] = {"receipt_last4": "3621", "refs": ["999999"]}
        asyncio.run(sms_ingest._sweep(None))
        assert h.approved == ["sub:6"], h.approved
        assert h.deposits[0].get("veto_since") is None
    finally:
        h.uninstall()
    print("PASS test_card_tiebreak_stays_instant")


def test_clean_match_and_matching_evidence_approve_instantly():
    """Clean single match whose receipt reads successfully with the right
    amount (trusted, agreeing card) -> instant approve, no defer."""
    dep = _dep()
    h = _Harness(deposits=[dep], candidates=[_cand("sub:4", image="/x/4.png")],
                 ai_reads={"sub:4": {"receipt_last4": "3621", "refs": []}})
    h.install()
    try:
        asyncio.run(sms_ingest._sweep(None))
        assert h.approved == ["sub:4"], h.approved
        assert h.deposits[0].get("veto_since") is None
    finally:
        h.uninstall()
    print("PASS test_clean_match_and_matching_evidence_approve_instantly")


def test_ai_outage_degrades_to_amount_only():
    """AI read fails (None) -> order is NOT poisoned; the plain unique amount
    match approves exactly as before the port. Same for no-image orders."""
    dep = _dep()
    h = _Harness(deposits=[dep], candidates=[_cand("sub:7", image="/x/7.png")],
                 ai_reads={"sub:7": None})   # read attempt fails
    h.install()
    try:
        asyncio.run(sms_ingest._sweep(None))
        assert h.approved == ["sub:7"], h.approved
        # Item-5 parity: a FAILED read stamps nothing (harness mirrors the
        # real _ai_enrich, which leaves the cache empty and arms the backoff).
        assert sms_ingest._ai_read_cache.get("sub:7") in (None, {})
        assert not h.notified
    finally:
        h.uninstall()

    # no image at all -> nothing to read -> approve as before
    dep2 = _dep(dedup_id="x2")
    h2 = _Harness(deposits=[dep2], candidates=[_cand("sub:8")])
    h2.install()
    try:
        asyncio.run(sms_ingest._sweep(None))
        assert h2.approved == ["sub:8"], h2.approved
    finally:
        h2.uninstall()
    print("PASS test_ai_outage_degrades_to_amount_only")


if __name__ == "__main__":
    test_contradiction_rules()
    test_join_and_evidence_helpers()
    test_ai_enrich_classification()
    test_incident_2277_replay()
    test_incident_2292_garbage_receipt()
    test_veto_grace_expiry_approves()
    test_unreadable_never_approves_even_after_grace()
    test_ref_join_is_never_vetoed()
    test_card_tiebreak_stays_instant()
    test_clean_match_and_matching_evidence_approve_instantly()
    test_ai_outage_degrades_to_amount_only()
    print("\nAll SMS evidence-veto + unreadable-gate tests passed.")
