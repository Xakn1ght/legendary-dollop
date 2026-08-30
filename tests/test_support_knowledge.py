#!/usr/bin/env python3
"""Support knowledge store: validation, lifecycle, conflicts, safe writes.

Ported from the live sales bot's test_support_knowledge.py.

    PYTHONPATH=src .venv/bin/python tests/test_support_knowledge.py
"""
import json
import os
import stat
import tempfile
import threading
import unittest
from unittest import mock

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from app.services import support_knowledge as sk  # noqa: E402


class Clock:
    def __init__(self, value=1_800_000_000):
        self.value = value

    def __call__(self):
        return self.value


class KnowledgeStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, 'knowledge.json')
        self.clock = Clock()
        self.events = []
        self.store = sk.KnowledgeStore(
            self.path, now_fn=self.clock,
            audit=lambda event, **fields: self.events.append((event, fields)))

    def tearDown(self):
        self.tmp.cleanup()

    def draft(self, **overrides):
        data = dict(kind='incident', title='اختلال همراه اول',
                    body='همراه اول تا ساعت ده اختلال دارد.',
                    scope={'operator': ['همراه اول']},
                    expires_ts=self.clock.value + 3600, creator='1')
        data.update(overrides)
        return self.store.create_draft(**data)

    def test_missing_file_and_private_atomic_write(self):
        self.assertFalse(os.path.exists(self.path))
        self.draft()
        self.assertTrue(os.path.exists(self.path))
        self.assertEqual(stat.S_IMODE(os.stat(self.path).st_mode), 0o600)
        self.assertFalse([p for p in os.listdir(self.tmp.name) if '.tmp.' in p])

    def test_draft_never_retrieved_then_approve_active(self):
        record = self.draft()
        self.assertEqual([], self.store.active_for('همراه اول وصل نمیشه'))
        approved = self.store.approve(record['id'], actor='1',
                                      expected_version=record['version'])
        self.assertEqual('active', approved['status'])
        self.assertEqual(record['id'], self.store.active_for('همراه اول وصل نمیشه')[0]['id'])

    def test_scheduled_activation_and_expiry_boundaries(self):
        record = self.draft(start_ts=self.clock.value + 100,
                            expires_ts=self.clock.value + 200)
        self.store.approve(record['id'], actor='1')
        self.assertEqual('scheduled', self.store.get(record['id'])['effective_status'])
        self.clock.value += 100
        self.assertEqual('active', self.store.get(record['id'])['effective_status'])
        self.clock.value += 100
        self.assertEqual('expired', self.store.get(record['id'])['effective_status'])
        self.assertEqual([], self.store.active_for('همراه اول'))

    def test_temporary_requires_expiry_but_permanent_does_not(self):
        incident = self.draft(expires_ts=None)
        with self.assertRaises(ValueError):
            self.store.approve(incident['id'], actor='1')
        faq = self.store.create_draft(kind='faq', title='برنامه آیفون',
                                      body='از Karing استفاده کنید.', creator='1')
        self.assertEqual('active', self.store.approve(faq['id'], actor='1')['status'])

    def test_stale_edit_and_idempotent_create(self):
        first = self.store.create_draft(kind='faq', title='الف', body='ب',
                                        idempotency_key='update-1')
        same = self.store.create_draft(kind='faq', title='دیگر', body='دیگر',
                                       idempotency_key='update-1')
        self.assertEqual(first['id'], same['id'])
        edited = self.store.update_draft(first['id'], title='جدید',
                                         expected_version=first['version'])
        with self.assertRaises(ValueError):
            self.store.update_draft(first['id'], title='کهنه',
                                    expected_version=first['version'])
        self.assertEqual('جدید', edited['title'])

    def test_resolve_reject_delete(self):
        active = self.draft()
        self.store.approve(active['id'], actor='1')
        self.assertEqual('resolved', self.store.resolve(active['id'], actor='1')['status'])
        draft = self.draft(title='دوم')
        self.assertEqual('rejected', self.store.reject(draft['id'], actor='1')['status'])
        self.assertTrue(self.store.delete(draft['id'], actor='1'))
        self.assertIsNone(self.store.get(draft['id']))

    def test_scope_relevance_and_irrelevant_filter(self):
        mci = self.draft()
        irancell = self.draft(title='اختلال ایرانسل', body='ایرانسل مشکل دارد.',
                              scope={'operator': ['ایرانسل']})
        self.store.approve(mci['id'], actor='1')
        self.store.approve(irancell['id'], actor='1')
        picked = self.store.active_for('اینترنت ایرانسل من وصل نمیشه')
        self.assertEqual(irancell['id'], picked[0]['id'])
        self.assertEqual([], self.store.active_for('قیمت خرید گروهی چنده'))

    def test_equal_priority_conflict_detection(self):
        a = self.draft()
        b = self.draft(body='همراه اول هیچ مشکلی ندارد.')
        self.store.approve(a['id'], actor='1')
        self.store.approve(b['id'], actor='1')
        records = self.store.active_for('همراه اول مشکل دارد', limit=10)
        self.assertEqual(1, len(sk.find_conflicts(records)))

    def test_corruption_keeps_last_good_and_blocks_writes(self):
        record = self.draft()
        with open(self.path, 'w', encoding='utf-8') as handle:
            handle.write('{broken')
        self.assertFalse(self.store.reload())
        self.assertTrue(self.store.write_blocked)
        self.assertEqual(record['id'], self.store.get(record['id'])['id'])
        with self.assertRaises(RuntimeError):
            self.draft(title='نباید نوشته شود')

    def test_failed_replace_leaves_no_partial_target(self):
        self.draft()
        with open(self.path, encoding='utf-8') as handle:
            before = handle.read()
        with mock.patch('app.services.support_knowledge.os.replace', side_effect=OSError('boom')):
            with self.assertRaises(OSError):
                self.draft(title='شکست')
        with open(self.path, encoding='utf-8') as handle:
            self.assertEqual(before, handle.read())
        self.assertFalse([p for p in os.listdir(self.tmp.name) if '.tmp.' in p])

    def test_concurrent_idempotency(self):
        records = []
        errors = []

        def worker():
            try:
                records.append(self.store.create_draft(
                    kind='faq', title='تست', body='پاسخ', idempotency_key='same'))
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual([], errors)
        self.assertEqual(1, len({r['id'] for r in records}))
        self.assertEqual(1, len(self.store.list_records()))


if __name__ == '__main__':
    unittest.main(verbosity=2)
