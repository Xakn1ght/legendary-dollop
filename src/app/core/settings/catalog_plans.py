"""VIP / subscription / charge catalog defaults and JSON overrides under ``app/core/``."""

import json
import sys

from app.core.settings.bootstrap import CORE_DIR

# VIP Membership Plans (purchasable through webapp)
VIP_PLANS = {
    "1_month": {"days": 30, "price": 99_000, "label_fa": "۱ ماهه", "label_en": "1 Month"},
    "3_months": {"days": 90, "price": 249_000, "label_fa": "۳ ماهه", "label_en": "3 Months"},
    "6_months": {"days": 180, "price": 449_000, "label_fa": "۶ ماهه", "label_en": "6 Months"},
    "1_year": {"days": 365, "price": 799_000, "label_fa": "۱ ساله", "label_en": "1 Year"},
    "lifetime": {"days": None, "price": 1_499_000, "label_fa": "مادام‌العمر", "label_en": "Lifetime"},
}

# -----------------------------
# Charging / Top-up settings
# -----------------------------
# Define preset packages the user can pick from when charging a service.
# You can edit these dicts freely – the code will pick them up automatically.
# Each key is the label shown to the user; values specify what the package does.
CHARGE_PRESET_PACKAGES = {
    "۱۰ گیگابایت": {"gb": 10, "price": 20_000},
    "۲۰ گیگابایت": {"gb": 20, "price": 35_000},
    "۳۰ گیگابایت": {"gb": 30, "price": 50_000},
    "۵۰ گیگابایت": {"gb": 50, "price": 80_000},
    "۸۰ گیگابایت": {"gb": 80, "price": 120_000},
    "۱۰۰ گیگابایت": {"gb": 100, "price": 140_000},
}

# Rate per day extension (Toman per day) - used for custom day charging
CHARGE_RATE_PER_DAY = 2000

# Day packages
DAY_PLANS = {
    "۳۰ روز": {"days": 30, "price": 60_000},
    "۶۰ روز": {"days": 60, "price": 110_000},
    "۹۰ روز": {"days": 90, "price": 150_000},
    "۱۸۰ روز": {"days": 180, "price": 280_000},
}

# Attempt to override PACKAGES from optional JSON file (created via admin settings)
PACKAGES_FILE_PATH = str(CORE_DIR / "charge_packages.json")
if CORE_DIR.joinpath("charge_packages.json").exists():
    try:
        with open(PACKAGES_FILE_PATH, "r", encoding="utf-8") as f:
            _loaded_packages = json.load(f)
            if isinstance(_loaded_packages, dict):
                CHARGE_PRESET_PACKAGES.clear()
                CHARGE_PRESET_PACKAGES.update(_loaded_packages)
    except Exception as _e:
        print("Failed to load custom charge_packages.json:", _e, file=sys.stderr)


def save_charge_packages(packages_dict):
    try:
        with open(PACKAGES_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(packages_dict, f, indent=2)
    except Exception as e:
        print(f"Failed to save charge packages: {e}", file=sys.stderr)


# Charge plan button layout
CHARGE_PLANS_LAYOUT_FILE = str(CORE_DIR / "charge_plans_layout.json")


def _load_charge_plans_layout():
    if CORE_DIR.joinpath("charge_plans_layout.json").exists():
        try:
            with open(CHARGE_PLANS_LAYOUT_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("columns", 2)
        except Exception:
            pass
    return 2


def save_charge_plans_layout(columns):
    try:
        with open(CHARGE_PLANS_LAYOUT_FILE, "w", encoding="utf-8") as f:
            json.dump({"columns": columns}, f)
    except Exception:
        pass


CHARGE_PLANS_BUTTON_COLUMNS = _load_charge_plans_layout()

# Plans Order (Custom sort)
CHARGE_PLANS_ORDER_FILE = str(CORE_DIR / "charge_plans_order.json")

# -----------------------------
# Subscription Plans (Main)
# -----------------------------
# Plans can have "vip_only": True to make them exclusive to VIP users
PLANS = {
    "۲۰ گیگابایت": {"price": 40_000, "gb": 20},
    "۴۰ گیگابایت": {"price": 75_000, "gb": 40},
    "۶۰ گیگابایت": {"price": 110_000, "gb": 60},
    "۱۰۰ گیگابایت": {"price": 150_000, "gb": 100},
    # VIP Exclusive Plans (better value)
    "👑 ۱۵۰ گیگابایت VIP": {"price": 180_000, "gb": 150, "vip_only": True},
    "👑 ۲۰۰ گیگابایت VIP": {"price": 220_000, "gb": 200, "vip_only": True},
}

# Attempt to override PLANS from optional JSON file (created via admin settings)
_plans_path = str(CORE_DIR / "plans.json")

if CORE_DIR.joinpath("plans.json").exists():
    try:
        with open(_plans_path, "r", encoding="utf-8") as _f:
            _loaded_plans = json.load(_f)
            if isinstance(_loaded_plans, dict):
                PLANS.clear()
                PLANS.update(_loaded_plans)
    except Exception as _e:
        print("Failed to load custom plans.json:", _e, file=sys.stderr)

# Plan button layout (shared between admin and user UIs)
PLANS_LAYOUT_FILE = str(CORE_DIR / "plans_layout.json")


def _load_plans_layout():
    if CORE_DIR.joinpath("plans_layout.json").exists():
        try:
            with open(PLANS_LAYOUT_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("columns", 2)
        except Exception:
            pass
    return 2


def save_plans_layout(columns):
    try:
        with open(PLANS_LAYOUT_FILE, "w", encoding="utf-8") as f:
            json.dump({"columns": columns}, f)
    except Exception:
        pass


PLANS_BUTTON_COLUMNS = _load_plans_layout()

# -----------------------------
# User categories (admin adjustable)
# -----------------------------
USER_CATEGORIES = [
    "normal",
    "super",
    "hyper",
]

_user_categories_path = str(CORE_DIR / "user_categories.json")

if CORE_DIR.joinpath("user_categories.json").exists():
    try:
        with open(_user_categories_path, "r", encoding="utf-8") as _f:
            _loaded = json.load(_f)
            if isinstance(_loaded, list):
                USER_CATEGORIES.clear()
                USER_CATEGORIES.extend(_loaded)
    except Exception as _e:
        print("Failed to load custom user_categories.json:", _e, file=sys.stderr)
