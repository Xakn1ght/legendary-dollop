from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote

from aiogram import Router
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton

from app.core.paths import data_path

router = Router()

# FSM States for referral flow and language selection


class ReferralStates(StatesGroup):
	awaiting_code = State()
	awaiting_language = State()  # For new users to select language first


ALLOWED_USERS_FILE = Path(data_path("allowed_users.json"))

def _load_allowed_users():
	"""Load legacy users list.

	We support two possible JSON formats:

	1) New simple dict format expected by the bot:
	   {
	       "123456": true,
	       "usernames": ["foo", "bar"]
	   }

	2) Legacy array-of-objects exported from elsewhere (what you currently have):
	   [
	       {"chat_id": 123, "username": "foo", ...},
	       {"chat_id": 456, "username": "bar", ...}
	   ]

	This helper normalises either input into the dict format used by the rest of the code.
	"""
	if not ALLOWED_USERS_FILE.exists():
		return {}

	try:
		with open(ALLOWED_USERS_FILE, "r", encoding="utf-8") as f:
			data = json.load(f)

		# Case 1: already a dict – return as-is
		if isinstance(data, dict):
			# Ensure missing "usernames" key exists for safe .get()
			data.setdefault("usernames", [])
			return data

		# Case 2: list of objects – convert
		if isinstance(data, list):
			allowed = {"usernames": []}
			for item in data:
				if not isinstance(item, dict):
					continue
				chat_id = item.get("chat_id")
				if chat_id is not None:
					allowed[str(chat_id)] = True
				uname = item.get("username")
				if uname and uname != "N/A":
					allowed["usernames"].append(uname)
			return allowed

	except Exception:
		pass  # fallthrough to default

	return {}  # default empty if anything goes wrong

ALLOWED_USERS = _load_allowed_users()


def _is_og_user(chat_id: int, username: str = None) -> bool:
	"""Check if user is an OG user (existing customer) from allowed_users.json"""
	if not ALLOWED_USERS:
		return False
	
	# Check by chat_id
	if str(chat_id) in ALLOWED_USERS:
		return True
	
	# Check by username
	if username and "usernames" in ALLOWED_USERS:
		if username.lower() in [u.lower() for u in ALLOWED_USERS.get("usernames", [])]:
			return True
	
	return False

def _get_bot_username(bot) -> str:
	"""Get bot username from bot object"""
	try:
		if hasattr(bot, 'username') and bot.username:
			return bot.username
		if hasattr(bot, '_me') and bot._me and hasattr(bot._me, 'username'):
			return bot._me.username
		# Fallback: try to get from bot token (last resort)
		return "AstroByteBot"
	except Exception:
		return "AstroByteBot"

def _create_referral_link(bot, referral_code: str) -> str:
	"""Create referral link for sharing"""
	if not referral_code:
		return ""
	bot_username = _get_bot_username(bot)
	return f"https://t.me/{bot_username}?start={referral_code}"

def _create_share_button(bot, referral_code: str, lang: str) -> InlineKeyboardButton:
	"""Create share referral link button"""
	referral_link = _create_referral_link(bot, referral_code)
	share_url = f"https://t.me/share/url?url={quote(referral_link)}&text=" + quote(
		("🎁 کد دعوت من برای ربات AstroByte:\n" if lang == "fa" else "🎁 My invite code for AstroByte bot:\n") + referral_link
	)
	return InlineKeyboardButton(
		text=("📤 اشتراک‌گذاری لینک دعوت" if lang == "fa" else "📤 Share Referral Link"),
		url=share_url
	)

