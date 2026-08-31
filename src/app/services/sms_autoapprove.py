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
  - the caller keeps the bank's tracking number as the cross-system claim key,
    but bank tracking numbers DO get reused: when a same-tracking SMS is proven
    materially different (amount / retrieval / card), it is a second real
    payment, not a replay, and is pooled under its own fingerprint. A tracking
    collision is never approval evidence by itself.
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


# ── RTL card-misread guard (bakbot parity round 2, 2026-07-18) ───────────────
# Iranian receipts print masked cards in print order ("6104 33** **** 2336",
# real last-4 2336) but some bank apps render the SAME card RTL-FLIPPED:
# "1781 43** **** 6104" — real last-4 1781, with 6104 (Bank Mellat's BIN) at
# the visual END. Two live bakbot incidents (Jul 2026): the vision reader
# returned the BANK PREFIX as "last-4", the bogus card contradicted the
# deposit's true payer card, and two legitimate payments sat out the full
# 10-minute veto grace for nothing. A "last-4" equal to a known Iranian BIN
# prefix is a misread, not a card — drop it entirely. Dropping is fail-safe:
# no card read means no join and no veto; it can cost a tie-break but can
# never approve anything.
IRAN_BIN_PREFIXES = frozenset({
    '6104', '6221', '6219', '6037', '5859', '6280', '6063', '6273', '6274',
    '5892', '6362', '5057', '6395', '5022', '6276', '5054', '6055', '5041',
    '6393', '6369',
})


def normalize_card_last4(value) -> str | None:
    """Normalize a card token/line coming from an IMAGE reader (AI vision or
    OCR) into a trustworthy last-4, or None when it cannot be trusted.

    Handles:
      - a bare last-4 ("2336") or a full PAN ("6219861908723264");
      - a masked line in print order   "6104 33** **** 2336" -> 2336;
      - the RTL-FLIPPED rendering      "1781 43** **** 6104" -> 1781
        (the clear group at the OPPOSITE end from the recognizable bank
        prefix — this is also how a verbatim card line returned by the AI
        reader gets resolved);
      - a misread where the reader returned the BIN itself ("6104") -> None.

    NOT applied to the SMS-side source card: ``parse_bank_sms`` reads
    machine-formatted bank TEXT in logical character order, where the
    RTL-vision misread cannot occur — see the comment at that call site.
    """
    s = normalize_digits(str(value or ''))
    groups = re.findall(r'\d+', s)
    digits = ''.join(groups)
    if len(digits) < 4:
        return None
    last4 = digits[-4:]
    if len(groups) > 1:
        # Multi-group (masked / verbatim) line: a recognizable bank prefix
        # marks the card's BEGINNING; the real last-4 is the clear group at
        # the other end. Both ends looking like prefixes is untrustworthy.
        first_bin = groups[0][:4] in IRAN_BIN_PREFIXES
        last_bin = groups[-1][:4] in IRAN_BIN_PREFIXES
        if first_bin and last_bin:
            return None
        if first_bin or last_bin:
            chosen = groups[-1] if first_bin else groups[0]
            if len(chosen) < 4:
                return None
            last4 = chosen[-4:]
        # Neither end recognizable: assume print order (digits[-4:] above).
    return None if last4 in IRAN_BIN_PREFIXES else last4


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
        # SMS-side cards are EXEMPT from the BIN-prefix misread guard
        # (normalize_card_last4): this is machine-generated bank TEXT whose
        # digit runs arrive in logical character order, so the RTL visual
        # flip that makes an IMAGE reader return the bank prefix as "last-4"
        # cannot happen here. Guarding anyway would drop legitimate last-4s
        # that merely collide with a BIN and needlessly defer real payments —
        # the exact failure the guard exists to prevent.
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


# ── segment-aware reference join (bakbot parity, 2026-08-31) ───────────────
# Ported verbatim: the bank SMS and the customer's receipt app print the same
# POL transaction code with its segments permuted, so exact equality misses
# real joins and the payment rides the full veto grace for nothing.
def _plausible_pol_code(s: str) -> bool:
    """18+ digits opening with a plausible Jalali date (14yy mm dd) — the
    shape of a پل (POL) کد رهگیری. Card-to-card refs are far shorter and
    never enter the segment-aware comparison."""
    if len(s) < 18 or not s.startswith('14'):
        return False
    try:
        mm, dd = int(s[4:6]), int(s[6:8])
    except ValueError:
        return False
    return 1 <= mm <= 12 and 1 <= dd <= 31


def _longest_common_digits(a: str, b: str) -> str:
    """Longest contiguous digit run appearing in both strings (codes are
    <=30 chars, the quadratic scan is nothing)."""
    best = ''
    for i in range(len(a)):
        for j in range(i + len(best) + 1, len(a) + 1):
            if a[i:j] in b:
                best = a[i:j]
            else:
                break
    return best


def pol_refs_join(a, b) -> bool:
    """Segment-aware join for پل tracking codes. The bank SMS and the
    customer's receipt app print the SAME transaction's code with its
    segments (Jalali date, 6-digit time, long serial) in DIFFERENT orders and
    with app-specific extra chunks — e.g. order #2998: SMS
    '140505030173131084179145020' vs receipt '14050503145020131084179'
    (date 14050503 · time 145020 · serial 131084179, permuted, SMS adds
    '0173'). Exact equality misses these and the pairing rides the 10-minute
    defer.

    Conservative rule — join only when the codes share ALL of:
      - the 8-digit date prefix (both must open with a plausible date),
      - a long serial: an >=8-digit common run after the date (an >=14-digit
        common run counts as serial+time fused in one block),
      - a 6-digit time: a common run among what remains once the serial is
        removed.
    Anything less (same date+time but a different serial, same date+serial
    but a different time, different dates, short card-to-card refs) is NOT a
    join. Two same-day پل payments never share an >=8-digit serial run."""
    a = re.sub(r'\D', '', str(a or ''))
    b = re.sub(r'\D', '', str(b or ''))
    if not (_plausible_pol_code(a) and _plausible_pol_code(b)):
        return False
    if a == b:
        return True
    if a[:8] != b[:8]:
        return False
    ra, rb = a[8:], b[8:]
    serial = _longest_common_digits(ra, rb)
    if len(serial) >= 14:
        return True
    if len(serial) < 8:
        return False
    t = _longest_common_digits(ra.replace(serial, '', 1), rb.replace(serial, '', 1))
    return len(t) >= 6


def refs_join(refs_a, refs_b) -> bool:
    """True when two ref collections identify the same transaction: exact
    string intersection, or a segment-aware پل join between any pair."""
    A = {str(r) for r in (refs_a or ()) if r}
    B = {str(r) for r in (refs_b or ()) if r}
    if not A or not B:
        return False
    if A & B:
        return True
    return any(pol_refs_join(x, y) for x in A for y in B)


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



def _identity_digits(deposit: dict, full_key: str, last4_key: str) -> str:
    """Best stable card identity available in a parsed bank notification."""
    full = re.sub(r'\D', '', str((deposit or {}).get(full_key) or ''))
    if full:
        return full
    return re.sub(r'\D', '', str((deposit or {}).get(last4_key) or ''))


def deposit_fingerprint(deposit: dict) -> str:
    """Namespaced claim key for one specific bank transaction.

    Used ONLY after a same-tracking collision has been proven by deterministic
    bank fields; normal deposits keep the legacy tracking id so this app and
    bakbot keep contending on the same shared claim.
    """
    amount = deposit_amount_toman(deposit)
    parts = (
        str((deposit or {}).get('tracking') or ''),
        str((deposit or {}).get('retrieval') or ''),
        '' if amount is None else str(amount),
        _identity_digits(deposit, 'source_card', 'source_last4'),
        _identity_digits(deposit, 'dest_card', 'dest_last4'),
    )
    basis = '\x1f'.join(parts)
    return 'sms2:' + hashlib.sha256(basis.encode('utf-8')).hexdigest()[:32]


def deposits_materially_distinct(old: dict, new: dict) -> bool:
    """True only when strong bank fields PROVE two same-id rows are different.

    Missing fields never prove a difference. Fails closed: if a tracking number
    repeats and every field we can compare is identical, automation cannot tell
    the two apart and must treat the second as a replay.
    """
    old_amount = deposit_amount_toman(old)
    new_amount = deposit_amount_toman(new)
    if old_amount is not None and new_amount is not None and old_amount != new_amount:
        return True

    a, b = str((old or {}).get('retrieval') or ''), str((new or {}).get('retrieval') or '')
    if a and b and a != b:
        return True

    for full_key, last4_key in (('source_card', 'source_last4'), ('dest_card', 'dest_last4')):
        a = _identity_digits(old, full_key, last4_key)
        b = _identity_digits(new, full_key, last4_key)
        # last four digits are stable across full and masked representations
        if a and b and a[-4:] != b[-4:]:
            return True
    return False


def classify_deposit_identity(existing: list[dict], incoming: dict) -> str:
    """'new' | 'duplicate' | 'collision' for an incoming SMS against the pool.

    An indistinguishable row wins over older differing ones, so re-forwarding
    an already-accepted collision stays idempotent.
    """
    legacy_id = str((incoming or {}).get('dedup_id') or '')
    same_id = [d for d in (existing or [])
               if str((d or {}).get('dedup_id') or '') == legacy_id]
    if not same_id:
        return 'new'
    if any(not deposits_materially_distinct(old, incoming) for old in same_id):
        return 'duplicate'
    return 'collision'

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
        ref_hits = [c for c in in_window if refs_join(dep_refs, c.get('refs') or ())]
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
            # Image-derived read: run the RTL/BIN misread guard.
            cand = normalize_card_last4(m.group(1))
            if cand:
                best = cand
    return best
