"""with_next_plan_preserved — the PasarGuard PUT-wipes-next_plan guard.

Live probe (2026-07-12) proved a PUT /api/user/{username} that omits
``next_plan`` silently deletes an armed next-plan. Every modify payload must
echo the armed object back verbatim. These tests pin the guard's contract:
echo when armed, respect an explicit key (None = deliberate clear), and
fail-open when the pre-read is unavailable.
"""

import asyncio
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from app.services.pasarguard import PasarGuardAPI  # noqa: E402

ARMED = {
    "user_template_id": None,
    "data_limit": 42949672960,
    "expire": 3024000,
    "add_remaining_traffic": False,
}


def run(coro):
    return asyncio.run(coro)


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.api = PasarGuardAPI.__new__(PasarGuardAPI)  # no HTTP/login init

    def _stub_info(self, result=None, raises=False):
        async def _get_user_info(username):
            if raises:
                raise RuntimeError("panel down")
            return result
        self.api.get_user_info = _get_user_info

    def test_echoes_armed_plan(self):
        self._stub_info({"username": "u", "next_plan": dict(ARMED)})
        out = run(self.api.with_next_plan_preserved("u", {"status": "active"}))
        self.assertEqual(out["next_plan"], ARMED)
        self.assertEqual(out["status"], "active")

    def test_original_payload_not_mutated(self):
        self._stub_info({"next_plan": dict(ARMED)})
        payload = {"data_limit": 1}
        run(self.api.with_next_plan_preserved("u", payload))
        self.assertNotIn("next_plan", payload)

    def test_no_armed_plan_leaves_payload_alone(self):
        self._stub_info({"username": "u", "next_plan": None})
        out = run(self.api.with_next_plan_preserved("u", {"status": "active"}))
        self.assertNotIn("next_plan", out)

    def test_explicit_key_wins_even_none(self):
        self._stub_info({"next_plan": dict(ARMED)})
        out = run(self.api.with_next_plan_preserved("u", {"next_plan": None}))
        self.assertIsNone(out["next_plan"])  # deliberate clear passes through

    def test_fail_open_on_read_error(self):
        self._stub_info(raises=True)
        out = run(self.api.with_next_plan_preserved("u", {"status": "active"}))
        self.assertEqual(out, {"status": "active"})

    def test_fail_open_on_missing_user(self):
        self._stub_info(None)
        out = run(self.api.with_next_plan_preserved("u", {"status": "active"}))
        self.assertEqual(out, {"status": "active"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
