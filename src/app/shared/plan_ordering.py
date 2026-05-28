from __future__ import annotations

import json
from pathlib import Path

from app.core.settings import CHARGE_PRESET_PACKAGES, PLANS

_CORE_DIR = Path(__file__).resolve().parents[1] / "core"
_PLANS_ORDER_FILE = _CORE_DIR / "plans_order.json"
_CHARGE_PLANS_ORDER_FILE = _CORE_DIR / "charge_plans_order.json"


def _load_order(path: Path, fallback: list[str]) -> list[str]:
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8") or "null")
            if isinstance(data, list):
                return [str(x) for x in data if str(x).strip()]
    except Exception:
        pass
    return list(fallback)


def get_ordered_plans() -> list[str]:
    order = _load_order(_PLANS_ORDER_FILE, list(PLANS.keys()))
    ordered = [k for k in order if k in PLANS]
    for k in PLANS.keys():
        if k not in ordered:
            ordered.append(k)
    return ordered


def get_ordered_charge_plans() -> list[str]:
    order = _load_order(_CHARGE_PLANS_ORDER_FILE, list(CHARGE_PRESET_PACKAGES.keys()))
    ordered = [k for k in order if k in CHARGE_PRESET_PACKAGES]
    for k in CHARGE_PRESET_PACKAGES.keys():
        if k not in ordered:
            ordered.append(k)
    return ordered


def save_plans_order(order: list[str]) -> None:
    try:
        _PLANS_ORDER_FILE.write_text(
            json.dumps(order, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


def save_charge_plans_order(order: list[str]) -> None:
    try:
        _CHARGE_PLANS_ORDER_FILE.write_text(
            json.dumps(order, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass

