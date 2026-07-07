"""Premium (custom) Telegram emoji for bot messages.

Mechanism (same as ../bakbot, the reference implementation): Telegram's HTML
parse mode understands ``<tg-emoji emoji-id="...">🎁</tg-emoji>``. Clients that
can render the premium emoji show the animated one; everything else — old
clients, or Telegram stripping the entity because the bot lacks the
entitlement — falls back to the plain emoji between the tags. The emoji ids
below are the owner-owned ids bakbot already sends to customers.

Bot API caveat: custom-emoji entities are only *honored* for bots that
purchased a Fragment username; otherwise the plain fallback emoji is shown.
Wrapping is therefore always safe, and the send helpers additionally retry
with the un-wrapped text if Telegram rejects the message outright.

Reply-keyboard button labels cannot carry custom emoji (plain text only by
Bot API design), so this applies to messages, not the main menu.
"""
from __future__ import annotations

import re

from aiogram.exceptions import TelegramBadRequest

# Owner-owned premium emoji ids (source: ../bakbot PLAN_TIER_EMOJI + templates).
# Key = plain emoji as it appears in copy, value = custom_emoji_id.
PREMIUM_EMOJI: dict[str, str] = {
    "🚀": "5201707043341222252",
    "👋": "5224339815889127935",
    "🎁": "5418379033798785747",
    "✅": "5237699328843200968",
    "⭐️": "5285375308369767796",
    "⭐": "5285375308369767796",
    "🪐": "5285454181149191307",
    "👨‍🚀": "5285082773852270464",
    "👤": "5195386019712613770",
    "❤️": "5424704610092726911",
    "☺️": "5379561106492630835",
    "✍️": "5197269100878907942",
    "🔗": "4958689671950369798",
    "⌛": "5386367538735104399",
    "❗️": "5445331903496332384",
    "❗": "5445331903496332384",
    "❌": "5210952531676504517",
    "🔴": "5283113359548363829",
    "🔵": "5285518176161903861",
    "⛔️": "5976295680686165294",
}

# Longest emoji first so multi-codepoint sequences (👨‍🚀, ⭐️) win over their prefixes.
_EMOJI_RE = re.compile(
    "|".join(re.escape(e) for e in sorted(PREMIUM_EMOJI, key=len, reverse=True))
)


def pe(emoji: str) -> str:
    """One emoji → its premium tg-emoji HTML (or itself if we own no id for it)."""
    eid = PREMIUM_EMOJI.get(emoji)
    if not eid:
        return emoji
    return f'<tg-emoji emoji-id="{eid}">{emoji}</tg-emoji>'


def premiumize(html_text: str) -> str:
    """Wrap every known plain emoji in an HTML-parse-mode text with its premium twin.

    Idempotent enough for our copy: already-wrapped emoji would be re-wrapped,
    so call it once, on plain-emoji source text.
    """
    if not html_text:
        return html_text
    return _EMOJI_RE.sub(lambda m: pe(m.group(0)), html_text)


async def answer_premium(message, text: str, **kwargs):
    """message.answer() with premium emoji; falls back to the plain text on rejection."""
    kwargs.setdefault("parse_mode", "HTML")
    rich = premiumize(text)
    if rich != text:
        try:
            return await message.answer(rich, **kwargs)
        except TelegramBadRequest:
            pass
    return await message.answer(text, **kwargs)


async def send_premium(bot, chat_id: int, text: str, **kwargs):
    """bot.send_message() with premium emoji; falls back to the plain text on rejection."""
    kwargs.setdefault("parse_mode", "HTML")
    rich = premiumize(text)
    if rich != text:
        try:
            return await bot.send_message(chat_id, rich, **kwargs)
        except TelegramBadRequest:
            pass
    return await bot.send_message(chat_id, text, **kwargs)


async def edit_premium(message, text: str, **kwargs):
    """message.edit_text() with premium emoji; falls back to the plain text on rejection."""
    kwargs.setdefault("parse_mode", "HTML")
    rich = premiumize(text)
    if rich != text:
        try:
            return await message.edit_text(rich, **kwargs)
        except TelegramBadRequest:
            pass
    return await message.edit_text(text, **kwargs)
