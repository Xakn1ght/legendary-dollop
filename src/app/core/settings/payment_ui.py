"""Payment card display defaults and canned support replies; JSON under ``app/core/``."""

import json
import os
import sys

from app.core.settings.bootstrap import CORE_DIR

# -----------------------------
# Payment Settings
# -----------------------------
PAYMENT_CARD_NUMBER = os.environ.get("PAYMENT_CARD_NUMBER", "6037-xxxx-xxxx-xxxx")
PAYMENT_CARD_HOLDER = os.environ.get("PAYMENT_CARD_HOLDER", "")

# Payment settings file (overrideable via admin)
_payment_settings_path = str(CORE_DIR / "payment_settings.json")
if CORE_DIR.joinpath("payment_settings.json").exists():
    try:
        with open(_payment_settings_path, "r", encoding="utf-8") as _f:
            _payment_data = json.load(_f)
            if "card_number" in _payment_data:
                PAYMENT_CARD_NUMBER = _payment_data["card_number"]
            if "card_holder" in _payment_data:
                PAYMENT_CARD_HOLDER = _payment_data["card_holder"]
    except Exception as _e:
        print("Failed to load payment_settings.json:", _e, file=sys.stderr)


def save_payment_settings(card_number=None, card_holder=None):
    global PAYMENT_CARD_NUMBER, PAYMENT_CARD_HOLDER
    if card_number is not None:
        PAYMENT_CARD_NUMBER = card_number
    if card_holder is not None:
        PAYMENT_CARD_HOLDER = card_holder
    try:
        with open(_payment_settings_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "card_number": PAYMENT_CARD_NUMBER,
                    "card_holder": PAYMENT_CARD_HOLDER,
                },
                f,
                indent=2,
            )
    except Exception as e:
        print(f"Failed to save payment settings: {e}", file=sys.stderr)


# Canned Responses
CANNED_RESPONSES = [
    "سلام، مشکل شما بررسی شد.",
    "لطفا اسکرین شات ارسال کنید.",
    "با تشکر از تماس شما.",
]
CANNED_RESPONSES_FILE = str(CORE_DIR / "canned_responses.json")

if CORE_DIR.joinpath("canned_responses.json").exists():
    try:
        with open(CANNED_RESPONSES_FILE, "r", encoding="utf-8") as f:
            loaded = json.load(f)
            if isinstance(loaded, list):
                CANNED_RESPONSES = loaded
    except Exception:
        pass


def save_canned_responses():
    try:
        with open(CANNED_RESPONSES_FILE, "w", encoding="utf-8") as f:
            json.dump(CANNED_RESPONSES, f, indent=2)
    except Exception:
        pass
