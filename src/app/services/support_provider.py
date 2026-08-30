"""Support-only LLM providers with a fail-closed monthly USD budget.

Ported from the live sales bot (`bakbot/support_provider.py`), with the
`requests` calls rewritten on aiohttp to match this app.

Deliberately SEPARATE from `sms_ai`: receipt reading is a money path, and a
support model experiment must never change how a payment is perceived. The
budget is a hard cutoff, not a warning — reservations make concurrent calls
cap-safe, so a burst can't overshoot while several answers are in flight.
"""
from __future__ import annotations

import asyncio
import json
import math
import os
import secrets
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

import aiohttp

from app.core.paths import data_path

BUDGET_FILE = data_path('support_budget.json')
_TIMEOUT = aiohttp.ClientTimeout(total=25, connect=5)
TEHRAN = ZoneInfo('Asia/Tehran')
MONTHLY_CAP_USD = float(os.environ.get('SUPPORT_AI_MONTHLY_USD', '3') or '3')
PRIMARY = (os.environ.get('SUPPORT_AI_PROVIDER') or 'gemini').strip().lower()
FALLBACK = (os.environ.get('SUPPORT_AI_FALLBACK') or 'openrouter_free').strip().lower()
MAX_OUTPUT_TOKENS = 700
RESERVATION_TTL_SEC = 15 * 60


def _clean(name: str, default: str = '') -> str:
    value = os.environ.get(name, default)
    return (value or default).split('#', 1)[0].strip()


GEMINI_KEYS = [v for v in (_clean('GEMINI_API_KEY'), _clean('GEMINI_API_KEY2')) if v]
DEEPSEEK_API_KEY = _clean('DEEPSEEK_API_KEY')
GROQ_API_KEY = _clean('GROQ_API_KEY')
OPENROUTER_API_KEY = _clean('OPENROUTER_API_KEY')

MODELS = {
    'gemini': _clean('SUPPORT_GEMINI_MODEL', 'gemini-3.5-flash-lite'),
    'deepseek': _clean('SUPPORT_DEEPSEEK_MODEL', 'deepseek-v4-flash'),
    'groq': _clean('SUPPORT_GROQ_MODEL', 'openai/gpt-oss-120b'),
    'openrouter_free': _clean('SUPPORT_OPENROUTER_MODEL', 'google/gemma-4-31b-it:free'),
}


def _prices(provider: str, default_model: str, input_default: str, output_default: str):
    """Known model defaults; an unknown override needs explicit prices.

    Stops a model-name edit from silently undercounting the hard cap.
    """
    raw_input, raw_output = (_clean(f'SUPPORT_{provider.upper()}_INPUT_USD'),
                             _clean(f'SUPPORT_{provider.upper()}_OUTPUT_USD'))
    if MODELS[provider] != default_model and not (raw_input and raw_output):
        return -1.0, -1.0
    return (float(raw_input or input_default), float(raw_output or output_default))


# Conservative standard paid prices per 1M tokens.
PRICES = {
    'gemini': _prices('gemini', 'gemini-3.5-flash-lite', '0.30', '2.50'),
    'deepseek': _prices('deepseek', 'deepseek-v4-flash', '0.14', '0.28'),
    'groq': _prices('groq', 'openai/gpt-oss-120b', '0.15', '0.60'),
    'openrouter_free': (0.0, 0.0),
}


class BudgetExceeded(RuntimeError):
    pass


class ProviderUnavailable(RuntimeError):
    pass


class BudgetLedger:
    """Micro-dollar ledger. Reservations make concurrent calls cap-safe."""

    def __init__(self, path=BUDGET_FILE, cap_usd=MONTHLY_CAP_USD, month_fn=None):
        self.path = path
        self.cap_micros = max(0, int(float(cap_usd) * 1_000_000))
        self.month_fn = month_fn or (lambda: datetime.now(TEHRAN).strftime('%Y-%m'))
        self._lock = threading.RLock()

    def _default(self):
        return {'month': self.month_fn(), 'spent_micros': 0, 'reservations': {}}

    def _load(self):
        try:
            with open(self.path, encoding='utf-8') as handle:
                data = json.load(handle)
            if not isinstance(data, dict):
                raise ValueError('bad ledger')
        except FileNotFoundError:
            data = self._default()
        except Exception as exc:
            # An unreadable ledger must never mean "spend freely".
            raise RuntimeError('support budget ledger unreadable') from exc
        if data.get('month') != self.month_fn():
            data = self._default()
        data.setdefault('spent_micros', 0)
        data.setdefault('reservations', {})
        cutoff = int(time.time()) - RESERVATION_TTL_SEC
        data['reservations'] = {k: v for k, v in data['reservations'].items()
                                if int(v.get('ts') or 0) >= cutoff}
        return data

    def _save(self, data):
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        tmp = f'{self.path}.tmp.{os.getpid()}.{threading.get_ident()}'
        try:
            with open(tmp, 'w', encoding='utf-8') as handle:
                json.dump(data, handle, ensure_ascii=False, indent=1)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(tmp, 0o600)
            os.replace(tmp, self.path)
            os.chmod(self.path, 0o600)
        finally:
            if os.path.exists(tmp):
                try:
                    os.unlink(tmp)
                except OSError:
                    pass

    def reserve(self, provider, model, input_tokens, max_output_tokens,
                input_price, output_price):
        if input_price < 0 or output_price < 0:
            raise ProviderUnavailable('unknown/invalid provider price')
        # $price per 1M tokens == `price` micro-dollars per token.
        micros = int(math.ceil(max(0, input_tokens) * input_price
                               + max(0, max_output_tokens) * output_price))
        call_id = secrets.token_hex(8)
        with self._lock:
            data = self._load()
            reserved = sum(int(v.get('micros') or 0) for v in data['reservations'].values())
            if data['spent_micros'] + reserved + micros > self.cap_micros:
                raise BudgetExceeded('monthly support AI budget reached')
            data['reservations'][call_id] = {'micros': micros, 'provider': provider,
                                             'model': model, 'ts': int(time.time())}
            self._save(data)
        return call_id, micros

    def reconcile(self, call_id, input_tokens=None, output_tokens=None,
                  input_price=0.0, output_price=0.0, success=True):
        with self._lock:
            data = self._load()
            reservation = data['reservations'].pop(call_id, None)
            if not reservation:
                return 0
            reserved = int(reservation.get('micros') or 0)
            if success and input_tokens is not None and output_tokens is not None:
                actual = int(math.ceil(max(0, input_tokens) * input_price
                                       + max(0, output_tokens) * output_price))
                # The reservation used prompt chars as a conservative token
                # upper bound plus the full max output; actual can't exceed it.
                actual = min(actual, reserved)
            elif success:
                actual = reserved  # no usage metadata: charge the full reserve
            else:
                actual = 0         # nothing completed
            data['spent_micros'] = int(data['spent_micros']) + actual
            self._save(data)
            return actual

    def status(self):
        with self._lock:
            data = self._load()
            reserved = sum(int(v.get('micros') or 0) for v in data['reservations'].values())
            return {'month': data['month'],
                    'spent_usd': data['spent_micros'] / 1_000_000,
                    'reserved_usd': reserved / 1_000_000,
                    'cap_usd': self.cap_micros / 1_000_000}


_ledger = BudgetLedger()


@dataclass
class ProviderResult:
    text: str
    input_tokens: int | None
    output_tokens: int | None
    model: str


def provider_configured(provider: str) -> bool:
    if provider not in PRICES or min(PRICES[provider]) < 0:
        return False
    if provider == 'gemini':
        return bool(GEMINI_KEYS)
    if provider == 'deepseek':
        return bool(DEEPSEEK_API_KEY)
    if provider == 'groq':
        return bool(GROQ_API_KEY)
    if provider == 'openrouter_free':
        return bool(OPENROUTER_API_KEY) and MODELS[provider].endswith(':free')
    return False


def available() -> bool:
    return any(provider_configured(p) for p in (PRIMARY, FALLBACK))


def configured_providers() -> list[str]:
    return [p for p in ('gemini', 'deepseek', 'groq', 'openrouter_free')
            if provider_configured(p)]


async def _gemini(prompt: str, want_json: bool = True) -> ProviderResult:
    model = MODELS['gemini']
    async with aiohttp.ClientSession(timeout=_TIMEOUT) as http:
        for key in GEMINI_KEYS:
            # Gemini 3.x wants thinkingLevel, not the legacy numeric
            # thinkingBudget; Google recommends leaving sampling at defaults.
            payload = {'contents': [{'parts': [{'text': prompt}]}],
                       'generationConfig': {
                           'thinkingConfig': {'thinkingLevel': 'MINIMAL'},
                           'maxOutputTokens': MAX_OUTPUT_TOKENS}}
            if want_json:
                payload['generationConfig']['responseMimeType'] = 'application/json'
            async with http.post(
                f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
                params={'key': key}, json=payload,
            ) as response:
                # A key can be revoked, restricted, or individually quota-limited;
                # try the next configured key without exposing any response body.
                if response.status in (401, 403, 404, 429):
                    continue
                if response.status != 200:
                    raise ProviderUnavailable(f'gemini HTTP {response.status}')
                body = await response.json(content_type=None)
            text = ''.join(part.get('text', '')
                           for cand in (body.get('candidates') or [])
                           for part in (cand.get('content', {}).get('parts') or [])).strip()
            usage = body.get('usageMetadata') or {}
            if text:
                return ProviderResult(text, usage.get('promptTokenCount'),
                                      usage.get('candidatesTokenCount'), model)
    raise ProviderUnavailable('gemini unavailable/quota')


async def _openai_compatible(provider: str, prompt: str, want_json: bool = True) -> ProviderResult:
    url, key = {
        'deepseek': ('https://api.deepseek.com/chat/completions', DEEPSEEK_API_KEY),
        'groq': ('https://api.groq.com/openai/v1/chat/completions', GROQ_API_KEY),
        'openrouter_free': ('https://openrouter.ai/api/v1/chat/completions', OPENROUTER_API_KEY),
    }[provider]
    payload = {'model': MODELS[provider],
               'messages': [{'role': 'user', 'content': prompt}],
               'max_tokens': MAX_OUTPUT_TOKENS, 'temperature': 0.1}
    if want_json:
        payload['response_format'] = {'type': 'json_object'}
    async with aiohttp.ClientSession(timeout=_TIMEOUT) as http:
        async with http.post(url, headers={'Authorization': f'Bearer {key}'},
                             json=payload) as response:
            if response.status != 200:
                raise ProviderUnavailable(f'{provider} HTTP {response.status}')
            body = await response.json(content_type=None)
    choices = body.get('choices') or []
    text = (choices[0].get('message', {}).get('content') or '').strip() if choices else ''
    usage = body.get('usage') or {}
    if not text:
        raise ProviderUnavailable(f'{provider} empty response')
    return ProviderResult(text, usage.get('prompt_tokens'),
                          usage.get('completion_tokens'), MODELS[provider])


async def ask_provider(provider: str, prompt: str, want_json: bool = True):
    provider = str(provider or '').lower()
    if not provider_configured(provider):
        return None, {'provider': provider, 'error': 'not_configured'}
    model = MODELS[provider]
    input_price, output_price = PRICES[provider]
    try:
        call_id, reserved = await asyncio.to_thread(
            _ledger.reserve, provider, model, max(1, len(prompt)),
            MAX_OUTPUT_TOKENS, input_price, output_price)
    except (BudgetExceeded, ProviderUnavailable) as exc:
        return None, {'provider': provider, 'model': model,
                      'error': type(exc).__name__, 'detail': str(exc)}
    try:
        result = await (_gemini(prompt, want_json) if provider == 'gemini'
                        else _openai_compatible(provider, prompt, want_json))
        actual = await asyncio.to_thread(
            _ledger.reconcile, call_id, result.input_tokens, result.output_tokens,
            input_price, output_price, True)
        return result.text, {'provider': provider, 'model': result.model,
                             'input_tokens': result.input_tokens,
                             'output_tokens': result.output_tokens,
                             'reserved_micros': reserved,
                             'cost_usd': actual / 1_000_000}
    except Exception as exc:
        await asyncio.to_thread(_ledger.reconcile, call_id, None, None, 0.0, 0.0, False)
        meta = {'provider': provider, 'model': model, 'error': type(exc).__name__}
        # Only our own controlled messages are safe to surface: a client
        # exception can carry the full Gemini URL, API key included.
        if isinstance(exc, ProviderUnavailable):
            meta['detail'] = str(exc)
        return None, meta


async def ask_with_meta(prompt: str, want_json: bool = True):
    """Return ``(text, safe metadata)`` — the metadata is admin-diagnostic."""
    started = time.perf_counter()
    seen: set[str] = set()
    last_meta: dict = {'error': 'no_provider'}
    for provider in (PRIMARY, FALLBACK):
        if provider in seen:
            continue
        seen.add(provider)
        text, meta = await ask_provider(provider, prompt, want_json=want_json)
        last_meta = meta
        if text:
            meta = dict(meta)
            meta['latency_ms'] = round((time.perf_counter() - started) * 1000)
            return text, meta
        if meta.get('error') == 'BudgetExceeded':
            break  # no fallback, paid or free, may bypass the hard cutoff
    last_meta = dict(last_meta)
    last_meta['latency_ms'] = round((time.perf_counter() - started) * 1000)
    return None, last_meta


async def ask(prompt: str, want_json: bool = True) -> str | None:
    """Support entry point. Support is text-only — no images, ever."""
    return (await ask_with_meta(prompt, want_json=want_json))[0]


def budget_status() -> dict:
    return _ledger.status()
