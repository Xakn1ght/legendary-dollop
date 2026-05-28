import time
from collections import defaultdict
from urllib.parse import unquote

from aiogram import F
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import BufferedInputFile, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import crud
from app.database.models import Subscription
from app.services.marzban import marzban_api
from app.utils.bot_i18n import get_cached_lang, t

from ..constants import COUNTRY_COLORS, COUNTRY_ORDER
from ..utils import (
    _create_doughnut_chart,
    convert_to_gb,
    country_flag,
    get_flag_icon_path,
    map_inbound_to_country,
)
from .common import _last_link_click, router


@router.callback_query(F.data.startswith("link_"))
async def send_subscription_links(callback: CallbackQuery, session: AsyncSession):
    lang = get_cached_lang(callback.from_user.id)
    sub_id = int(callback.data.split("_")[1])

    # Cool-down check (30 s)
    key = (callback.from_user.id, sub_id)
    now = time.time()
    last_ts = _last_link_click.get(key)
    if last_ts and now - last_ts < 30:
        await callback.answer(t(lang, "wait_before_links"), show_alert=True)
        return

    _last_link_click[key] = now

    # Load subscription & fetch links from Marzban
    sub = await crud.activate_subscription(session, sub_id)
    if not sub:
        await callback.answer(t(lang, "service_not_found"), show_alert=True)
        return

    user_info = await marzban_api.get_fast_user_info(sub.marzban_username, getattr(sub, 'sub_token', None))
    if not user_info:
        await callback.answer(t(lang, "failed_fetch_links"), show_alert=True)
        return

    links = user_info.get("links", []) or []
    if not links:
        await callback.answer(t(lang, "no_links_returned"), show_alert=True)
        return

    def _link_name(url: str) -> str:
        """Return decoded name for config (text after #)."""
        if '#' in url:
            return unquote(url.split('#')[-1])
        try:
            return url.split('//')[1].split('/')[0]
        except Exception:
            return "config"

    lines = [f"🌐 <b>{_link_name(l)}</b>\n<code>{l}</code>" for l in links]
    # Add a close (X) button so user can dismiss the long list
    close_kb = InlineKeyboardBuilder()
    close_kb.button(text=t(lang, "close_btn"), callback_data="close_inline")
    await callback.message.answer(
        "\n\n".join(lines),
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=close_kb.as_markup()
    )
    await callback.answer(t(lang, "links_sent"))


@router.callback_query(F.data == "close_inline")
async def close_inline_message(callback: CallbackQuery):
    """Closes (deletes) the message that contains the inline keyboard."""
    try:
        await callback.message.delete()
    except TelegramBadRequest:
        # If already deleted or cannot delete, just ignore
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("usage_"))
async def send_usage(callback: CallbackQuery, session: AsyncSession):
    lang = get_cached_lang(callback.from_user.id)
    sub_id = int(callback.data.split("_")[1])

    sub = await session.get(Subscription, sub_id)
    if not sub:
        await callback.answer(t(lang, "service_not_found"), show_alert=True)
        return

    usage_list = await marzban_api.get_user_usage(sub.marzban_username, days=7)
    if usage_list is None:
        await callback.answer(t(lang, "failed_fetch_usage"), show_alert=True)
        return

    # Build textual summary and chart data (aggregate by country)
    lines = [t(lang, "weekly_usage")]
    country_to_gb: dict[str, float] = defaultdict(float)
    for idx, item in enumerate(usage_list, 1):
        node = item.get('node_name', f"node{idx}")
        country = map_inbound_to_country(node)
        used_gb = float(convert_to_gb(item.get('used_traffic', 0)))
        country_to_gb[country] += used_gb

    # Show ONLY countries present in data (no fake entries). Keep requested order; put 'Other' last.
    present = list(country_to_gb.keys())
    # Order by configured list first, then any unknowns
    ordered = [c for c in COUNTRY_ORDER if c in present] + [c for c in present if c not in COUNTRY_ORDER]
    # Move Other to end if present
    if "Other" in ordered:
        ordered = [c for c in ordered if c != "Other"] + ["Other"]

    # Build one definitive data structure to eliminate any misalignment
    items_data = []  # list of dicts with country, value, color, icon
    for country in ordered:
        val = float(country_to_gb.get(country, 0.0))
        color = COUNTRY_COLORS.get(country, (127, 140, 141))
        icon = get_flag_icon_path(country)
        items_data.append({
            "country": country,
            "value": val,
            "color": color,
            "icon": icon,
        })
    labels: list[str] = [item["country"] for item in items_data]
    values: list[float] = [item["value"] for item in items_data]
    icons: list[str | None] = [item["icon"] for item in items_data]
    colors: list[tuple[int, int, int]] = [item["color"] for item in items_data]
    for item in items_data:
        country = item["country"]
        gb = item["value"]
        lines.append(f"{country_flag(country)} {country}: {gb:.2f} GB")

    # Create a doughnut chart image (higher resolution, no title)
    img_bytes = _create_doughnut_chart(
        title="",
        labels=labels,
        values=values,
        icons=icons,
        colors=colors,
        width=1920,
        height=1080,
    )

    # Send as photo with caption (use BufferedInputFile for aiogram v3)
    try:
        img_bytes.seek(0)
        photo = BufferedInputFile(img_bytes.getvalue(), filename="usage.png")
        await callback.message.answer_photo(photo=photo, caption="\n".join(lines))
    except Exception:
        # Fallback to text-only
        await callback.message.answer("\n".join(lines))

    await callback.answer()
