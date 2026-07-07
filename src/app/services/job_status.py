"""In-process registry of background-job runs, surfaced by the admin health
endpoint. Persisted to a small JSON file so the panel still shows the last
known state right after a restart."""
import json
import threading
import time

from app.core.paths import data_path

_FILE = data_path("job_status.json")
_lock = threading.Lock()
_runs: dict[str, dict] = {}
_loaded = False


def _load_once() -> None:
    global _loaded
    if _loaded:
        return
    _loaded = True
    try:
        with open(_FILE, encoding="utf-8") as f:
            saved = json.load(f)
        if isinstance(saved, dict):
            _runs.update(saved)
    except Exception:
        pass


def record_job_run(name: str, success: bool, duration: float | None = None) -> None:
    with _lock:
        _load_once()
        _runs[name] = {
            "last_run_at": int(time.time()),
            "ok": bool(success),
            "duration_ms": int((duration or 0) * 1000),
        }
        try:
            with open(_FILE, "w", encoding="utf-8") as f:
                json.dump(_runs, f)
        except Exception:
            pass


def get_job_statuses() -> dict[str, dict]:
    with _lock:
        _load_once()
        return dict(_runs)
