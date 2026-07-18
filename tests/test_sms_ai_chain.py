"""Offline tests for the sms_ai provider chain (items 6-7, bakbot parity).

- Gemini: keys OUTER, models INNER; 429 -> next key (same model list),
  404 -> next model (same key); timeout / non-quota HTTP -> next model;
  thinkingBudget=0 sent, one retry without it on a 400 that mentions it.
- NVIDIA NIM: TEXT ONLY — never called when an image is present;
  400/404/410 and per-model timeouts advance to the next model.

All HTTP is monkeypatched through sms_ai._post.

Run: PYTHONPATH=src python tests/test_sms_ai_chain.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from app.services import sms_ai  # noqa: E402

CALLS: list = []


def _fake_post(script):
    """script: list of (status, body) popped per call; records (url, key, model,
    has_thinking) into CALLS."""
    async def _post(http, url, *, params=None, headers=None, payload=None):
        model = url.rsplit('/', 2)[-1].split(':')[0] if 'generativelanguage' in url else \
            (payload or {}).get('model', '')
        thinking = 'thinkingConfig' in ((payload or {}).get('generationConfig') or {})
        CALLS.append((('gemini' if 'generativelanguage' in url else 'nvidia'),
                      (params or {}).get('key'), model, thinking))
        if not script:
            raise AssertionError('unexpected extra HTTP call')
        status, body = script.pop(0)
        if status == 'timeout':
            raise TimeoutError('simulated timeout')
        return status, body
    return _post


GEMINI_OK = '{"candidates":[{"content":{"parts":[{"text":"{\\"ok\\":1}"}]}}]}'
NIM_OK = '{"choices":[{"message":{"content":"hint text"}}]}'


def _reset(keys, nvidia=''):
    CALLS.clear()
    sms_ai.GEMINI_KEYS[:] = keys
    sms_ai.NVIDIA_API_KEY = nvidia
    sms_ai.OPENROUTER_API_KEY = ''
    sms_ai.GEMINI_MODELS[:] = ['m1', 'm2']
    sms_ai.NVIDIA_MODELS[:] = ['n1', 'n2']


def test_429_next_key():
    """Key1 quota-dead -> the SAME model list is retried on key2 immediately."""
    _reset(['K1', 'K2'])
    sms_ai._post = _fake_post([(429, 'quota'), (200, GEMINI_OK)])
    out = asyncio.run(sms_ai._gemini('p'))
    assert out == '{"ok":1}', out
    assert [(c[1], c[2]) for c in CALLS] == [('K1', 'm1'), ('K2', 'm1')], CALLS


def test_404_next_model_same_key():
    """Model not on this account -> next model, key unchanged."""
    _reset(['K1'])
    sms_ai._post = _fake_post([(404, 'not found'), (200, GEMINI_OK)])
    out = asyncio.run(sms_ai._gemini('p'))
    assert out == '{"ok":1}'
    assert [(c[1], c[2]) for c in CALLS] == [('K1', 'm1'), ('K1', 'm2')], CALLS


def test_timeout_and_http_error_advance():
    """Timeouts and non-quota HTTP errors advance the chain, never abort it."""
    _reset(['K1', 'K2'])
    sms_ai._post = _fake_post([('timeout', ''), (500, 'oops'),      # key1 m1, m2
                               (200, GEMINI_OK)])                    # key2 m1
    out = asyncio.run(sms_ai._gemini('p'))
    assert out == '{"ok":1}'
    assert [(c[1], c[2]) for c in CALLS] == [('K1', 'm1'), ('K1', 'm2'), ('K2', 'm1')], CALLS


def test_thinking_knob_retry():
    """First call carries thinkingBudget=0; a 400 retries once without it."""
    _reset(['K1'])
    sms_ai._post = _fake_post([(400, 'Unknown field thinkingConfig'), (200, GEMINI_OK)])
    out = asyncio.run(sms_ai._gemini('p'))
    assert out == '{"ok":1}'
    assert CALLS[0][3] is True and CALLS[1][3] is False, CALLS
    assert CALLS[0][2] == CALLS[1][2] == 'm1'


def test_nvidia_text_only():
    """_ask with an IMAGE never touches NIM; text jobs fall back to it."""
    _reset([], nvidia='NVK')
    sms_ai._post = _fake_post([])  # any call would raise
    out = asyncio.run(sms_ai._ask('p', image_bytes=b'img'))
    assert out is None and CALLS == [], CALLS

    sms_ai._post = _fake_post([(200, NIM_OK)])
    out = asyncio.run(sms_ai._ask('p'))
    assert out == 'hint text'
    assert CALLS and CALLS[-1][0] == 'nvidia' and CALLS[-1][2] == 'n1'


def test_nvidia_model_advance():
    """410 (EOL) / 404 / 400 and timeouts advance to the next NIM model."""
    _reset([], nvidia='NVK')
    sms_ai._post = _fake_post([(410, 'gone'), (200, NIM_OK)])
    out = asyncio.run(sms_ai._nvidia('p'))
    assert out == 'hint text'
    assert [c[2] for c in CALLS] == ['n1', 'n2'], CALLS

    CALLS.clear()
    sms_ai._post = _fake_post([('timeout', ''), (200, NIM_OK)])
    out = asyncio.run(sms_ai._nvidia('p'))
    assert out == 'hint text'
    assert [c[2] for c in CALLS] == ['n1', 'n2'], CALLS


def test_receipt_prompt_mentions_rtl_card_layouts():
    """Item 8a (2026-07-18): the receipt prompt must spell out BOTH masked-card
    layouts, the bank-prefix rule, and the verbatim fallback."""
    p = sms_ai._RECEIPT_PROMPT
    assert '6219 86** **** 7804' in p, 'print-order example missing'
    assert '1781 43** **** 6104' in p, 'RTL-flipped example missing'
    assert 'NEVER return the bank prefix as the last-4' in p
    assert 'OPPOSITE end' in p
    assert 'VERBATIM' in p, 'unsure -> verbatim card line fallback missing'


def test_extract_handles_verbatim_card_line():
    """Item 8a caller side: when the model returns the whole card line
    verbatim (its 'unsure' fallback), extract_receipt_fields resolves the
    real last-4 next to the bank prefix — and drops a bare BIN misread."""
    import json as _json

    def _run(card_value):
        async def fake_ask(prompt, image_bytes=None, mime='image/jpeg', want_json=True):
            return _json.dumps({
                'success': True, 'amount': 850000, 'amount_unit': 'rial',
                'source_card_last4': card_value, 'dest_card_last4': None,
                'ref_numbers': ['123456'], 'time_text': None})
        orig_ask, orig_avail = sms_ai._ask, sms_ai.ai_available
        sms_ai._ask, sms_ai.ai_available = fake_ask, lambda: True
        try:
            return asyncio.run(sms_ai.extract_receipt_fields(b'img'))
        finally:
            sms_ai._ask, sms_ai.ai_available = orig_ask, orig_avail

    # Verbatim print-order line -> last visible group.
    assert _run('6104 33** **** 2336')['source_card_last4'] == '2336'
    # Verbatim RTL-FLIPPED line -> the group OPPOSITE the bank prefix.
    assert _run('1781 43** **** 6104')['source_card_last4'] == '1781'
    # Bare BIN prefix returned as "last-4" -> dropped (None), refs survive.
    got = _run('6104')
    assert got['source_card_last4'] is None and got['ref_numbers'] == ['123456']
    # Clean last-4 passes through untouched.
    assert _run('7804')['source_card_last4'] == '7804'


def test_model_list_2026():
    """Default model list matches the 2026 account reality (order matters)."""
    import importlib
    saved = dict(os.environ)
    for k in ('SMS_AI_MODEL', 'NVIDIA_MODEL'):
        os.environ.pop(k, None)
    try:
        mod = importlib.reload(sms_ai)
        assert mod.GEMINI_MODELS == ['gemini-2.5-flash', 'gemini-3-flash-preview',
                                     'gemini-3.1-flash-lite', 'gemini-2.0-flash'], mod.GEMINI_MODELS
        assert mod.NVIDIA_MODELS == ['nvidia/nvidia-nemotron-nano-9b-v2',
                                     'qwen/qwen3-next-80b-a3b-instruct'], mod.NVIDIA_MODELS
    finally:
        os.environ.clear()
        os.environ.update(saved)
        importlib.reload(sms_ai)


if __name__ == '__main__':
    fns = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for fn in fns:
        fn()
        print('PASS', fn.__name__)
    print(f'\nAll {len(fns)} sms_ai chain tests passed.')
