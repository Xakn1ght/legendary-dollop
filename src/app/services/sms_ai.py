"""Free-tier AI assist for bank-SMS receipt matching (optional; dormant without a key).

Async twin of bakbot's ``sms_ai.py``. Two jobs, both PERCEPTION — the AI never
approves anything:
  1. ``extract_receipt_fields(image_bytes)``: read a customer's receipt image
     (any Iranian bank app layout, Persian digits) into structured fields:
     amount, source-card last-4 (کارت مبدا), reference numbers (شماره
     مرجع/پیگیری/بازیابی). Those fields feed the DETERMINISTIC matcher in
     ``sms_autoapprove.pick_match()``.
  2. ``match_hint(...)``: for a deposit the rules could not resolve, write the
     admin a short Persian suggestion. Advisory text only.

Providers (checked in this order; set whichever key you have in config/.env):
  - GEMINI_API_KEY      Google AI Studio free tier (~1500 req/day on Flash).
  - OPENROUTER_API_KEY  OpenRouter :free vision models (~50 req/day).

No key -> ``ai_available()`` is False and callers skip AI entirely.
"""
from __future__ import annotations

import base64
import json
import os
import re

import aiohttp

from app.utils.logger import bot_logger

_TIMEOUT = aiohttp.ClientTimeout(total=30, connect=5)


def _clean(name: str, default: str = '') -> str:
    v = os.environ.get(name, default)
    if v is None:
        v = default
    return v.split('#', 1)[0].strip()


GEMINI_API_KEY = _clean('GEMINI_API_KEY')
OPENROUTER_API_KEY = _clean('OPENROUTER_API_KEY')
# First model that answers wins; env override goes first if set.
GEMINI_MODELS = [m for m in [_clean('SMS_AI_MODEL')] if m] + [
    'gemini-3-flash', 'gemini-2.5-flash', 'gemini-2.0-flash',
]
OPENROUTER_MODEL = _clean('OPENROUTER_MODEL', 'google/gemma-4-31b-it:free')


def ai_available() -> bool:
    return bool(GEMINI_API_KEY or OPENROUTER_API_KEY)


# ── provider plumbing ───────────────────────────────────────────────────────
async def _gemini(prompt: str, image_bytes: bytes | None = None,
                  mime: str = 'image/jpeg', want_json: bool = True) -> str | None:
    if not GEMINI_API_KEY:
        return None
    parts = [{'text': prompt}]
    if image_bytes:
        parts.append({'inline_data': {'mime_type': mime,
                                      'data': base64.b64encode(image_bytes).decode()}})
    payload = {'contents': [{'parts': parts}]}
    if want_json:
        payload['generationConfig'] = {'response_mime_type': 'application/json'}
    async with aiohttp.ClientSession(timeout=_TIMEOUT) as http:
        for model in GEMINI_MODELS:
            try:
                async with http.post(
                    f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
                    params={'key': GEMINI_API_KEY}, json=payload,
                ) as r:
                    if r.status == 404:
                        continue  # model id not on this account — try the next
                    if r.status != 200:
                        bot_logger.warning(f'[SMS-AI] gemini {model} HTTP {r.status}: {(await r.text())[:200]}')
                        return None
                    data = await r.json()
                cands = data.get('candidates') or []
                texts = [p.get('text', '') for c in cands
                         for p in (c.get('content', {}).get('parts') or [])]
                out = ''.join(texts).strip()
                return out or None
            except Exception as e:
                bot_logger.warning(f'[SMS-AI] gemini error: {e}')
                return None
    return None


async def _openrouter(prompt: str, image_bytes: bytes | None = None,
                      mime: str = 'image/jpeg') -> str | None:
    if not OPENROUTER_API_KEY:
        return None
    content: list | str
    if image_bytes:
        data_uri = f'data:{mime};base64,' + base64.b64encode(image_bytes).decode()
        content = [{'type': 'text', 'text': prompt},
                   {'type': 'image_url', 'image_url': {'url': data_uri}}]
    else:
        content = prompt
    try:
        async with aiohttp.ClientSession(timeout=_TIMEOUT) as http:
            async with http.post(
                'https://openrouter.ai/api/v1/chat/completions',
                headers={'Authorization': f'Bearer {OPENROUTER_API_KEY}'},
                json={'model': OPENROUTER_MODEL,
                      'messages': [{'role': 'user', 'content': content}]},
            ) as r:
                if r.status != 200:
                    bot_logger.warning(f'[SMS-AI] openrouter HTTP {r.status}: {(await r.text())[:200]}')
                    return None
                data = await r.json()
        choices = data.get('choices') or []
        out = (choices[0].get('message', {}).get('content') or '').strip() if choices else ''
        return out or None
    except Exception as e:
        bot_logger.warning(f'[SMS-AI] openrouter error: {e}')
        return None


async def _ask(prompt: str, image_bytes: bytes | None = None,
               mime: str = 'image/jpeg', want_json: bool = True) -> str | None:
    out = await _gemini(prompt, image_bytes, mime, want_json)
    if out is None:
        out = await _openrouter(prompt, image_bytes, mime)
    return out


def extract_json(text: str) -> dict | None:
    """Pull the first JSON object out of a model reply (tolerates ``` fences)."""
    if not text:
        return None
    t = re.sub(r'^```(?:json)?\s*|\s*```$', '', text.strip(), flags=re.MULTILINE)
    start = t.find('{')
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(t)):
        if t[i] == '{':
            depth += 1
        elif t[i] == '}':
            depth -= 1
            if depth == 0:
                try:
                    obj = json.loads(t[start:i + 1])
                    return obj if isinstance(obj, dict) else None
                except ValueError:
                    return None
    return None


# ── job 1: receipt image -> structured fields ───────────────────────────────
_RECEIPT_PROMPT = """You extract data from IRANIAN bank / card-to-card transfer receipt images.
Layouts vary by bank app (blubank, Resalat, Saman, ...). Text is Persian; digits may be Persian (۰-۹).

Return ONLY strict JSON, exactly this shape (null when a field is absent/unreadable):
{"success": true|false, "amount": <int|null>, "amount_unit": "rial"|"toman"|null,
 "source_card_last4": "<4 digits|null>", "dest_card_last4": "<4 digits|null>",
 "ref_numbers": ["<digits>", ...], "time_text": "<string|null>"}

Rules:
- success: true only if the receipt clearly shows a SUCCESSFUL transfer (e.g. انتقال موفق).
- amount: the transferred amount (مبلغ / مبلغ انتقال) as an integer, no separators.
- amount_unit: "rial" if the receipt says ریال, "toman" if it says تومان; null if unclear.
- source_card_last4: last 4 REAL digits of the SENDER card (کارت مبدا / از کارت). Cards may be masked like ‎6219 86** **** 7804 — take the last visible 4 digits.
- dest_card_last4: same for the RECEIVING card (کارت مقصد / به کارت).
- ref_numbers: every reference-like number on the receipt (شماره مرجع، شماره پیگیری، شماره بازیابی، کد رهگیری), digits only, as strings.
- time_text: the receipt's own date/time line verbatim, if any.
Output the JSON object only — no prose, no markdown."""


async def extract_receipt_fields(image_bytes: bytes, mime: str = 'image/jpeg') -> dict | None:
    """AI-read one receipt image. Returns the parsed dict (normalised) or None."""
    if not ai_available() or not image_bytes:
        return None
    out = await _ask(_RECEIPT_PROMPT, image_bytes, mime)
    d = extract_json(out or '')
    if not d:
        return None

    def _l4(v):
        digits = re.sub(r'\D', '', str(v or ''))
        return digits[-4:] if len(digits) >= 4 else None

    refs = []
    for r in (d.get('ref_numbers') or []):
        digits = re.sub(r'\D', '', str(r))
        if 4 <= len(digits) <= 30:
            refs.append(digits)
    amount = None
    try:
        a = int(re.sub(r'\D', '', str(d.get('amount'))))
        amount = a if a > 0 else None
    except (TypeError, ValueError):
        pass
    unit = d.get('amount_unit') if d.get('amount_unit') in ('rial', 'toman') else None
    return {
        'success': bool(d.get('success')),
        'amount': amount,
        'amount_unit': unit,
        'source_card_last4': _l4(d.get('source_card_last4')),
        'dest_card_last4': _l4(d.get('dest_card_last4')),
        'ref_numbers': refs,
        'time_text': (str(d.get('time_text')) if d.get('time_text') else None),
    }


def receipt_amount_toman(fields: dict) -> int | None:
    """Receipt amount in toman, or None if the unit is unknown/ambiguous."""
    amount = fields.get('amount')
    if not amount:
        return None
    unit = fields.get('amount_unit')
    if unit == 'toman':
        return int(amount)
    if unit == 'rial':
        return int(amount) // 10 if amount % 10 == 0 else None
    return None


# ── job 2: advisory hint for the admin ──────────────────────────────────────
_HINT_PROMPT = """You help an admin match ONE Iranian bank deposit SMS to ONE pending VPN order.
The deterministic system could not decide. Give a SHORT recommendation in PERSIAN (max 3 lines):
which order id most likely matches and why (amount/time/card/ref evidence), or say it's undecidable.
You are ADVISORY ONLY — a human presses the button. Do not invent data.

Bank SMS (amounts here are RIAL; order prices are TOMAN, 1 toman = 10 rial):
{sms}

Deposit parsed: amount_toman={amount_toman}, source_card_last4={src4}, refs={refs}

Pending orders (id | amount_toman | created | receipt_card_last4 | receipt_refs):
{orders}"""


async def match_hint(sms_text: str, deposit: dict, candidates: list[dict]) -> str | None:
    """Short Persian advisory for the admin. None if AI is off or errors."""
    if not ai_available():
        return None
    from app.services.sms_autoapprove import deposit_amount_toman
    lines = []
    for c in candidates[:12]:
        lines.append(f"{c.get('order_id')} | {c.get('amount')} | ts={c.get('receipt_ts')}"
                     f" | card={c.get('receipt_last4') or '—'}"
                     f" | refs={','.join(str(r) for r in (c.get('refs') or [])) or '—'}")
    prompt = _HINT_PROMPT.format(
        sms=(sms_text or '')[:800],
        amount_toman=deposit_amount_toman(deposit),
        src4=deposit.get('source_last4') or '—',
        refs=','.join(x for x in (deposit.get('tracking'), deposit.get('retrieval')) if x) or '—',
        orders='\n'.join(lines) or '(none)',
    )
    out = await _ask(prompt, want_json=False)
    if not out:
        return None
    return out.strip()[:600]
