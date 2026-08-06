#!/usr/bin/env python3
"""Save points for testing.

Take a snapshot before a test phase, go back to it when a bug ruins the run,
instead of resetting the whole database and redoing every phone step.

Usage:
    .venv/bin/python scripts/checkpoint.py save phase3
    .venv/bin/python scripts/checkpoint.py list
    .venv/bin/python scripts/checkpoint.py load phase3
    .venv/bin/python scripts/checkpoint.py rm phase3

A checkpoint holds the PostgreSQL database plus the JSON state files in
src/app/data/. Loading one also stops the bots, flushes Redis (so no stale
cache survives the rollback) and starts the bots again.
"""

import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from app.core.settings import DATABASE_URL  # noqa: E402

CHECKPOINT_DIR = PROJECT_ROOT / "checkpoints"
DATA_DIR = PROJECT_ROOT / "src" / "app" / "data"
SERVICES = ["astrobyte-userbot", "astrobyte-adminbot"]
NAME_RE = re.compile(r"^[A-Za-z0-9._-]{1,40}$")


# --- helpers -------------------------------------------------------------

def die(msg: str) -> None:
    print(f"ERROR: {msg}")
    sys.exit(1)


def parse_db_url(url: str) -> dict:
    clean = url.replace("postgresql+asyncpg://", "postgresql://")
    p = urlparse(clean)
    return {
        "host": p.hostname or "localhost",
        "port": p.port or 5432,
        "database": (p.path or "").lstrip("/"),
        "user": p.username,
        "password": unquote(p.password) if p.password else None,
    }


def pg_env(db: dict) -> dict:
    env = os.environ.copy()
    if db["password"]:
        env["PGPASSWORD"] = db["password"]
    return env


def run(cmd: list, env=None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, env=env, capture_output=True, text=True)


def services(action: str) -> None:
    """Stop or start the bots. Never fatal - a dev box may not have them."""
    result = run(["systemctl", action, *SERVICES])
    if result.returncode == 0:
        print(f"   bots {action}ped" if action == "stop" else "   bots started")
    else:
        print(f"   note: could not {action} bots ({result.stderr.strip()[:80]})")


def flush_redis() -> None:
    """Drop cached rows and bot conversation state left over from the future."""
    code = (
        "import asyncio\n"
        "from app.core.redis_config import get_redis_client\n"
        "async def m():\n"
        "    r = await get_redis_client()\n"
        "    await r.flushdb()\n"
        "asyncio.run(m())\n"
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    result = run([sys.executable, "-c", code], env=env)
    if result.returncode == 0:
        print("   redis flushed")
    else:
        print(f"   note: redis flush failed ({result.stderr.strip()[-120:]})")


def slot(name: str) -> Path:
    if not NAME_RE.match(name):
        die("name may only contain letters, numbers, dot, dash, underscore")
    return CHECKPOINT_DIR / name


# --- commands ------------------------------------------------------------

def cmd_save(name: str) -> None:
    db = parse_db_url(DATABASE_URL)
    if not db["database"]:
        die("DATABASE_URL has no database name")

    target = slot(name)
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)

    print(f"Saving checkpoint '{name}'")
    result = run(
        [
            "pg_dump",
            "-h", db["host"], "-p", str(db["port"]),
            "-U", db["user"], "-d", db["database"],
            "-F", "c", "-f", str(target / "db.dump"),
        ],
        env=pg_env(db),
    )
    if result.returncode != 0:
        shutil.rmtree(target)
        die(f"pg_dump failed: {result.stderr.strip()[-300:]}")
    print("   database saved")

    if DATA_DIR.is_dir():
        shutil.copytree(DATA_DIR, target / "data", dirs_exist_ok=True)
        print("   state files saved")

    (target / "STAMP").write_text(datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "\n")
    print(f"Done. Go back here with:  .venv/bin/python scripts/checkpoint.py load {name}")


def cmd_load(name: str) -> None:
    target = slot(name)
    dump = target / "db.dump"
    if not dump.is_file():
        die(f"no checkpoint named '{name}' (see: checkpoint.py list)")

    db = parse_db_url(DATABASE_URL)
    stamp = (target / "STAMP").read_text().strip() if (target / "STAMP").is_file() else "unknown"
    print(f"Going back to checkpoint '{name}' (saved {stamp})")
    print("This throws away everything that happened after it.")

    services("stop")

    result = run(
        [
            "pg_restore",
            "-h", db["host"], "-p", str(db["port"]),
            "-U", db["user"], "-d", db["database"],
            "--clean", "--if-exists", "--no-owner",
            str(dump),
        ],
        env=pg_env(db),
    )
    # pg_restore warns noisily about objects it could not drop; only a missing
    # binary or a hard failure with no tables restored is worth stopping for.
    if result.returncode != 0 and "pg_restore: error:" in result.stderr:
        hard = [ln for ln in result.stderr.splitlines() if ln.startswith("pg_restore: error:")]
        if hard:
            print("   restore reported errors:")
            for line in hard[:5]:
                print(f"     {line}")
    print("   database restored")

    saved_data = target / "data"
    if saved_data.is_dir():
        if DATA_DIR.is_dir():
            shutil.rmtree(DATA_DIR)
        shutil.copytree(saved_data, DATA_DIR)
        print("   state files restored")

    flush_redis()
    services("start")
    print("Done. You are back at the moment you saved.")


def cmd_list() -> None:
    if not CHECKPOINT_DIR.is_dir() or not any(CHECKPOINT_DIR.iterdir()):
        print("No checkpoints yet.")
        print("Make one with:  .venv/bin/python scripts/checkpoint.py save phase0")
        return
    print("Checkpoints:")
    for entry in sorted(CHECKPOINT_DIR.iterdir()):
        if not (entry / "db.dump").is_file():
            continue
        stamp_file = entry / "STAMP"
        stamp = stamp_file.read_text().strip() if stamp_file.is_file() else "unknown"
        size_mb = (entry / "db.dump").stat().st_size / (1024 * 1024)
        print(f"   {entry.name:<20} saved {stamp}   {size_mb:.1f} MB")


def cmd_rm(name: str) -> None:
    target = slot(name)
    if not target.is_dir():
        die(f"no checkpoint named '{name}'")
    shutil.rmtree(target)
    print(f"Deleted checkpoint '{name}'")


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help", "help"):
        print(__doc__)
        return
    action = args[0]
    if action == "list":
        cmd_list()
        return
    if len(args) < 2:
        die(f"'{action}' needs a name, for example: checkpoint.py {action} phase3")
    name = args[1]
    if action == "save":
        cmd_save(name)
    elif action == "load":
        cmd_load(name)
    elif action == "rm":
        cmd_rm(name)
    else:
        die(f"unknown command '{action}' (use save, load, list or rm)")


if __name__ == "__main__":
    main()
