#!/usr/bin/env python3
"""Delete leftover TEST accounts from the PasarGuard panel.

Rolling back the database with scripts/checkpoint.py does not roll back the
VPN panel, so test accounts pile up there. This removes them.

    .venv/bin/python scripts/cleanup_test_panel_users.py            # list only
    .venv/bin/python scripts/cleanup_test_panel_users.py --delete   # actually delete

SAFETY — the panel is shared with thousands of REAL customer accounts.
This script:
  * refuses to run unless TEST_PANEL_PREFIX is set in config/.env;
  * refuses a prefix shorter than 2 characters;
  * only ever considers names that START WITH that prefix;
  * re-checks the prefix on every single name immediately before deleting;
  * lists what it found and does nothing at all without --delete;
  * skips any name that exists in our own database as a real subscription
    unless that subscription is also prefixed.
"""

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from app.core.settings import TEST_PANEL_PREFIX  # noqa: E402
from app.services.pasarguard import pasarguard_api  # noqa: E402

PAGE_SIZE = 200
MAX_PAGES = 200


def die(msg: str) -> None:
    print(f"ERROR: {msg}")
    sys.exit(1)


async def fetch_panel_usernames(prefix: str) -> list[str]:
    """Ask the panel for prefixed names only, then filter again locally.

    ``search`` matches anywhere in the name, so a real account that merely
    CONTAINS the prefix can come back — the startswith() check below is what
    actually decides, and it runs again before every delete."""
    session = await pasarguard_api._get_session()
    headers = await pasarguard_api._get_headers()
    base = pasarguard_api.base_url.rstrip("/")

    names: list[str] = []
    offset = 0
    for _ in range(MAX_PAGES):
        url = f"{base}/api/users?offset={offset}&limit={PAGE_SIZE}&search={prefix}"
        async with session.get(url, headers=headers) as resp:
            if resp.status == 401:
                await pasarguard_api._login()
                headers = await pasarguard_api._get_headers()
                continue
            if resp.status != 200:
                die(f"panel returned {resp.status} listing users: {(await resp.text())[:200]}")
            payload = await resp.json()

        batch = payload.get("users") if isinstance(payload, dict) else payload
        if not batch:
            break
        for user in batch:
            name = (user or {}).get("username") or ""
            if name.startswith(prefix):
                names.append(name)
        if len(batch) < PAGE_SIZE:
            break
        offset += PAGE_SIZE

    return names


async def real_subscription_names() -> set[str]:
    """Panel usernames our database considers live subscriptions."""
    from app.database.models import AsyncSessionLocal, Subscription
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(Subscription.marzban_username))).scalars().all()
    return {r for r in rows if r}


async def main() -> None:
    prefix = (TEST_PANEL_PREFIX or "").strip()
    if not prefix:
        die(
            "TEST_PANEL_PREFIX is not set — refusing to run.\n"
            "       This is the guard that stops this script touching real accounts.\n"
            "       Set TEST_PANEL_PREFIX=qa in config/.env while testing."
        )
    if len(prefix) < 2:
        die(f"TEST_PANEL_PREFIX '{prefix}' is too short — use at least 2 characters")

    do_delete = "--delete" in sys.argv[1:]

    print(f"Looking for panel accounts starting with '{prefix}'")
    found = await fetch_panel_usernames(prefix)

    if not found:
        print("Nothing to clean up.")
        return

    live = await real_subscription_names()
    # A prefixed name still present in our DB is a test sub we have not rolled
    # back yet — deleting it on the panel would strand the row. Skip it.
    stale = [n for n in found if n not in live]
    skipped = [n for n in found if n in live]

    print(f"Found {len(found)} test account(s) on the panel:")
    for name in found:
        mark = "  in use (skipping)" if name in live else ""
        print(f"   {name}{mark}")

    if skipped:
        print(f"\n{len(skipped)} still linked to a subscription row — left alone.")

    if not stale:
        print("\nNothing safe to delete.")
        return

    if not do_delete:
        print(f"\n{len(stale)} would be deleted. Nothing was changed.")
        print("Run again with --delete to remove them.")
        return

    print(f"\nDeleting {len(stale)} account(s)...")
    removed = 0
    for name in stale:
        # Final guard: re-check the prefix on the exact string being deleted.
        if not name.startswith(prefix):
            print(f"   REFUSED (no prefix): {name}")
            continue
        try:
            ok = await pasarguard_api.delete_user(name)
        except Exception as exc:
            print(f"   failed {name}: {str(exc)[:100]}")
            continue
        if ok:
            removed += 1
            print(f"   deleted {name}")
        else:
            print(f"   could not delete {name}")

    print(f"\nDone. {removed} of {len(stale)} removed.")


async def _run() -> None:
    try:
        await main()
    finally:
        try:
            session = await pasarguard_api._get_session()
            await session.close()
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(_run())
