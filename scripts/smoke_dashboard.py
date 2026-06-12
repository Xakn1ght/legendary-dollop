#!/usr/bin/env python3
"""Dashboard API smoke tester.

Forges valid Telegram WebApp initData (HMAC per Telegram spec, signed with the
real BOT_TOKEN from config/.env) so dashboard endpoints can be exercised
end-to-end from the CLI without a phone.

Usage:
    .venv/bin/python scripts/smoke_dashboard.py [chat_id] [path ...]
    # default: runs the standard probe set against http://localhost:8585
"""
import hashlib
import hmac
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://localhost:8585"


def _bot_token() -> str:
    for line in (ROOT / "config" / ".env").read_text().splitlines():
        if line.startswith("BOT_TOKEN="):
            return line.split("=", 1)[1].strip().strip('"')
    raise SystemExit("BOT_TOKEN not found in config/.env")


def make_init_data(chat_id: int, first_name: str = "Smoke", username: str = "smoketest") -> str:
    user = json.dumps(
        {"id": chat_id, "first_name": first_name, "username": username, "language_code": "fa"},
        separators=(",", ":"),
    )
    fields = {"auth_date": str(int(time.time())), "query_id": "AAE-smoke", "user": user}
    check_string = "\n".join(f"{k}={fields[k]}" for k in sorted(fields))
    secret = hmac.new(b"WebAppData", _bot_token().encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    return urllib.parse.urlencode(fields)


def call(chat_id: int, path: str, method: str = "GET", body: dict | None = None):
    req = urllib.request.Request(
        BASE + path,
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={
            "X-Telegram-Init-Data": make_init_data(chat_id),
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode() or "{}")
        except Exception:
            return e.code, {}


def main():
    chat_id = int(sys.argv[1]) if len(sys.argv) > 1 else 999000111
    paths = sys.argv[2:]
    if paths:
        for p in paths:
            print(p, "→", call(chat_id, p))
        return

    print(f"chat_id={chat_id}")
    for label, path in [
        ("preferences GET", "/api/dashboard/preferences"),
        ("plans", "/api/dashboard/purchase/plans"),
        ("custom-quote 52GB", "/api/dashboard/purchase/custom-quote?gb=52"),
        ("referrals", "/api/dashboard/referrals"),
        ("rewards summary", "/api/dashboard/rewards"),
    ]:
        status, data = call(chat_id, path)
        brief = json.dumps(data, ensure_ascii=False)
        print(f"{label:24s} {status} {brief[:160]}")

    status, data = call(chat_id, "/api/dashboard/preferences", "POST", {"accent": "cyan", "theme": "light"})
    print(f"{'preferences POST accent':24s} {status} {json.dumps(data, ensure_ascii=False)[:160]}")
    status, data = call(chat_id, "/api/dashboard/preferences")
    print(f"{'preferences re-GET':24s} {status} {json.dumps(data, ensure_ascii=False)[:160]}")


if __name__ == "__main__":
    main()
