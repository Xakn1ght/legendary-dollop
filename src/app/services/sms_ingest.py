"""Bank-SMS receipt auto-approval — stateful glue for ASTROBYTE.

Reads forwarded PARSIANBANK deposit SMS (from a channel the user bot is in),
matches each against the single pending order it uniquely belongs to
(purchase / charge / VIP), and approves via the SAME flow-service functions the
admin's Approve button uses. Pure parse/match logic lives in
``services/sms_autoapprove.py``; this file is the impure part (DB, Telegram,
persistence, cross-system claim).

Safety:
  - OFF by default. Needs SMS_SOURCE_CHAT_ID set AND armed (SMS_AUTO_APPROVE=1
    or the runtime state file). ``sms_enabled()`` is the single gate.
  - exact amount + time window; a deposit approves at most ONE order, and only
    when unambiguous. Ambiguous / no match -> manual (unchanged today).
  - deduped by the bank tracking number locally, and by a CROSS-SYSTEM claim
    (shared SQLite) so bakbot and ASTROBYTE watching the same channel can never
    both approve the same deposit.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time

from sqlalchemy import select

from app.core.paths import data_path, webapp_path
from app.core.settings import ADMIN_ID
from app.database.models import AsyncSessionLocal, ChargeRequest, Subscription, VipOrder
from app.services import sms_ai, sms_autoapprove
from app.utils.logger import bot_logger

_SYSTEM = 'astrobyte'


def _clean(name: str, default: str = '') -> str:
    """Env read tolerating an inline '# comment' (never used on secrets)."""
    v = os.environ.get(name, default)
    if v is None:
        v = default
    return v.split('#', 1)[0].strip()


SMS_SOURCE_CHAT_ID = _clean('SMS_SOURCE_CHAT_ID')
SMS_MATCH_WINDOW_SEC = int(_clean('SMS_MATCH_WINDOW_SEC', '2700') or '2700')
SMS_DEPOSIT_TTL_SEC = int(_clean('SMS_DEPOSIT_TTL_SEC', '21600') or '21600')
# Evidence-veto grace: an amount-only match whose evidence CONTRADICTS the
# deposit (wrong payer card / disagreeing refs) is deferred this long so the
# true owner's order can appear and win by card/ref instead (bakbot #2277).
SMS_VETO_GRACE_SEC = int(_clean('SMS_VETO_GRACE_SEC', '600') or '600')
SMS_DEST_CARD_LAST4 = set(x for x in _clean('SMS_DEST_CARD_LAST4').replace(' ', '').split(',') if x)
# Shared across bakbot + ASTROBYTE so one deposit is claimed by exactly one system.
SMS_CLAIM_DB = _clean('SMS_CLAIM_DB', '/root/5a06b8e65bdb/sms_claims.sqlite3')
# After a FAILED AI read (quota 429 / network / no JSON) skip further read
# attempts for this long, then retry. The failure must never stamp the
# one-read-per-order marker (bakbot #2406: a 429'd read counted as "done",
# the order stayed evidence-blind forever and was approved blind).
SMS_AI_FAIL_BACKOFF_SEC = int(_clean('SMS_AI_FAIL_BACKOFF_SEC', '300') or '300')
_ai_fail_until = 0.0

_DEPOSITS_FILE = data_path('sms_deposits.json')
_STATE_FILE = data_path('sms_state.json')
_lock = threading.Lock()


# ── enable / kill-switch ────────────────────────────────────────────────────
def sms_enabled() -> bool:
    if not SMS_SOURCE_CHAT_ID:
        return False
    try:
        with open(_STATE_FILE, encoding='utf-8') as f:
            st = json.load(f)
        if 'enabled' in st:
            return bool(st['enabled'])
    except Exception:
        pass
    return _clean('SMS_AUTO_APPROVE') == '1'


def set_sms_enabled(enabled: bool) -> None:
    try:
        with open(_STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump({'enabled': bool(enabled), 'ts': int(time.time())}, f)
    except Exception as e:
        bot_logger.warning(f'[SMS] could not persist state: {e}')


# ── deposits pool (dedup + late-order sweep) ────────────────────────────────
def _load_deposits() -> list:
    try:
        with open(_DEPOSITS_FILE, encoding='utf-8') as f:
            return json.load(f) or []
    except Exception:
        return []


def _save_deposits(deps: list) -> None:
    try:
        with open(_DEPOSITS_FILE, 'w', encoding='utf-8') as f:
            json.dump(deps, f, ensure_ascii=False)
    except Exception as e:
        bot_logger.warning(f'[SMS] could not persist deposits: {e}')


def _prune(deps: list) -> list:
    cutoff = int(time.time()) - SMS_DEPOSIT_TTL_SEC
    return [d for d in deps if int(d.get('ts', 0)) >= cutoff or d.get('matched')]


# ── cross-system claim ──────────────────────────────────────────────────────
def _claim_deposit(dedup_id: str) -> bool:
    """Atomically claim a deposit id in the shared DB. Returns True if THIS
    system won it (safe to approve); False if another system already owns it."""
    try:
        con = sqlite3.connect(SMS_CLAIM_DB, timeout=5)
        try:
            con.execute('CREATE TABLE IF NOT EXISTS claims('
                        'dedup_id TEXT PRIMARY KEY, system TEXT, ts INTEGER)')
            cur = con.execute('INSERT OR IGNORE INTO claims(dedup_id, system, ts) VALUES(?,?,?)',
                              (dedup_id, _SYSTEM, int(time.time())))
            con.commit()
            return cur.rowcount == 1
        finally:
            con.close()
    except Exception as e:
        # If the shared claim store is unreachable, fail CLOSED (do not approve)
        # to avoid a cross-system double-approve.
        bot_logger.warning(f'[SMS] claim store error, refusing auto-approve: {e}')
        return False


def _release_claim(dedup_id: str) -> None:
    try:
        con = sqlite3.connect(SMS_CLAIM_DB, timeout=5)
        try:
            con.execute('DELETE FROM claims WHERE dedup_id=? AND system=?', (dedup_id, _SYSTEM))
            con.commit()
        finally:
            con.close()
    except Exception:
        pass


# ── candidates + dest cards ─────────────────────────────────────────────────
def _allowed_dest_last4() -> set:
    allowed = set(SMS_DEST_CARD_LAST4)
    try:
        from app.core.settings import payment_ui
        digits = ''.join(ch for ch in (payment_ui.PAYMENT_CARD_NUMBER or '') if ch.isdigit())
        if len(digits) >= 4:
            allowed.add(digits[-4:])
    except Exception:
        pass
    return allowed


# One AI read per order per process: typed id -> cache entry.
#   {'receipt_last4':…, 'refs':[…]}          trusted evidence (amount agrees)
#   {'receipt_mismatch_card_last4':…,
#    'receipt_mismatch_refs':[…]}            VETO-ONLY: receipt amount != order
#       (split payment / wrong screenshot — bakbot #2277). Never a positive
#       join or tie-break; only blocks/defers a contradicted pairing.
#   {'receipt_unreadable': True}             AI READ COMPLETED and the image is
#       not a readable successful transfer (bakbot #2292 garbage screenshot).
#       Such an order must NEVER auto-approve on an amount-only match.
#   {}                                       the local image file is MISSING —
#       degrade to plain amount matching (a retry can't conjure it back).
# A FAILED AI call (quota 429 / network / no JSON) stamps NOTHING here: the
# order stays unread and is retried after SMS_AI_FAIL_BACKOFF_SEC (bakbot
# #2406 — a stamped failure left the order evidence-blind forever).
_ai_read_cache: dict = {}


def _local_receipt_path(receipt_image_url: str | None) -> str | None:
    """Local file for a dashboard-uploaded receipt (/admin/uploads/receipts/x)."""
    if not receipt_image_url:
        return None
    fname = os.path.basename(receipt_image_url)
    if not fname or fname in ('.', '..'):
        return None
    path = webapp_path('admin', 'uploads', 'receipts', fname)
    return path if os.path.isfile(path) else None


async def _candidates(session) -> list:
    """Receipt-backed pending orders across purchase / charge / VIP, shaped for
    sms_autoapprove.pick_match(). Amount is the net the buyer transfers (toman);
    pick_match converts the rial SMS amount itself. `image` is the local
    receipt file used for lazy AI enrichment on collisions."""
    out = []
    subs = (await session.execute(
        select(Subscription).where(Subscription.status == 'pending')
    )).scalars().all()
    for s in subs:
        amt = s.paid_amount if s.paid_amount is not None else s.price
        out.append({'order_id': f'sub:{s.id}', 'amount': int(amt or 0),
                    'receipt_ts': _epoch(s.created_at),
                    'image': _local_receipt_path(s.receipt_image_url)})
    charges = (await session.execute(
        select(ChargeRequest).where(ChargeRequest.status == 'pending')
    )).scalars().all()
    for c in charges:
        amt = c.paid_amount if c.paid_amount is not None else c.price
        out.append({'order_id': f'charge:{c.id}', 'amount': int(amt or 0),
                    'receipt_ts': _epoch(c.created_at),
                    'image': _local_receipt_path(c.receipt_image_url)})
    vips = (await session.execute(
        select(VipOrder).where(VipOrder.status == 'pending')
    )).scalars().all()
    for v in vips:
        out.append({'order_id': f'vip:{v.id}', 'amount': int(v.price or 0),
                    'receipt_ts': _epoch(v.created_at),
                    'image': _local_receipt_path(v.receipt_image_url)})
    return _apply_ai_cache(out)


def _apply_ai_cache(cands: list) -> list:
    """Merge per-order AI-read evidence onto candidate dicts (single source —
    the offline glue tests feed synthetic candidates through this too)."""
    for c in cands:
        cached = _ai_read_cache.get(c['order_id']) or {}
        c['receipt_last4'] = cached.get('receipt_last4')
        c['refs'] = cached.get('refs') or []
        # Veto-only evidence from an amount-mismatched receipt read: never
        # matches positively, only blocks contradicted amount-only matches.
        c['veto_card_last4'] = cached.get('receipt_mismatch_card_last4')
        c['veto_refs'] = cached.get('receipt_mismatch_refs') or []
        # Completed AI read said the image is not a successful transfer —
        # this order may never auto-approve on an amount-only match.
        c['receipt_unreadable'] = bool(cached.get('receipt_unreadable'))
    return cands


async def _ai_enrich(cands: list) -> bool:
    """AI-read receipt images of the given candidates (once per order). Returns
    True if anything new was learned. Classification of a COMPLETED read:
      - success=false OR nothing extractable (no amount, no card, no refs)
        -> receipt_unreadable flag (bakbot #2292: garbage screenshot must not
        behave like clean evidence);
      - readable amount that != the order total -> veto-only fields (bakbot
      #2277: split payment / wrong screenshot still tells us who paid);
      - otherwise -> trusted evidence.
    A FAILED read (AI outage / quota 429 / no JSON) caches NOTHING — the
    one-read-per-order marker is only stamped by a completed read, and a
    global SMS_AI_FAIL_BACKOFF_SEC cooldown throttles the next attempt
    (bakbot #2406: a 429'd read counted as "done" and the order was approved
    blind, forever unable to gain evidence). A missing local file still
    caches {}: retrying cannot conjure the image back."""
    global _ai_fail_until
    if not sms_ai.ai_available():
        return False
    learned = False
    for c in cands:
        oid = c['order_id']
        if oid in _ai_read_cache or not c.get('image'):
            continue
        if time.time() < _ai_fail_until:
            bot_logger.info(f'[SMS] receipt of {oid}: AI-read skipped — failure backoff active '
                            f'({int(_ai_fail_until - time.time())}s left)')
            continue
        try:
            with open(c['image'], 'rb') as f:
                blob = f.read()
        except OSError:
            _ai_read_cache[oid] = {}
            continue
        mime = 'image/png' if c['image'].lower().endswith('.png') else 'image/jpeg'
        fields = await sms_ai.extract_receipt_fields(blob, mime)
        if fields is None:
            _ai_fail_until = time.time() + SMS_AI_FAIL_BACKOFF_SEC
            bot_logger.info(f'[SMS] receipt of {oid}: AI read FAILED (quota/network/no JSON) — '
                            f'read marker NOT stamped; retrying after {SMS_AI_FAIL_BACKOFF_SEC}s')
            continue
        rec_toman = sms_ai.receipt_amount_toman(fields)
        extracted_any = bool(fields.get('amount') or fields.get('source_card_last4')
                             or fields.get('ref_numbers'))
        if not fields.get('success') or not extracted_any:
            entry: dict = {'receipt_unreadable': True}
            bot_logger.info(f'[SMS] receipt of {oid}: not a readable successful-transfer image '
                            f'(success={fields.get("success")}, extracted_any={extracted_any}) '
                            f'— flagged unreadable; amount-only auto-approval blocked')
        elif rec_toman is not None and rec_toman != int(c.get('amount', -1)):
            entry = {'receipt_mismatch_card_last4': fields.get('source_card_last4'),
                     'receipt_mismatch_refs': fields.get('ref_numbers') or []}
            bot_logger.info(f'[SMS] receipt of {oid}: amount {rec_toman} toman != order '
                            f'{c.get("amount")} — fields kept as veto-only evidence '
                            f"(card …{entry.get('receipt_mismatch_card_last4') or '—'} "
                            f"refs {entry.get('receipt_mismatch_refs') or '—'})")
        else:
            entry = {'receipt_last4': fields.get('source_card_last4'),
                     'refs': fields.get('ref_numbers') or []}
            bot_logger.info(f"[SMS] receipt of {oid} AI-read: card …{entry.get('receipt_last4') or '—'} "
                            f"refs {entry.get('refs') or '—'}")
        _ai_read_cache[oid] = entry
        learned = learned or bool(entry)
    return learned


def _epoch(dt) -> int:
    try:
        return int(dt.timestamp())
    except Exception:
        return 0


# ── evidence veto + unreadable gate (bakbot #2277 + #2292, 2026-07-11) ──────
def _dep_refs(dep: dict) -> set:
    return {str(r) for r in (dep.get('tracking'), dep.get('retrieval')) if r}


def _ref_joined(dep: dict, cand: dict) -> bool:
    """True when the deposit's SMS refs agree with the candidate's TRUSTED
    receipt refs — the definitive join; never vetoed, never gated."""
    return bool(_dep_refs(dep) & {str(r) for r in (cand.get('refs') or ()) if r})


def _card_joined(dep: dict, cand: dict) -> bool:
    """True when the deposit's payer card equals the candidate's TRUSTED
    receipt card — the tie-break evidence; stays instant, never gated.
    (Veto-only card can never card-join: it is block-only by definition.)"""
    src4 = dep.get('source_last4')
    return bool(src4 and cand.get('receipt_last4') == src4)


def _has_receipt_evidence(cand: dict) -> bool:
    return bool(cand.get('refs') or cand.get('receipt_last4')
                or cand.get('veto_refs') or cand.get('veto_card_last4')
                or cand.get('receipt_unreadable'))


def _evidence_contradiction(dep: dict, cand: dict) -> str | None:
    """Reason string when the deposit's evidence CONTRADICTS the candidate's
    receipt evidence (trusted or veto-only), else None. Spec order (bakbot
    parity, 2026-07-14):
      1. deposit refs agree with trusted receipt refs -> ref join, NEVER a
         contradiction;
      2. payer card == TRUSTED receipt card -> positive same-payer evidence,
         never a contradiction EVEN IF refs are disjoint (bank apps print
         their own reference numbers — bakbot #2331 was a legit payment
         needlessly deferred 10 min over disjoint refs). Never applied to the
         veto-only card: veto evidence is block-only by definition;
      3. both sides have refs and none agree -> contradiction;
      4. payer card != receipt card (trusted OR veto-only) -> contradiction;
      5. deposit refs vs veto-only refs, both present, none agree ->
         contradiction.
    """
    cand = cand or {}
    dep_refs = _dep_refs(dep)
    trusted_refs = {str(r) for r in (cand.get('refs') or ()) if r}
    if dep_refs & trusted_refs:
        return None  # 1. ref join — definitive, never vetoed
    src4 = dep.get('source_last4')
    if src4 and cand.get('receipt_last4') and str(cand['receipt_last4']) == str(src4):
        return None  # 2. same-payer card agreement — approve, refs may disagree
    if dep_refs and trusted_refs:
        return f'sms refs {sorted(dep_refs)} disagree with receipt refs {sorted(trusted_refs)}'
    if src4:
        for key in ('receipt_last4', 'veto_card_last4'):
            rc = cand.get(key)
            if rc and str(rc) != str(src4):
                return f'payer card …{src4} != receipt card …{rc} ({key})'
    veto_refs = {str(r) for r in (cand.get('veto_refs') or ()) if r}
    if dep_refs and veto_refs and not (dep_refs & veto_refs):
        return f'sms refs {sorted(dep_refs)} disagree with mismatched-receipt refs {sorted(veto_refs)}'
    return None


def _update_deposit(dedup_id: str, **fields) -> None:
    with _lock:
        deps = _load_deposits()
        for d in deps:
            if d.get('dedup_id') == dedup_id:
                d.update(fields)
        _save_deposits(deps)


def _veto_defer(dep: dict, order_id: str, reason: str) -> bool:
    """Contradicted amount-only pairing: defer, don't hard-reject.

    Returns True while the pairing must stay deferred (grace running — the true
    owner's order usually appears and wins by ref/card on a later sweep), and
    False once the grace has expired with no better owner — the caller may then
    approve (AI misreads happen; the unreadable gate is the only hard block).
    The grace clock is per deposit+order pair and persisted on the deposit."""
    now = int(time.time())
    since = int(dep.get('veto_since') or 0)
    if not since or dep.get('veto_order') != order_id:
        dep['veto_since'] = now
        dep['veto_order'] = order_id
        _update_deposit(dep['dedup_id'], veto_since=now, veto_order=order_id)
        bot_logger.info(f"[SMS] evidence veto: deposit {dep['dedup_id']} vs {order_id} — "
                        f"{reason}; deferring up to {SMS_VETO_GRACE_SEC}s")
        return True
    if now - since < SMS_VETO_GRACE_SEC:
        bot_logger.debug(f"[SMS] evidence veto holding: {dep['dedup_id']} vs {order_id} "
                         f"({now - since}s of {SMS_VETO_GRACE_SEC}s)")
        return True
    bot_logger.info(f"[SMS] evidence veto grace expired with no better owner: "
                    f"{dep['dedup_id']} -> {order_id} approving despite: {reason}")
    return False


def _amount_rivals(cand: dict, pending: list) -> list:
    """All unmatched pooled deposits that amount-match candidate order `cand`
    inside the time window — the contention set for an amount-only pairing."""
    out = []
    for d in pending:
        if d.get('matched'):
            continue
        amt = sms_autoapprove.deposit_amount_toman(d)
        if amt is None or amt != int(cand.get('amount', -1)):
            continue
        if abs(int(d.get('ts', 0)) - int(cand.get('receipt_ts', 0))) > SMS_MATCH_WINDOW_SEC:
            continue
        out.append(d)
    return out


def _pick_rival_by_evidence(rivals: list, cand: dict) -> dict | None:
    """Choose which of several amount-matching deposits owns order `cand`,
    by receipt evidence only (bakbot #2406: NEVER by pool position — customer
    B's order consumed customer A's earlier deposit that way):
      1. the deposit whose bank refs intersect the order's TRUSTED receipt
         refs wins;
      2. else exactly ONE deposit whose source card equals the order's
         TRUSTED receipt card wins;
      3. else None — no decisive evidence, caller defers them all.
    """
    cand_refs = {str(r) for r in (cand.get('refs') or ()) if r}
    if cand_refs:
        ref_hits = [d for d in rivals if _dep_refs(d) & cand_refs]
        if len(ref_hits) == 1:
            return ref_hits[0]
    c4 = cand.get('receipt_last4')
    if c4:
        card_hits = [d for d in rivals if str(d.get('source_last4') or '') == str(c4)]
        if len(card_hits) == 1:
            return card_hits[0]
    return None


async def _audit_multi_deposit_deferred(order_id: str, rivals: list) -> None:
    """Panel audit-trail entry for a deferred multi-deposit contention."""
    try:
        from app.services.audit import record_audit
        await record_audit(
            None, 'sms.multi_deposit_deferred', target_type='sms', target_id=order_id,
            summary=f'{len(rivals)} deposits amount-match {order_id} without decisive evidence — all deferred',
            detail={'deposits': [d.get('dedup_id') for d in rivals]},
        )
    except Exception:
        pass


async def _block_unreadable(bot, dep: dict, order_id: str) -> None:
    """Rule 5b: an order whose receipt is a non-receipt image NEVER auto-approves
    on an amount-only match — not even after the grace. Tell the admin once per
    deposit+order pair; the deposit stays unmatched so a better-owning order
    can still take it later."""
    if dep.get('unreadable_notified') == order_id:
        return
    dep['unreadable_notified'] = order_id
    _update_deposit(dep['dedup_id'], unreadable_notified=order_id)
    bot_logger.info(f"[SMS] unreadable-receipt gate: deposit {dep['dedup_id']} amount-matches "
                    f"{order_id} but its receipt is not a readable transfer image — manual only")
    await _notify_admin(
        bot,
        'واریز بانکی با یک سفارش هم‌مبلغ است اما رسید مشتری تصویر یک انتقال موفق قابل‌خواندن نیست — '
        'تایید خودکار انجام نشد. اگر پرداخت را تایید می‌کنید دستی تایید کنید.\n'
        f'مبلغ: {sms_autoapprove.deposit_amount_toman(dep) or 0:,} تومان'
        f' · پیگیری: {dep.get("tracking") or "—"}'
        f' · کارت مبدا: …{dep.get("source_last4") or "—"}\n'
        f'سفارش: {order_id}')


# ── admin notify ────────────────────────────────────────────────────────────
async def _notify_admin(bot, text: str) -> None:
    """Admin hints/alerts go out on the ADMIN bot — never the user bot, even
    though this code runs inside the user-bot process (`bot` is kept only for
    call-compat and as documentation of the calling context)."""
    if not ADMIN_ID:
        return
    try:
        from app.utils.admin_bot_helper import get_admin_bot

        admin_bot = get_admin_bot()
        if not admin_bot:
            bot_logger.warning("[SMS] ADMIN_BOT_TOKEN not set — admin hint skipped (never sent via user bot)")
            return
        await admin_bot.send_message(ADMIN_ID, text)
    except Exception:
        pass


# ── entry points ────────────────────────────────────────────────────────────
async def handle_incoming_sms(bot, text: str) -> None:
    """Parse one forwarded SMS, store it, and try to auto-approve. Opens its own
    DB session so it is independent of the aiogram middleware session lifecycle."""
    dep = sms_autoapprove.parse_bank_sms(text)
    if not dep:
        return
    if not sms_autoapprove.dest_card_allowed(dep, _allowed_dest_last4()):
        return
    with _lock:
        deps = _prune(_load_deposits())
        if any(d.get('dedup_id') == dep['dedup_id'] for d in deps):
            return  # already seen this deposit
        dep['ts'] = int(time.time())
        dep['matched'] = None
        deps.append(dep)
        _save_deposits(deps)
    bot_logger.info(f"[SMS] deposit pooled: {dep['amount']} rial "
                    f"({sms_autoapprove.deposit_amount_toman(dep)} toman) "
                    f"tracking={dep.get('tracking')}")
    await _sweep(bot)


async def sweep_pooled(bot) -> None:
    """Retry all unmatched pooled deposits against current pending orders. Called
    periodically so an SMS that arrived before its receipt still gets matched."""
    if not sms_enabled():
        return
    await _sweep(bot)


async def _sweep(bot) -> None:
    if not sms_enabled():
        return
    with _lock:
        deps = _prune(_load_deposits())
        _save_deposits(deps)
    pending = [d for d in deps if not d.get('matched')]
    if not pending:
        return
    async with AsyncSessionLocal() as session:
        cands = await _candidates(session)
        if not cands:
            return
        for dep in pending:
            kind, res = sms_autoapprove.pick_match(dep, cands, int(dep['ts']), SMS_MATCH_WINDOW_SEC)
            if kind == 'ambiguous' and sms_ai.ai_available():
                # Same-amount collision: AI-read the colliding receipts (once
                # each) to fill card last-4 + refs, then re-pick.
                if await _ai_enrich([c for c in cands if c['order_id'] in res]):
                    cands = await _candidates(session)
                kind, res = sms_autoapprove.pick_match(dep, cands, int(dep['ts']), SMS_MATCH_WINDOW_SEC)
            if kind == 'approve':
                cand = next((c for c in cands if c['order_id'] == res), None)
                # Hard gate for amount-only approvals (both entry points — the
                # incoming-SMS path and the 60s order sweep — funnel through
                # here, so a fresh order can never approve un-inspected; that
                # was bakbot incident #2292). Ref joins and card tie-breaks
                # stay instant and unchanged.
                if cand is not None and not _ref_joined(dep, cand) and not _card_joined(dep, cand):
                    # 5a. The winner's receipt has never been AI-read: read it
                    # NOW, then re-evaluate the pick with the new evidence.
                    if (cand['order_id'] not in _ai_read_cache
                            and sms_ai.ai_available() and cand.get('image')):
                        if await _ai_enrich([cand]):
                            cands = await _candidates(session)
                            kind, res = sms_autoapprove.pick_match(
                                dep, cands, int(dep['ts']), SMS_MATCH_WINDOW_SEC)
                            cand = next((c for c in cands if c['order_id'] == res), None)
                    if kind == 'approve' and cand is not None \
                            and not _ref_joined(dep, cand) and not _card_joined(dep, cand):
                        # 5b. A garbage/non-receipt image never auto-approves.
                        if cand.get('receipt_unreadable'):
                            await _block_unreadable(bot, dep, res)
                            continue
                        # 5d. Multi-deposit contention (bakbot #2406): when
                        # SEVERAL pooled deposits amount-match this order,
                        # the owner is chosen by receipt evidence (ref join,
                        # then payer card) — never by pool position. With no
                        # decisive evidence ALL rivals are deferred for the
                        # grace and audit-logged; the sweep (or a human)
                        # resolves after that.
                        rivals = _amount_rivals(cand, [p for p in pending if not p.get('matched')])
                        if len(rivals) > 1:
                            chosen = _pick_rival_by_evidence(rivals, cand)
                            if chosen is not None and chosen.get('dedup_id') != dep.get('dedup_id'):
                                # The rightful deposit approves this order in
                                # its own turn; this one stays available.
                                bot_logger.info(
                                    f"[SMS] contention: {len(rivals)} deposits match {res}; "
                                    f"evidence picks {chosen.get('dedup_id')} — skipping {dep['dedup_id']}")
                                continue
                            if chosen is None:
                                fresh = dep.get('veto_order') != res or not dep.get('veto_since')
                                if fresh:
                                    await _audit_multi_deposit_deferred(res, rivals)
                                    for r in rivals:
                                        if r.get('dedup_id') != dep.get('dedup_id'):
                                            _veto_defer(r, res, 'multi-deposit contention (no decisive evidence)')
                                if _veto_defer(dep, res, 'multi-deposit contention (no decisive evidence)'):
                                    continue
                        # 5c. Contradicting evidence defers for the grace, then
                        # (no better owner having appeared) approves.
                        reason = _evidence_contradiction(dep, cand)
                        if reason and _veto_defer(dep, res, reason):
                            continue
            if kind == 'approve':
                ok = await _approve(bot, session, res, dep)
                if ok:
                    dep['matched'] = res  # in-memory too: rivals within THIS sweep must see it
                    _mark_matched(dep['dedup_id'], res)
                    # This order is consumed; drop it from the candidate pool.
                    cands = [c for c in cands if c['order_id'] != res]
            elif kind == 'ambiguous':
                hint = await sms_ai.match_hint(
                    dep.get('raw', ''), dep, [c for c in cands if c['order_id'] in res]) or ''
                await _notify_admin(
                    bot,
                    'واریز بانکی با چند سفارش هم‌خوانی داشت (تأیید دستی لازم):\n'
                    f'مبلغ: {sms_autoapprove.deposit_amount_toman(dep) or 0:,} تومان'
                    f' · پیگیری: {dep.get("tracking") or "—"}\n'
                    f'سفارش‌ها: {", ".join(res)}'
                    + (f'\n\nپیشنهاد هوش مصنوعی:\n{hint}' if hint else ''))


def _mark_matched(dedup_id: str, order_id: str) -> None:
    with _lock:
        deps = _load_deposits()
        for d in deps:
            if d.get('dedup_id') == dedup_id:
                d['matched'] = order_id
        _save_deposits(deps)


async def _approve(bot, session, typed_id: str, dep: dict) -> bool:
    """Approve one order via the correct flow service. Claims the deposit in the
    shared store first so no other system (bakbot) can also approve it."""
    try:
        kind, sid = typed_id.split(':', 1)
        oid = int(sid)
    except Exception:
        return False

    if not _claim_deposit(dep['dedup_id']):
        bot_logger.info(f"[SMS] deposit {dep['dedup_id']} already claimed elsewhere; skip {typed_id}")
        return False

    try:
        if kind == 'sub':
            from app.services.subscription_processing import process_approved_subscription
            sub = await session.get(Subscription, oid)
            if not sub or sub.status != 'pending':
                _release_claim(dep['dedup_id'])
                return False
            ok = await process_approved_subscription(oid, session, bot, approved_by="سیستم (پیامک بانک)")
        elif kind == 'charge':
            from app.services.flows.charge import approve_charge
            from app.services.flows.errors import FlowError
            try:
                await approve_charge(session, oid, user_bot=bot)
                ok = True
            except FlowError as e:
                bot_logger.warning(f'[SMS] charge approve failed {oid}: {e.code}')
                ok = False
        elif kind == 'vip':
            from app.handlers.admin.vip import activate_vip_order
            v = await session.get(VipOrder, oid)
            if not v or v.status != 'pending':
                _release_claim(dep['dedup_id'])
                return False
            ok = await activate_vip_order(session, v, notify_user_bot=bot)
        else:
            ok = False
    except Exception as e:
        bot_logger.error(f'[SMS] approve error {typed_id}: {e}')
        ok = False

    if not ok:
        _release_claim(dep['dedup_id'])
        return False

    bot_logger.info(f'[SMS] AUTO-APPROVED {typed_id} amount={dep["amount"]} tracking={dep.get("tracking")}')
    # dep['amount'] is the raw RIAL figure — show the toman value users/admins think in.
    await _notify_admin(
        bot,
        f'تأیید خودکار از روی پیامک بانک\n'
        f'سفارش: {typed_id}\n'
        f'مبلغ: {sms_autoapprove.deposit_amount_toman(dep) or 0:,} تومان\n'
        f'کارت مبدأ: …{dep.get("source_last4") or "—"} · پیگیری: {dep.get("tracking") or "—"}')
    return True
