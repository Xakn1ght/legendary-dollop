#!/usr/bin/env python3
"""Support LLM provider: hard budget cap, safe errors, key rotation.

Ported from the live sales bot's test_support_provider.py, with the HTTP
mocks moved from `requests` to aiohttp.

    PYTHONPATH=src .venv/bin/python tests/test_support_provider.py
"""
import asyncio
import json
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from app.services import support_provider as sp  # noqa: E402


class _FakeResponse:
    def __init__(self, status, body=None):
        self.status = status
        self._body = body or {}

    async def json(self, content_type=None):
        return self._body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


class _FakeSession:
    """Stands in for aiohttp.ClientSession; records every post() call."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self._responses.pop(0)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


def _patch_session(*responses):
    session = _FakeSession(responses)
    return mock.patch.object(sp.aiohttp, 'ClientSession', lambda *a, **kw: session), session


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.month = ['2026-08']
        self.path = os.path.join(self.tmp.name, 'budget.json')
        self.ledger = sp.BudgetLedger(self.path, cap_usd=3, month_fn=lambda: self.month[0])

    def tearDown(self):
        self.tmp.cleanup()

    def test_reserve_reconcile_and_private_file(self):
        call, reserved = self.ledger.reserve('x', 'm', 1000, 100, .3, 2.5)
        self.assertGreater(reserved, 0)
        self.assertGreater(self.ledger.reconcile(call, 500, 50, .3, 2.5, success=True), 0)
        status = self.ledger.status()
        self.assertGreater(status['spent_usd'], 0)
        self.assertEqual(0, status['reserved_usd'])
        self.assertEqual(0o600, os.stat(self.path).st_mode & 0o777)

    def test_failure_releases_reservation(self):
        call, _ = self.ledger.reserve('x', 'm', 1000, 100, .3, 2.5)
        self.ledger.reconcile(call, success=False)
        self.assertEqual(0, self.ledger.status()['spent_usd'])
        self.assertEqual(0, self.ledger.status()['reserved_usd'])

    def test_concurrent_reservations_never_cross_cap(self):
        accepted, rejected = [], []

        def worker():
            try:
                accepted.append(self.ledger.reserve('x', 'm', 400_000, 0, 1, 0))
            except sp.BudgetExceeded:
                rejected.append(True)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(7, len(accepted))
        self.assertEqual(3, len(rejected))
        self.assertLessEqual(self.ledger.status()['reserved_usd'], 3)

    def test_month_rollover_resets_new_month(self):
        call, _ = self.ledger.reserve('x', 'm', 1_000_000, 0, 1, 0)
        self.ledger.reconcile(call, 1_000_000, 0, 1, 0, success=True)
        self.assertEqual(1, self.ledger.status()['spent_usd'])
        self.month[0] = '2026-09'
        self.assertEqual(0, self.ledger.status()['spent_usd'])

    def test_corrupt_ledger_fails_closed(self):
        Path(self.path).write_text('{bad', encoding='utf-8')
        with self.assertRaises(RuntimeError):
            self.ledger.reserve('x', 'm', 1, 1, 1, 1)

    def test_stale_reservation_is_released_after_restart(self):
        Path(self.path).write_text(json.dumps(
            {'month': self.month[0], 'spent_micros': 0,
             'reservations': {'dead': {'micros': 3_000_000, 'ts': 1}}}), encoding='utf-8')
        call, _ = self.ledger.reserve('x', 'm', 1, 0, 1, 0)
        self.assertTrue(call)


class ProviderTests(unittest.TestCase):
    def test_detailed_call_reports_safe_cost_and_latency(self):
        meta_in = {'provider': 'gemini', 'model': 'test-model',
                   'input_tokens': 12, 'output_tokens': 3, 'cost_usd': 0.000011}

        async def fake_ask_provider(*a, **kw):
            return '{}', meta_in

        with mock.patch.object(sp, 'ask_provider', fake_ask_provider):
            text, meta = asyncio.run(sp.ask_with_meta('hello'))
        self.assertEqual('{}', text)
        self.assertEqual('gemini', meta['provider'])
        self.assertEqual(0.000011, meta['cost_usd'])
        self.assertIsInstance(meta['latency_ms'], int)

    def test_unknown_or_unconfigured_provider_never_calls_network(self):
        patch, session = _patch_session()
        with patch:
            text, meta = asyncio.run(sp.ask_provider('not-real', 'hello'))
        self.assertIsNone(text)
        self.assertEqual('not_configured', meta['error'])
        self.assertEqual([], session.calls)

    def test_unknown_model_without_explicit_prices_is_fail_closed(self):
        patch, session = _patch_session()
        with mock.patch.dict(sp.MODELS, {'gemini': 'future-unknown-model'}), \
                mock.patch.dict(sp.PRICES, {'gemini': (-1.0, -1.0)}), \
                mock.patch.object(sp, 'GEMINI_KEYS', ['configured']), patch:
            text, meta = asyncio.run(sp.ask_provider('gemini', 'hello'))
        self.assertIsNone(text)
        self.assertEqual('not_configured', meta['error'])
        self.assertEqual([], session.calls)

    def test_gemini_usage_is_returned_and_key_never_enters_the_body(self):
        ok = _FakeResponse(200, {
            'candidates': [{'content': {'parts': [{'text': '{"reply":"ok"}'}]}}],
            'usageMetadata': {'promptTokenCount': 12, 'candidatesTokenCount': 3}})
        patch, session = _patch_session(ok)
        with mock.patch.object(sp, 'GEMINI_KEYS', ['secret-test-key']), patch:
            result = asyncio.run(sp._gemini('prompt'))
        self.assertEqual(12, result.input_tokens)
        payload = session.calls[0][1]['json']
        self.assertNotIn('secret-test-key', json.dumps(payload))
        config = payload['generationConfig']
        self.assertEqual('MINIMAL', config['thinkingConfig']['thinkingLevel'])
        self.assertNotIn('thinkingBudget', config['thinkingConfig'])
        self.assertNotIn('temperature', config)

    def test_gemini_rotates_restricted_key(self):
        ok = _FakeResponse(200, {'candidates': [{'content': {'parts': [{'text': '{}'}]}}],
                                 'usageMetadata': {}})
        patch, session = _patch_session(_FakeResponse(403), ok)
        with mock.patch.object(sp, 'GEMINI_KEYS', ['first-secret', 'second-secret']), patch:
            result = asyncio.run(sp._gemini('prompt'))
        self.assertEqual('{}', result.text)
        self.assertEqual(2, len(session.calls))

    def test_provider_error_detail_never_leaks_the_url(self):
        patch, _ = _patch_session(_FakeResponse(500))
        with mock.patch.object(sp, 'GEMINI_KEYS', ['secret-test-key']), patch:
            text, meta = asyncio.run(sp.ask_provider('gemini', 'hello'))
        self.assertIsNone(text)
        self.assertNotIn('secret-test-key', json.dumps(meta))
        self.assertEqual('gemini HTTP 500', meta.get('detail'))

    def test_budget_exceeded_stops_the_fallback_too(self):
        seen = []

        async def fake_ask_provider(provider, prompt, want_json=True):
            seen.append(provider)
            return None, {'provider': provider, 'error': 'BudgetExceeded'}

        with mock.patch.object(sp, 'ask_provider', fake_ask_provider):
            text, meta = asyncio.run(sp.ask_with_meta('hello'))
        self.assertIsNone(text)
        self.assertEqual([sp.PRIMARY], seen)


if __name__ == '__main__':
    unittest.main(verbosity=2)
