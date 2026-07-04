"""Client-side error intake.

The Mini App posts JS errors here so real-device failures (Android WebView
quirks, auth issues, …) are visible server-side instead of being debugged
via screenshots. Events land in logs/client_errors.jsonl, one JSON per line.

Deliberately auth-free: errors matter most exactly when auth is broken.
Abuse is bounded by per-IP rate limiting, payload caps, and log rotation.
"""

import json
import logging
import time
from pathlib import Path

from aiohttp import web

_LOG_DIR = Path(__file__).resolve().parents[2] / "data"
_LOG_FILE = _LOG_DIR / "client_errors.jsonl"
_MAX_BODY = 32 * 1024          # request cap
_MAX_EVENTS = 10               # events per request
_MAX_FIELD = 2000              # chars per field
_MAX_LOG_BYTES = 5 * 1024 * 1024  # rotate at 5MB (keep one .1 backup)

_BUCKET: dict[str, list[float]] = {}
_BUCKET_MAX = 30               # requests / 5 min / IP
_BUCKET_WINDOW = 300.0


def _rate_ok(ip: str) -> bool:
    now = time.monotonic()
    hits = [t for t in _BUCKET.get(ip, []) if now - t < _BUCKET_WINDOW]
    if len(hits) >= _BUCKET_MAX:
        _BUCKET[ip] = hits
        return False
    hits.append(now)
    _BUCKET[ip] = hits
    if len(_BUCKET) > 2000:  # keep the table bounded
        _BUCKET.clear()
    return True


def _clip(value, limit=_MAX_FIELD) -> str:
    return str(value)[:limit] if value is not None else ""


def _rotate_if_needed() -> None:
    try:
        if _LOG_FILE.exists() and _LOG_FILE.stat().st_size > _MAX_LOG_BYTES:
            backup = _LOG_FILE.with_suffix(".jsonl.1")
            if backup.exists():
                backup.unlink()
            _LOG_FILE.rename(backup)
    except OSError:
        pass


async def handle_client_log(request: web.Request) -> web.Response:
    ip = request.headers.get("X-Forwarded-For", request.remote or "?").split(",")[0].strip()
    if not _rate_ok(ip):
        return web.json_response({"ok": False}, status=429)
    if (request.content_length or 0) > _MAX_BODY:
        return web.json_response({"ok": False}, status=413)
    try:
        payload = await request.json()
    except Exception:
        return web.json_response({"ok": False}, status=400)

    events = payload.get("events") if isinstance(payload, dict) else None
    if not isinstance(events, list) or not events:
        return web.json_response({"ok": False}, status=400)

    received_at = int(time.time())
    lines = []
    for ev in events[:_MAX_EVENTS]:
        if not isinstance(ev, dict):
            continue
        lines.append(json.dumps({
            "at": received_at,
            "ip": ip,
            "kind": _clip(ev.get("kind"), 32) or "error",
            "msg": _clip(ev.get("msg")),
            "stack": _clip(ev.get("stack"), 4000),
            "page": _clip(ev.get("page"), 300),
            "ua": _clip(ev.get("ua"), 300),
            "platform": _clip(ev.get("platform"), 32),
            "lang": _clip(ev.get("lang"), 8),
            "extra": _clip(ev.get("extra"), 1000),
        }, ensure_ascii=False))

    if lines:
        try:
            _LOG_DIR.mkdir(parents=True, exist_ok=True)
            _rotate_if_needed()
            with open(_LOG_FILE, "a", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
        except OSError as e:
            logging.warning("client-log write failed: %s", e)

    return web.json_response({"ok": True})
