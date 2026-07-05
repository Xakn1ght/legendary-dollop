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
SMS_DEST_CARD_LAST4 = set(x for x in _clean('SMS_DEST_CARD_LAST4').replace(' ', '').split(',') if x)
# Shared across bakbot + ASTROBYTE so one deposit is claimed by exactly one system.
SMS_CLAIM_DB = _clean('SMS_CLAIM_DB', '/root/5a06b8e65bdb/sms_claims.sqlite3')

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


# One AI read per order per process: typed id -> {'receipt_last4':…, 'refs':[…]}
# ({} = tried and got nothing usable, so we don't burn quota again).
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
    for c in out:
        cached = _ai_read_cache.get(c['order_id']) or {}
        c['receipt_last4'] = cached.get('receipt_last4')
        c['refs'] = cached.get('refs') or []
    return out


async def _ai_enrich(cands: list) -> bool:
    """AI-read receipt images of the given candidates (once per order). Returns
    True if anything new was learned. Fields with an amount that contradicts
    the order are discarded (wrong screenshot -> human)."""
    if not sms_ai.ai_available():
        return False
    learned = False
    for c in cands:
        oid = c['order_id']
        if oid in _ai_read_cache or not c.get('image'):
            continue
        try:
            with open(c['image'], 'rb') as f:
                blob = f.read()
        except OSError:
            _ai_read_cache[oid] = {}
            continue
        mime = 'image/png' if c['image'].lower().endswith('.png') else 'image/jpeg'
        fields = await sms_ai.extract_receipt_fields(blob, mime)
        entry: dict = {}
        if fields:
            rec_toman = sms_ai.receipt_amount_toman(fields)
            if rec_toman is not None and rec_toman != int(c.get('amount', -1)):
                bot_logger.info(f'[SMS] receipt of {oid}: amount {rec_toman} toman != order '
                                f'{c.get("amount")} — ignoring extracted fields')
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


# ── admin notify ────────────────────────────────────────────────────────────
async def _notify_admin(bot, text: str) -> None:
    if not (bot and ADMIN_ID):
        return
    try:
        await bot.send_message(ADMIN_ID, text)
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
                ok = await _approve(bot, session, res, dep)
                if ok:
                    _mark_matched(dep['dedup_id'], res)
                    # This order is consumed; drop it from the candidate pool.
                    cands = [c for c in cands if c['order_id'] != res]
            elif kind == 'ambiguous':
                hint = await sms_ai.match_hint(
                    dep.get('raw', ''), dep, [c for c in cands if c['order_id'] in res]) or ''
                await _notify_admin(
                    bot,
                    '🤖 واریز بانکی با چند سفارش هم‌خوانی داشت (تأیید دستی لازم):\n'
                    f'مبلغ: {sms_autoapprove.deposit_amount_toman(dep) or 0:,} تومان'
                    f' · پیگیری: {dep.get("tracking") or "—"}\n'
                    f'سفارش‌ها: {", ".join(res)}'
                    + (f'\n\n💡 پیشنهاد هوش مصنوعی:\n{hint}' if hint else ''))


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
            ok = await process_approved_subscription(oid, session, bot)
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
    await _notify_admin(
        bot,
        f'🤖 تأیید خودکار از روی پیامک بانک\n'
        f'سفارش: {typed_id}\n'
        f'مبلغ: {dep["amount"]:,} تومان\n'
        f'کارت مبدأ: …{dep.get("source_last4") or "—"} · پیگیری: {dep.get("tracking") or "—"}')
    return True
