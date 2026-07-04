"""Bank-SMS receipt auto-approval — pure, dependency-free core.

Shared logic with the bakbot sales bot: turn a forwarded PARSIANBANK deposit
SMS into a structured deposit and decide, conservatively, whether it uniquely
matches a single pending order. Pure functions only (no I/O, no bot/DB imports)
so the money-path logic is unit-testable offline. The stateful glue (reading
the channel, DB candidates, calling the approve path) lives in
``services/sms_ingest.py``.

Safety stance (money is involved):
  - amounts must match EXACTLY (to the toman); no fuzzy amounts.
  - a deposit auto-approves at most ONE order, and only when unambiguous.
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

    m = re.search(r'مبلغ\s*[:：]?\s*([+\-])?\s*([\d,]+)', t)
    if not m:
        return None
    sign, raw_amount = m.group(1), m.group(2)
    if sign == '-':
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
        'amount': amount,
        'source_last4': source_last4,
        'dest_last4': dest_last4,
        'dest_card': dest_card,
        'tracking': tracking,
        'retrieval': retrieval,
        'dedup_id': dedup_id,
        'raw': text,
    }


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

    `candidates`: [{'order_id': str, 'amount': int, 'receipt_ts': int,
                    'receipt_last4': str|None}]. `order_id` is a typed id like
    'sub:12' / 'charge:5' / 'vip:3' in ASTROBYTE.

    Returns ('approve', order_id) | ('ambiguous', [ids]) | ('none', []).
    """
    amt = deposit['amount']
    in_window = [
        c for c in candidates
        if int(c.get('amount', -1)) == amt
        and abs(int(deposit_ts) - int(c.get('receipt_ts', 0))) <= window_sec
    ]
    if not in_window:
        return ('none', [])
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
