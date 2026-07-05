"""Bank-SMS receipt auto-approval — pure, dependency-free core.

Shared logic with the bakbot sales bot: turn a forwarded PARSIANBANK deposit
SMS into a structured deposit and decide, conservatively, whether it uniquely
matches a single pending order. Pure functions only (no I/O, no bot/DB imports)
so the money-path logic is unit-testable offline. The stateful glue (reading
the channel, DB candidates, calling the approve path) lives in
``services/sms_ingest.py``.

Safety stance (money is involved):
  - amounts must match EXACTLY (to the toman); no fuzzy amounts. Bank SMS
    amounts are RIAL, order prices are TOMAN — the deposit is converted
    (rial // 10) before comparison; a rial amount not divisible by 10 never
    matches anything.
  - a deposit auto-approves at most ONE order, and only when unambiguous.
  - a ref-number join (receipt's شماره مرجع == SMS's شماره بازیابی/پیگیری) may
    break an amount collision, but never overrides the amount gate.
  - the caller dedups by the bank's tracking number (and a cross-system claim)
    so one deposit can never approve twice.
"""

from __future__ import annotations

import hashlib
import re

_DIGIT_MAP = {ord(p): str(i) for i, p in enumerate('۰۱۲۳۴۵۶۷۸۹')}
_DIGIT_MAP.update({ord(p): str(i) for i, p in enumerate('٠١٢٣٤٥٦٧٨٩')})
_DIGIT_MAP[ord('،')] = ','
_DIGIT_MAP[ord('٬')] = ','


def normalize_digits(text: str) -> str:
    return (text or '').translate(_DIGIT_MAP)


def _card_last4(token: str) -> str | None:
    digits = re.sub(r'\D', '', token or '')
    return digits[-4:] if len(digits) >= 4 else None


_CARD_RE = r'([\d][\d*\s]{10,20}[\d*])'


def parse_bank_sms(text: str) -> dict | None:
    """Parse a PARSIANBANK-style deposit SMS; return a deposit dict or None."""
    if not text:
        return None
    t = normalize_digits(text)

    # RTL rendering means the sign can appear before OR after the digits
    # ("مبلغ:+850,000" vs "مبلغ:850,000+"), so accept both positions. The
    # trailing-sign lookahead must not cross the line break (the next line is
    # the balance, which carries its own digits).
    m = re.search(r'مبلغ\s*[:：]?\s*([+\-])?\s*([\d,]+)[^\S\n]*([+\-])?', t)
    if not m:
        return None
    lead, raw_amount, trail = m.group(1), m.group(2), m.group(3)
    if lead == '-' or trail == '-':
        return None  # outgoing / debit
    # Withdrawal SMS sometimes carry no sign at all — the keyword is the tell.
    if 'برداشت' in t and lead != '+' and trail != '+':
        return None
    try:
        amount = int(raw_amount.replace(',', ''))
    except ValueError:
        return None
    if amount <= 0:
        return None

    source_last4 = dest_last4 = dest_card = None
    m_src = re.search(r'از\s*کارت\s*' + _CARD_RE, t)
    if m_src:
        source_last4 = _card_last4(m_src.group(1))
    m_dst = re.search(r'به\s*کارت\s*' + _CARD_RE, t)
    if m_dst:
        dest_digits = re.sub(r'\D', '', m_dst.group(1))
        dest_last4 = dest_digits[-4:] if len(dest_digits) >= 4 else None
        dest_card = dest_digits or None

    m_track = re.search(r'شماره\s*پیگیری\s*[:：]?\s*(\d+)', t)
    tracking = m_track.group(1) if m_track else None
    m_ret = re.search(r'شماره\s*بازیابی\s*[:：]?\s*(\d+)', t)
    retrieval = m_ret.group(1) if m_ret else None

    dedup_id = tracking or retrieval
    if not dedup_id:
        basis = f'{amount}|{source_last4}|{dest_last4}|{t.strip()}'
        dedup_id = 'h' + hashlib.sha256(basis.encode('utf-8')).hexdigest()[:16]

    return {
        'amount': amount,          # as printed in the SMS (rial for PARSIAN)
        'amount_unit': 'rial',
        'source_last4': source_last4,
        'dest_last4': dest_last4,
        'dest_card': dest_card,
        'tracking': tracking,
        'retrieval': retrieval,
        'dedup_id': dedup_id,
        'raw': text,
    }


def deposit_amount_toman(deposit: dict) -> int | None:
    """Deposit amount converted to toman (order prices are toman).

    PARSIAN SMS amounts are rial (1 toman = 10 rial). Deposits pooled before
    this field existed default to rial too. A rial amount not divisible by 10
    is malformed — return None so it can never match. ``amount_unit`` may be
    set to 'toman' by the caller for sources that already report toman.
    """
    try:
        amount = int(deposit.get('amount', 0))
    except (TypeError, ValueError):
        return None
    if amount <= 0:
        return None
    if deposit.get('amount_unit') == 'toman':
        return amount
    return amount // 10 if amount % 10 == 0 else None


def dest_card_allowed(deposit: dict, allowed_last4: set[str]) -> bool:
    dl4 = deposit.get('dest_last4')
    if not dl4:
        return True
    if not allowed_last4:
        return True
    return dl4 in allowed_last4


def pick_match(deposit: dict, candidates: list[dict], deposit_ts: int,
               window_sec: int) -> tuple[str, list]:
    """Decide which pending order (if any) a deposit belongs to.

    `candidates`: [{'order_id': str, 'amount': int (TOMAN), 'receipt_ts': int,
                    'receipt_last4': str|None, 'refs': iterable[str] (opt)}].
    `order_id` is a typed id like 'sub:12' / 'charge:5' / 'vip:3' in ASTROBYTE.
    `refs` are reference numbers read off the customer's receipt image.

    Returns ('approve', order_id) | ('ambiguous', [ids]) | ('none', []).
    """
    amt = deposit_amount_toman(deposit)
    if amt is None:
        return ('none', [])
    in_window = [
        c for c in candidates
        if int(c.get('amount', -1)) == amt
        and abs(int(deposit_ts) - int(c.get('receipt_ts', 0))) <= window_sec
    ]
    if not in_window:
        return ('none', [])

    # Ref-number join beats everything else (still inside the amount gate):
    # the receipt's شماره مرجع equals the SMS's بازیابی/پیگیری only for the
    # actual transfer, so a unique hit is definitive even in a collision.
    dep_refs = {r for r in (deposit.get('tracking'), deposit.get('retrieval')) if r}
    if dep_refs:
        ref_hits = [c for c in in_window if dep_refs & {str(r) for r in (c.get('refs') or ())}]
        if len(ref_hits) == 1:
            return ('approve', ref_hits[0]['order_id'])

    if len(in_window) == 1:
        return ('approve', in_window[0]['order_id'])

    dl4 = deposit.get('source_last4')
    if dl4:
        carded = [c for c in in_window if c.get('receipt_last4') and c['receipt_last4'] == dl4]
        if len(carded) == 1:
            return ('approve', carded[0]['order_id'])

    return ('ambiguous', [c['order_id'] for c in in_window])


def receipt_card_last4(png_bytes: bytes) -> str | None:
    """Best-effort OCR of a receipt image for its card last-4 (None if OCR
    unavailable or nothing found). Safe no-op without tesseract installed."""
    try:
        import io

        import pytesseract  # type: ignore
        from PIL import Image  # type: ignore
    except Exception:
        return None
    try:
        img = Image.open(io.BytesIO(png_bytes))
        raw = pytesseract.image_to_string(img, lang='fas+eng')
    except Exception:
        return None
    t = normalize_digits(raw or '')
    best = None
    for m in re.finditer(_CARD_RE, t):
        digits = re.sub(r'\D', '', m.group(1))
        if 12 <= len(digits) <= 19:
            best = digits[-4:]
    return best
