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
    GEMINI_API_KEY2     Optional second key (different Google account) used
                        when the first is quota-exhausted: keys iterate OUTER,
                        models INNER — HTTP 429 jumps to the next key (same
                        model list), HTTP 404 tries the next model (same key).
                        2026-format keys start with "AQ." (old "AIza…" work).
  - NVIDIA_API_KEY      NVIDIA NIM (integrate.api.nvidia.com, OpenAI chat
                        format). TEXT ONLY (admin match-hints): ground-truth
                        tests on real Iranian receipts (Jul 2026) showed NIM
                        vision models must NEVER read receipts —
                        nemotron-nano-12b-v2-vl fabricates plausible digits
                        (fake refs/cards, the worst failure for a money
                        matcher), llama-3.2-90b-vision refuses financial
                        images, gemma-4-31b-it/qwen3.5 cold-start past 25s,
                        gemma-3-27b is EOL (HTTP 410).
  - OPENROUTER_API_KEY  OpenRouter :free vision models (~50 req/day).

No key -> ``ai_available()`` is False and callers skip AI entirely.
"""
from __future__ import annotations

import base64
import json
import os
import re

import aiohttp

from app.services.sms_autoapprove import normalize_card_last4
from app.utils.logger import bot_logger

_TIMEOUT = aiohttp.ClientTimeout(total=30, connect=5)


def _clean(name: str, default: str = '') -> str:
    v = os.environ.get(name, default)
    if v is None:
        v = default
    return v.split('#', 1)[0].strip()


GEMINI_API_KEY = _clean('GEMINI_API_KEY')
# Optional second key (different Google account): its own ~1500 req/day budget.
GEMINI_API_KEY2 = _clean('GEMINI_API_KEY2')
GEMINI_KEYS = [k for k in (GEMINI_API_KEY, GEMINI_API_KEY2) if k]
NVIDIA_API_KEY = _clean('NVIDIA_API_KEY')
OPENROUTER_API_KEY = _clean('OPENROUTER_API_KEY')
# First model that answers wins; env override goes first if set.
# Mixed old/new-account list: 2.5-flash is the proven digit-exact reader on
# older keys but 404s ("not available to new users") on 2026 Google accounts,
# which get 3-flash-preview / 3.1-flash-lite instead. 404 tries the next
# model on the same key; 429 jumps to the next key.
GEMINI_MODELS = [m for m in [_clean('SMS_AI_MODEL')] if m] + [
    'gemini-2.5-flash', 'gemini-3-flash-preview',
    'gemini-3.1-flash-lite', 'gemini-2.0-flash',
]
# TEXT models only — see the NVIDIA note in the module docstring. Override via
# NVIDIA_MODEL only after a ground-truth digit test against known receipts.
NVIDIA_MODELS = [m for m in [_clean('NVIDIA_MODEL')] if m] + [
    'nvidia/nvidia-nemotron-nano-9b-v2',
    'qwen/qwen3-next-80b-a3b-instruct',
]
OPENROUTER_MODEL = _clean('OPENROUTER_MODEL', 'google/gemma-4-31b-it:free')


def ai_available() -> bool:
    return bool(GEMINI_KEYS or NVIDIA_API_KEY or OPENROUTER_API_KEY)


# ── provider plumbing ───────────────────────────────────────────────────────
async def _post(http: aiohttp.ClientSession, url: str, *, params=None,
                headers=None, payload=None) -> tuple[int, str]:
    """One POST -> (status, body text). Kept tiny so tests can monkeypatch it."""
    async with http.post(url, params=params, headers=headers, json=payload) as r:
        return r.status, await r.text()


async def _gemini(prompt: str, image_bytes: bytes | None = None,
                  mime: str = 'image/jpeg', want_json: bool = True) -> str | None:
    if not GEMINI_KEYS:
        return None
    parts = [{'text': prompt}]
    if image_bytes:
        parts.append({'inline_data': {'mime_type': mime,
                                      'data': base64.b64encode(image_bytes).decode()}})
    gen_cfg: dict = {}
    if want_json:
        gen_cfg['response_mime_type'] = 'application/json'
    # Extraction needs no reasoning: gemini-3 models "think" by default and can
    # blow a 25s read budget on images (measured 25s+ -> 2.8s with thinking
    # off). Models that reject the knob get one retry without it (400).
    gen_cfg['thinkingConfig'] = {'thinkingBudget': 0}
    payload = {'contents': [{'parts': parts}], 'generationConfig': gen_cfg}
    async with aiohttp.ClientSession(timeout=_TIMEOUT) as http:
        for ki, key in enumerate(GEMINI_KEYS):
            for model in GEMINI_MODELS:
                body = payload
                status: int | None = None
                text = ''
                for attempt in range(2):
                    try:
                        status, text = await _post(
                            http,
                            f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
                            params={'key': key}, payload=body)
                    except Exception as e:
                        # Timeout / network: advance to the next model, never
                        # abort the whole chain.
                        bot_logger.warning(f'[SMS-AI] gemini {model} error: {e} — trying next model')
                        status = None
                        break
                    if status == 400 and attempt == 0 and 'thinkingConfig' in (body.get('generationConfig') or {}):
                        # Model rejects the thinking knob — retry once without it.
                        body = {**payload,
                                'generationConfig': {k: v for k, v in gen_cfg.items() if k != 'thinkingConfig'}}
                        continue
                    break
                if status is None:
                    continue
                if status == 404:
                    continue  # model id not available on this account — next model
                if status == 429:
                    bot_logger.warning(f'[SMS-AI] gemini key{ki + 1} {model} quota 429'
                                       + (' — trying next key' if ki + 1 < len(GEMINI_KEYS) else ''))
                    break  # this key is exhausted — same model list on the next key
                if status != 200:
                    bot_logger.warning(f'[SMS-AI] gemini {model} HTTP {status}: {text[:200]}')
                    continue  # non-quota HTTP error — next model
                try:
                    data = json.loads(text)
                except ValueError:
                    continue
                cands = data.get('candidates') or []
                texts = [p.get('text', '') for c in cands
                         for p in (c.get('content', {}).get('parts') or [])]
                out = ''.join(texts).strip()
                if out:
                    return out
    return None


async def _nvidia(prompt: str) -> str | None:
    """NVIDIA NIM, TEXT ONLY — never handed a receipt image (vision models
    fabricate digits / refuse / cold-start; see module docstring). 400/404/410
    and per-model timeouts advance to the next model."""
    if not NVIDIA_API_KEY:
        return None
    async with aiohttp.ClientSession(timeout=_TIMEOUT) as http:
        for model in NVIDIA_MODELS:
            try:
                status, text = await _post(
                    http, 'https://integrate.api.nvidia.com/v1/chat/completions',
                    headers={'Authorization': f'Bearer {NVIDIA_API_KEY}'},
                    payload={'model': model,
                             'messages': [{'role': 'user', 'content': prompt}],
                             'max_tokens': 1024, 'temperature': 0})
            except Exception as e:
                # Cold/heavy models time out — give the next one a shot.
                bot_logger.warning(f'[SMS-AI] nvidia {model} error: {e} — trying next model')
                continue
            if status in (400, 404, 410):
                continue  # model rejected/retired for this account — next model
            if status != 200:
                bot_logger.warning(f'[SMS-AI] nvidia {model} HTTP {status}: {text[:200]}')
                return None
            try:
                data = json.loads(text)
            except ValueError:
                continue
            choices = data.get('choices') or []
            out = (choices[0].get('message', {}).get('content') or '').strip() if choices else ''
            if out:
                return out
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
            status, text = await _post(
                http, 'https://openrouter.ai/api/v1/chat/completions',
                headers={'Authorization': f'Bearer {OPENROUTER_API_KEY}'},
                payload={'model': OPENROUTER_MODEL,
                         'messages': [{'role': 'user', 'content': content}]})
        if status != 200:
            bot_logger.warning(f'[SMS-AI] openrouter HTTP {status}: {text[:200]}')
            return None
        data = json.loads(text)
        choices = data.get('choices') or []
        out = (choices[0].get('message', {}).get('content') or '').strip() if choices else ''
        return out or None
    except Exception as e:
        bot_logger.warning(f'[SMS-AI] openrouter error: {e}')
        return None


async def _ask(prompt: str, image_bytes: bytes | None = None,
               mime: str = 'image/jpeg', want_json: bool = True) -> str | None:
    out = await _gemini(prompt, image_bytes, mime, want_json)
    if out is None and image_bytes is None:
        # NIM is a TEXT-ONLY fallback — its vision models hallucinated
        # digits / refused on real receipts (see module docstring).
        out = await _nvidia(prompt)
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
- source_card_last4: last 4 REAL digits of the SENDER card (کارت مبدا / از کارت).
- dest_card_last4: same for the RECEIVING card (کارت مقصد / به کارت).
- CARD LAYOUT (critical): cards are masked and appear in TWO possible orders.
  Print order: "6219 86** **** 7804" — bank prefix (6219) first, real last-4 (7804) at the end.
  RTL-FLIPPED order: "1781 43** **** 6104" — the SAME kind of card rendered right-to-left: the recognizable
  bank prefix (6104, 6219, 6037, 5892, ...) sits at the visual END and the REAL last-4 (1781) is at the visual START.
  The real last-4 is ALWAYS the clear 4-digit group NEXT TO the masked stars, at the OPPOSITE end from the
  recognizable Iranian bank prefix (6104=Mellat, 6219=Saman, 6037=Melli/Keshavarzi, 5892=Sepah, 6221=Parsian, ...).
  NEVER return the bank prefix as the last-4. If you cannot tell which end is which, return the whole card
  line VERBATIM (all its digit groups and stars) in the field instead of guessing 4 digits.
- ref_numbers: every reference-like number on the receipt (شماره مرجع، شماره پیگیری، شماره بازیابی، کد رهگیری), digits only, as strings.
- CRITICAL: transcribe long numbers DIGIT BY DIGIT, exactly as printed — never drop, add or reorder a digit. Re-read each ref number once to verify before answering.
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
        # Image-derived card fields go through the shared RTL/BIN misread
        # guard: it resolves masked/verbatim card lines (either RTL layout)
        # and drops a "last-4" that is really a bank BIN prefix (two live
        # bakbot incidents, Jul 2026 — a dropped card is only a lost
        # tie-break, a bogus one falsely vetoes real payments).
        return normalize_card_last4(v)

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
