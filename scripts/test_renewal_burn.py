#!/usr/bin/env python3
"""End-to-end test of automatic renewal, using REAL traffic.

Proves the whole chain works without waiting for a customer to run out:

  1. makes a test account on the panel with a tiny limit (20 MB, not 1 GB -
     the panel fires at exhaustion regardless of size, so a small limit tests
     exactly the same thing in seconds);
  2. books a renewal on it, armed as PasarGuard's native next_plan, the same
     way a real paid booking is armed at approval;
  3. downloads junk through a real server config until the limit is gone;
  4. waits for the PANEL to fire the booked plan by itself;
  5. checks our side noticed: subscription marked renewed, history row written,
     and (with --dm) the user DM sent;
  6. deletes the test account and rows.

Traffic goes through a plain xray process listening on 127.0.0.1 only. It never
becomes a system route, so this server's own traffic and other sites are
untouched.

    .venv/bin/python scripts/test_renewal_burn.py
    .venv/bin/python scripts/test_renewal_burn.py --keep     # leave it behind
    .venv/bin/python scripts/test_renewal_burn.py --dm       # also send the DM

Requires TEST_PANEL_PREFIX in config/.env (so the account is identifiable and
scripts/cleanup_test_panel_users.py can remove it if this exits badly).
"""

import asyncio
import random
import string
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from _vless import parse_vless, write_config  # noqa: E402
from app.core.settings import TEST_PANEL_PREFIX  # noqa: E402
from app.services.pasarguard import pasarguard_api as api  # noqa: E402

XRAY = PROJECT_ROOT / "bin" / "xray"
SOCKS_PORT = 10808
BURN_LIMIT_BYTES = 20 * 1024 * 1024        # 20 MB
CHUNK_BYTES = 5 * 1024 * 1024              # per download request
BURN_URL = f"https://speed.cloudflare.com/__down?bytes={CHUNK_BYTES}"
FIRE_WAIT_SEC = 180                        # how long to wait for the panel
POLL_SEC = 10
BOOKED_TEMPLATE = "۲۰ گیگ | یکماه"         # what gets booked as the next plan

PASS, FAIL, INFO = "PASS", "FAIL", "    "
results: list[tuple[str, str]] = []


def step(status: str, msg: str) -> None:
    print(f"[{status}] {msg}" if status in (PASS, FAIL) else f"       {msg}")
    if status in (PASS, FAIL):
        results.append((status, msg))


def die(msg: str) -> None:
    print(f"ERROR: {msg}")
    sys.exit(1)


# --- panel helpers -------------------------------------------------------

async def set_data_limit(username: str, limit_bytes: int) -> bool:
    """add_user only speaks whole GB; the point of this test is a tiny limit."""
    return bool(await api.update_user(username, {"data_limit": int(limit_bytes)}))


async def used_bytes(username: str) -> int:
    await api.invalidate_user_info(username)
    info = await api.get_user_info(username)
    return int((info or {}).get("used_traffic") or 0)


async def pick_link(username: str) -> str:
    info = await api.get_user_info(username)
    token = (info or {}).get("subscription_url", "").rstrip("/").split("/")[-1]
    links = await api.get_subscription_links(token)
    if not links:
        die("panel returned no config links for the test account")
    # Prefer Turkey (unlimited on our side); fall back to whatever exists.
    turkey = [ln for ln in links if "%D8%AA%D8%B1%DA%A9" in ln]
    return (turkey or links)[0]


# --- traffic -------------------------------------------------------------

def burn(link: str, target_bytes: int) -> int:
    """Download through the config until target_bytes have gone over it."""
    if not XRAY.is_file():
        # bin/ is gitignored, so a fresh clone has to fetch this once.
        die(
            f"xray binary not found at {XRAY}\n"
            "       Get it with:\n"
            "         curl -sL -o /tmp/xray.zip https://github.com/XTLS/Xray-core/releases/latest/download/Xray-linux-64.zip\n"
            "         .venv/bin/python -c \"import zipfile;zipfile.ZipFile('/tmp/xray.zip').extract('xray','bin')\"\n"
            "         chmod +x bin/xray"
        )

    cfg_path = "/tmp/astro_renewal_test_xray.json"
    write_config(link, SOCKS_PORT, cfg_path)

    proc = subprocess.Popen(
        [str(XRAY), "-c", cfg_path],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    try:
        time.sleep(3)
        if proc.poll() is not None:
            die(f"xray failed to start: {(proc.stdout.read() or '')[:300]}")

        moved = 0
        deadline = time.time() + 180
        while moved < target_bytes and time.time() < deadline:
            r = subprocess.run(
                ["curl", "-s", "--socks5-hostname", f"127.0.0.1:{SOCKS_PORT}",
                 "-o", "/dev/null", "-w", "%{size_download}",
                 "--max-time", "45", BURN_URL],
                capture_output=True, text=True,
            )
            got = int(r.stdout.strip() or 0)
            if got <= 0:
                step(INFO, "a download returned nothing - retrying")
                time.sleep(2)
                continue
            moved += got
            print(f"       sent {moved / 1024 / 1024:.1f} MB", end="\r", flush=True)
        print()
        return moved
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


# --- the test ------------------------------------------------------------

async def run(keep: bool, send_dm: bool) -> None:
    prefix = (TEST_PANEL_PREFIX or "").strip()
    if not prefix:
        die("TEST_PANEL_PREFIX is not set in config/.env - refusing to create panel accounts")

    from app.database import crud
    from app.database.models import AsyncSessionLocal, Subscription, User
    from app.services.nextplan import arm_native_next_plan, reconcile_booked_sub
    from sqlalchemy import select

    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    username = f"{prefix}renew{suffix}"
    sub_id = None
    bot = None

    try:
        # 1. panel account with a tiny limit ------------------------------
        step(INFO, f"creating test account {username}")
        if not await api.add_user(username, data_limit_gb=1, expire_days=1):
            die("panel refused to create the test account")
        if not await set_data_limit(username, BURN_LIMIT_BYTES):
            die("could not set the 20 MB limit")
        info = await api.get_user_info(username)
        limit = int((info or {}).get("data_limit") or 0)
        step(PASS if limit == BURN_LIMIT_BYTES else FAIL,
             f"account created with a {limit / 1024 / 1024:.0f} MB limit")

        # 2. a booked renewal, armed on the panel -------------------------
        async with AsyncSessionLocal() as db:
            owner = (await db.execute(select(User).limit(1))).scalars().first()
            if not owner:
                die("no users in the database to attach the test subscription to")
            sub = Subscription(
                user_id=owner.id,
                marzban_username=username,
                plan_name="renewal burn test",
                price=0,
                status="active",
                created_at=datetime.utcnow(),
                renewal_paid=True,
                renewal_template=BOOKED_TEMPLATE,
                renewal_price=0,
                renewal_requested_at=datetime.utcnow(),
            )
            db.add(sub)
            await db.commit()
            await db.refresh(sub)
            sub_id = sub.id
            armed = await arm_native_next_plan(db, sub, source="renewal burn test")
        step(PASS if armed else FAIL, f"renewal booked and armed on the panel ({BOOKED_TEMPLATE})")
        if not armed:
            return

        info = await api.get_user_info(username)
        step(PASS if isinstance((info or {}).get("next_plan"), dict) else FAIL,
             "panel confirms a next plan is waiting")

        # 3. burn the 20 MB ----------------------------------------------
        link = await pick_link(username)
        step(INFO, f"pushing traffic through: {parse_vless(link)['tag'][:40]}")
        moved = burn(link, BURN_LIMIT_BYTES + CHUNK_BYTES)
        step(PASS if moved >= BURN_LIMIT_BYTES else FAIL,
             f"sent {moved / 1024 / 1024:.1f} MB through the server")

        # 4. wait for the PANEL to fire the booked plan --------------------
        step(INFO, f"waiting up to {FIRE_WAIT_SEC}s for the panel to fire it")
        fired = False
        waited = 0
        while waited < FIRE_WAIT_SEC:
            info = await api.get_user_info(username)
            if not isinstance((info or {}).get("next_plan"), dict):
                fired = True
                break
            await asyncio.sleep(POLL_SEC)
            waited += POLL_SEC
            print(f"       still waiting ({waited}s), used "
                  f"{await used_bytes(username) / 1024 / 1024:.1f} MB", end="\r", flush=True)
        print()
        step(PASS if fired else FAIL,
             f"panel fired the booked plan by itself (after ~{waited}s)" if fired
             else f"panel did NOT fire within {FIRE_WAIT_SEC}s")
        if not fired:
            return

        # 5. did our side notice? -----------------------------------------
        if send_dm:
            from aiogram import Bot
            from app.core.settings import BOT_TOKEN
            bot = Bot(token=BOT_TOKEN)

        async with AsyncSessionLocal() as db:
            sub = await db.get(Subscription, sub_id)
            outcome = await reconcile_booked_sub(db, sub, bot)
        step(PASS if outcome == "fired" else FAIL, f"our watchdog reported '{outcome}'")

        async with AsyncSessionLocal() as db:
            sub = await db.get(Subscription, sub_id)
            step(PASS if sub.renewal_applied else FAIL, "subscription marked as renewed")
            step(PASS if sub.renewal_armed_at is None else FAIL, "armed flag cleared")
            history = await crud.get_renewal_history(db, sub_id) \
                if hasattr(crud, "get_renewal_history") else None
        if history is not None:
            step(PASS if history else FAIL, f"renewal history row written ({len(history)})")

        info = await api.get_user_info(username)
        new_limit = int((info or {}).get("data_limit") or 0)
        step(PASS if new_limit > BURN_LIMIT_BYTES else FAIL,
             f"panel applied the new plan ({new_limit / 1024 ** 3:.0f} GB)")

    finally:
        if bot is not None:
            await bot.session.close()
        if keep:
            step(INFO, f"--keep: leaving {username} in place")
        else:
            step(INFO, "cleaning up")
            try:
                await api.delete_user(username)
            except Exception as exc:
                print(f"       could not delete panel account: {str(exc)[:80]}")
            if sub_id:
                from app.database.models import AsyncSessionLocal as S
                from app.database.models import Subscription as Sub
                from sqlalchemy import text
                async with S() as db:
                    # renewal_history rows point at the subscription - a passing
                    # run always writes one, so clear them first.
                    await db.execute(
                        text("DELETE FROM renewal_history WHERE subscription_id = :i"),
                        {"i": sub_id},
                    )
                    row = await db.get(Sub, sub_id)
                    if row:
                        await db.delete(row)
                    await db.commit()

        print()
        failed = [m for s, m in results if s == FAIL]
        passed = [m for s, m in results if s == PASS]
        print(f"{len(passed)} passed, {len(failed)} failed")
        if failed:
            for m in failed:
                print(f"   FAILED: {m}")
        sys.exit(1 if failed else 0)


async def _main() -> None:
    args = sys.argv[1:]
    try:
        await run(keep="--keep" in args, send_dm="--dm" in args)
    finally:
        try:
            session = await api._get_session()
            await session.close()
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(_main())
