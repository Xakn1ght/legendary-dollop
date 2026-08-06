"""Owner-editable bot texts — /texts in the ADMIN bot.

Flow (built for a non-technical owner):
  /texts            → how-to + a few sample keys
  <paste any text>  → finds messages containing it (searches fa/en/keys)
  pick a result     → shows current fa/en with edit / reset buttons
  edit              → send the replacement AS A NORMAL MESSAGE — bold, links
                      and PREMIUM EMOJIS are captured from the message
                      entities (html_text keeps <tg-emoji>) and stored in
                      data/bot_texts_overrides.json
  preview           → the saved text is sent back through the bot so what
                      you see is exactly what users will get

Safety: an override may only use {placeholders} that exist in the default
text (a typo'd {nmae} would crash .format() at send time — rejected here).
The user bot hot-reloads the overrides file within ~3s (see bot_i18n).
"""
from __future__ import annotations

import html as html_mod

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.shared.admin_access import ADMIN_IDS
from app.utils import bot_i18n

router = Router()

# chat_id → {"mode": "search"|"edit", "key": str, "lang": "fa"|"en"}
_STATE: dict[int, dict] = {}

_PAGE_SIZE = 8


def _is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS


def _label(key: str) -> str:
    """Button label: key + a peek at the Persian text."""
    fa = (bot_i18n.get_override(key).get("fa") or bot_i18n.get_default(key).get("fa") or "")
    fa = " ".join(fa.split())
    return f"{key} · {fa[:24]}" if fa else key


def _search(query: str) -> list[str]:
    q = " ".join(query.split()).lower()
    if not q:
        return []
    hits = []
    for key in bot_i18n.list_text_keys():
        texts = [key.lower()]
        for src in (bot_i18n.get_default(key), bot_i18n.get_override(key)):
            texts.extend(v.lower() for v in src.values())
        if any(q in t for t in texts):
            hits.append(key)
    return hits


def _results_kb(keys: list[str], page: int = 0) -> InlineKeyboardMarkup:
    start = page * _PAGE_SIZE
    chunk = keys[start:start + _PAGE_SIZE]
    rows = [[InlineKeyboardButton(text=_label(k), callback_data=f"btx:open:{k}")] for k in chunk]
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="قبلی", callback_data=f"btx:page:{page - 1}"))
    if start + _PAGE_SIZE < len(keys):
        nav.append(InlineKeyboardButton(text="بعدی", callback_data=f"btx:page:{page + 1}"))
    if nav:
        rows.append(nav)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _detail_kb(key: str) -> InlineKeyboardMarkup:
    ov = bot_i18n.get_override(key)
    rows = [
        [
            InlineKeyboardButton(text="ویرایش فارسی", callback_data=f"btx:edit:fa:{key}"),
            InlineKeyboardButton(text="Edit EN", callback_data=f"btx:edit:en:{key}"),
        ]
    ]
    reset = []
    if "fa" in ov:
        reset.append(InlineKeyboardButton(text="فارسی به پیش‌فرض", callback_data=f"btx:reset:fa:{key}"))
    if "en" in ov:
        reset.append(InlineKeyboardButton(text="EN default", callback_data=f"btx:reset:en:{key}"))
    if reset:
        rows.append(reset)
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _show_detail(message: Message, key: str) -> None:
    default = bot_i18n.get_default(key)
    ov = bot_i18n.get_override(key)
    ph = bot_i18n.placeholders(default.get("fa", "") + default.get("en", ""))

    def block(lang: str) -> str:
        cur = ov.get(lang) or default.get(lang) or "—"
        tag = " (ویرایش‌شده)" if lang in ov else ""
        return f"<b>{lang.upper()}{tag}:</b>\n<code>{html_mod.escape(cur)}</code>"

    note = ""
    if ph:
        note = "\n\nجای‌گیرها (باید عیناً بمانند): " + " ".join(f"<code>{{{p}}}</code>" for p in sorted(ph))
    await message.answer(
        f"<b>{key}</b>\n\n{block('fa')}\n\n{block('en')}{note}",
        reply_markup=_detail_kb(key),
    )


@router.message(Command("texts"))
async def texts_cmd(message: Message):
    if not _is_admin(message.from_user.id):
        return
    _STATE[message.chat.id] = {"mode": "search"}
    await message.answer(
        "<b>ویرایش پیام‌های ربات</b>\n\n"
        "بخشی از متن پیامی که می‌خوای عوض کنی رو همینجا بفرست "
        "(مثلاً «دعوت شما» یا «خرید سرویس») تا پیداش کنم.\n\n"
        "بعد از انتخاب، متن جدید رو به‌صورت یک پیام عادی بفرست — "
        "<b>بولد، لینک و ایموجی‌های پرمیوم</b> همون‌طور که می‌فرستی ذخیره می‌شن.\n"
        "تغییرات بدون ری‌استارت، تا چند ثانیه بعد روی ربات اصلی اعمال می‌شن."
    )


@router.callback_query(F.data.startswith("btx:"))
async def texts_cb(callback: CallbackQuery):
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    parts = callback.data.split(":")
    action = parts[1]
    chat_id = callback.message.chat.id

    if action == "page":
        st = _STATE.get(chat_id) or {}
        keys = st.get("results") or []
        page = int(parts[2])
        try:
            await callback.message.edit_reply_markup(reply_markup=_results_kb(keys, page))
        except Exception:
            pass
        await callback.answer()
        return

    if action == "open":
        key = parts[2]
        _STATE[chat_id] = {"mode": "search"}
        await _show_detail(callback.message, key)
        await callback.answer()
        return

    if action == "edit":
        lang, key = parts[2], parts[3]
        if key not in bot_i18n.list_text_keys():
            await callback.answer("Unknown key", show_alert=True)
            return
        _STATE[chat_id] = {"mode": "edit", "key": key, "lang": lang}
        ph = bot_i18n.placeholders(
            bot_i18n.get_default(key).get(lang, "") or bot_i18n.get_default(key).get("fa", "")
        )
        hint = (" — جای‌گیرها را نگه دار: " + " ".join(f"<code>{{{p}}}</code>" for p in sorted(ph))) if ph else ""
        await callback.message.answer(
            f"متن جدید <b>{key}</b> ({lang.upper()}) را به‌صورت یک پیام بفرست{hint}\n"
            "برای انصراف: /cancel"
        )
        await callback.answer()
        return

    if action == "reset":
        lang, key = parts[2], parts[3]
        try:
            bot_i18n.set_override(key, lang, None)
            await callback.answer("به پیش‌فرض برگشت")
            await _show_detail(callback.message, key)
        except Exception as e:
            await callback.answer(f"خطا: {e}", show_alert=True)
        return

    await callback.answer()


@router.message(Command("cancel"))
async def texts_cancel(message: Message):
    if not _is_admin(message.from_user.id):
        return
    if (_STATE.get(message.chat.id) or {}).get("mode") == "edit":
        _STATE[message.chat.id] = {"mode": "search"}
        await message.answer("لغو شد.")


@router.message(F.text | F.caption)
async def texts_free_text(message: Message):
    """Search queries + edit submissions. LAST router in admin_main, so any
    text other admin handlers consumed never reaches here."""
    if not _is_admin(message.from_user.id):
        return
    st = _STATE.get(message.chat.id)
    if not st:
        return
    raw_plain = message.text or message.caption or ""
    if raw_plain.startswith("/"):
        return

    if st.get("mode") == "edit":
        key, lang = st["key"], st["lang"]
        # html_text preserves bold/links AND premium emoji as <tg-emoji> tags.
        try:
            new_html = message.html_text
        except Exception:
            new_html = html_mod.escape(raw_plain)
        default_src = bot_i18n.get_default(key)
        allowed = bot_i18n.placeholders(default_src.get("fa", "") + default_src.get("en", ""))
        used = bot_i18n.placeholders(new_html)
        unknown = used - allowed
        if unknown:
            await message.answer(
                "این جای‌گیرها در متن اصلی وجود ندارند و موقع ارسال خطا می‌دهند: "
                + " ".join(f"<code>{{{p}}}</code>" for p in sorted(unknown))
                + "\nمتن را اصلاح کن و دوباره بفرست."
            )
            return
        try:
            bot_i18n.set_override(key, lang, new_html)
        except Exception as e:
            await message.answer(f"ذخیره نشد: {e}")
            return
        _STATE[message.chat.id] = {"mode": "search"}
        # Preview through the bot = exactly what users will see (placeholders
        # filled with samples). If Telegram rejects the HTML, the admin sees
        # the error here instead of users seeing a broken DM later.
        sample = {p: "نمونه" if lang == "fa" else "Sample" for p in allowed}
        if "name" in sample:
            sample["name"] = "Tsuki"
        try:
            preview = new_html.format(**sample) if sample else new_html
        except Exception:
            preview = new_html
        await message.answer("ذخیره شد — پیش‌نمایش (همین را کاربر می‌بیند):")
        try:
            await message.answer(preview)
        except Exception as e:
            bot_i18n.set_override(key, lang, None)
            await message.answer(
                f"تلگرام این متن را نپذیرفت ({html_mod.escape(str(e))}) — تغییر برگردانده شد."
            )
        return

    # search mode
    hits = _search(raw_plain)
    if not hits:
        await message.answer("چیزی پیدا نشد — یک تکه متن دیگر از همان پیام را امتحان کن.")
        return
    st["results"] = hits
    await message.answer(
        f"{len(hits)} پیام پیدا شد:",
        reply_markup=_results_kb(hits, 0),
    )
