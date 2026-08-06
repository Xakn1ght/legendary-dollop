"""Last-seen-connected tracker for panel nodes.

PasarGuard's node object carries no "last seen" — a DISABLED/disconnected node
tells you nothing about when it was last alive (audit finding: the Servers page
showed only an IP for those). So we stamp it ourselves: every consumer that
already holds a fresh node list (the 5-min node_watch job, the /api/admin/nodes
route while the Servers page polls) calls ``stamp_and_get`` and connected nodes
get their timestamp advanced. Stored as a small JSON file in data/ (same
pattern as node_watch.json) so restarts keep history; keyed by node id, with
the name kept alongside for display after a node is renamed/removed.

Single-writer by design: only the user-bot process serves HTTP and runs the
scheduler, so file races are not a concern.
"""
import json
import time

from app.core.paths import data_path
from app.utils.logger import bot_logger

_FILE = data_path("node_last_seen.json")
_OK_STATUSES = {"connected", "healthy"}
# Skip the disk write when no stamp moved by more than this (the Servers page
# polls every 10s; rewriting an unchanged file that often is pointless).
_WRITE_GRANULARITY_SEC = 30


def _load() -> dict:
    try:
        with open(_FILE, encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def stamp_and_get(nodes: list) -> dict:
    """Advance the last-seen stamp for every currently-connected node and
    return the full map {node_id_str: {"ts": epoch_sec, "name": str}}."""
    seen = _load()
    now = int(time.time())
    dirty = False
    for n in nodes or []:
        if not isinstance(n, dict) or n.get("id") is None:
            continue
        status = str(n.get("status") or "").lower()
        if status not in _OK_STATUSES:
            continue
        key = str(n["id"])
        prev = seen.get(key) or {}
        if now - int(prev.get("ts") or 0) >= _WRITE_GRANULARITY_SEC:
            seen[key] = {"ts": now, "name": str(n.get("name") or f"node-{key}")}
            dirty = True
    if dirty:
        try:
            with open(_FILE, "w", encoding="utf-8") as f:
                json.dump(seen, f, ensure_ascii=False)
        except Exception as e:
            bot_logger.warning(f"[NODES] could not persist last-seen map: {e}")
    return seen
