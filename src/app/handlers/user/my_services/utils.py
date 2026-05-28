import os
import time
import urllib.request
from io import BytesIO

from aiogram.filters import BaseFilter
from aiogram.types import Message
from PIL import Image, ImageDraw, ImageFont

from .constants import COUNTRY_COLORS, COUNTRY_ORDER


def convert_to_gb(usage_byte):
    if not usage_byte:
        return 0
    return round(usage_byte / 1024 / 1024 / 1024, 2)


def map_inbound_to_country(inbound_name: str) -> str:
    """Return a human-friendly country name based on an inbound/node name.

    Uses simple keyword matching; falls back to the original name when unknown.
    """
    if not inbound_name:
        return "Other"
    name = inbound_name.lower()
    mapping: list[tuple[list[str], str]] = [
        (["swiss", "switzerland", "ch-"], "Switzerland"),
        (["germany", "de-", "berlin"], "Germany"),
        (["netherland", "netherlands", "nl-", "amsterdam"], "Netherlands"),
        (["turkey", "tr-", "istanbul"], "Turkey"),
        (["usa", "unitedstates", "united-states", "us-", "america"], "USA"),
        (["uae", "emirates", "dubai", "ae-"], "UAE"),
        (["france", "fr-", "paris"], "France"),
        (["uk", "unitedkingdom", "united-kingdom", "gb-", "london"], "United Kingdom"),
        (["canada", "ca-", "toronto"], "Canada"),
    ]
    for keywords, country in mapping:
        if any(k in name for k in keywords):
            return country
    if "master" in name:
        return "Other"
    # If not matched, bucket under Other so legend shows countries only
    return "Other"


def country_flag(country: str) -> str:
    flags = {
        "Switzerland": "🇨🇭",
        "Germany": "🇩🇪",
        "Netherlands": "🇳🇱",
        "Turkey": "🇹🇷",
        "USA": "🇺🇸",
        "UAE": "🇦🇪",
        "France": "🇫🇷",
        "United Kingdom": "🇬🇧",
        "Canada": "🇨🇦",
        "Other": "🌐",
    }
    return flags.get(country, "🌐")


def country_code(country: str) -> str | None:
    codes = {
        "Switzerland": "ch",
        "Germany": "de",
        "Netherlands": "nl",
        "Turkey": "tr",
        "USA": "us",
        "UAE": "ae",
        "France": "fr",
        "United Kingdom": "gb",
        "Canada": "ca",
        "Other": None,
    }
    return codes.get(country)


def get_flag_icon_path(country: str) -> str | None:
    code = country_code(country)
    if not code:
        return None
    flags_dir = os.path.join("app", "assets", "flags")
    os.makedirs(flags_dir, exist_ok=True)
    local_path = os.path.join(flags_dir, f"{code}.png")
    if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
        return local_path
    try:
        url = f"https://flagcdn.com/w40/{code}.png"
        urllib.request.urlretrieve(url, local_path)
        return local_path
    except Exception:
        return None


def get_days_remaining(timestamp):
    if not timestamp:
        return "نامحدود ♾️"
    remaining_seconds = timestamp - int(time.time())
    if remaining_seconds <= 0:
        return "پایان یافته 🔚"
    return f"{remaining_seconds // (60 * 60 * 24)} روز"


def _traffic_bar(percent: float, length: int = 10) -> str:
    if percent < 0:
        percent = 0
    if percent > 1:
        percent = 1
    filled = int(round(percent * length))
    empty = max(0, length - filled)
    return "▉" * filled + "▁" * empty


def _to_persian_digits(text):
    """Convert Latin digits to Persian digits."""
    persian_map = str.maketrans('0123456789.', '۰۱۲۳۴۵۶۷۸۹٫')
    return str(text).translate(persian_map)


def to_persian_digits(s):
    persian_digits = "۰۱۲۳۴۵۶۷۸۹"
    return ''.join(persian_digits[int(ch)] if ch.isdigit() else ch for ch in str(s))


class MyServiceFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        if not message.text:
            return False
        txt = message.text.replace('‌', '')  # remove ZWNJ if present
        return ('سرویس' in txt) and ('من' in txt)


def _link_name(url: str) -> str:
    """Return decoded name for config (text after #)."""
    if '#' in url:
        return urllib.parse.unquote(url.split('#')[-1])
    try:
        return url.split('//')[1].split('/')[0]
    except Exception:
        return "config"


def _measure_text(draw_obj, text: str, font):
    """Helper to measure text size across Pillow versions"""
    try:
        bbox = draw_obj.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]
    except Exception:
        try:
            bbox = font.getbbox(text)
            return bbox[2] - bbox[0], bbox[3] - bbox[1]
        except Exception:
            # Last resort fallback
            return (max(8 * len(text), 8), 16)


def _load_font(size: int, prefer_latin: bool = False):
    """Load a high-quality font.

    - For Latin text, prefer Google fonts (Inter/Roboto) vendored under `app/assets/fonts`.
    - Falls back to system fonts and Persian/Arabic-capable fonts.
    """
    fonts_dir = os.path.join("app", "assets", "fonts")
    os.makedirs(fonts_dir, exist_ok=True)

    def ensure_font(local_name: str, url: str) -> str | None:
        path = os.path.join(fonts_dir, local_name)
        if os.path.exists(path) and os.path.getsize(path) > 0:
            return path
        try:
            # Attempt download; ignore failures and return None
            urllib.request.urlretrieve(url, path)
            return path
        except Exception:
            return None

    def first_existing(paths: list[str]) -> str | None:
        for p in paths:
            if p and os.path.exists(p) and os.path.getsize(p) > 0:
                return p
        return None

    # Prefer bundled Product Sans and system fonts first (no network). Only if none
    # are available, attempt lightweight downloads of open fonts.
    product_sans_local = first_existing([
        os.path.join(fonts_dir, "Product Sans Regular.ttf"),
        os.path.join(fonts_dir, "Product Sans.ttf"),
        os.path.join(fonts_dir, "ProductSans-Regular.ttf"),
    ])

    system_latin = [
        "/usr/share/fonts/truetype/roboto/Roboto-Regular.ttf",
        "/usr/share/fonts/truetype/inter/Inter.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ]
    system_arabic = [
        "/usr/share/fonts/truetype/vazirmatn/Vazirmatn-Regular.ttf",
        "/usr/share/fonts/truetype/vazir/Vazir.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf",
    ]

    primary_candidates = [product_sans_local] + (
        system_latin if prefer_latin else system_arabic
    ) + (
        system_arabic if prefer_latin else system_latin
    )
    for path in primary_candidates:
        try:
            if path:
                return ImageFont.truetype(path, size)
        except Exception:
            continue

    # Last resort: try downloading a few high-quality open fonts
    inter_local = ensure_font(
        "Inter-Regular.ttf",
        "https://github.com/google/fonts/raw/main/ofl/inter/Inter-Regular.ttf",
    )
    roboto_local = ensure_font(
        "Roboto-Regular.ttf",
        "https://github.com/google/fonts/raw/main/apache/roboto/Roboto-Regular.ttf",
    )
    noto_sans_local = ensure_font(
        "NotoSans-Regular.ttf",
        "https://github.com/google/fonts/raw/main/ofl/notosans/NotoSans-Regular.ttf",
    )
    download_candidates = [
        p for p in [product_sans_local, inter_local, roboto_local, noto_sans_local] if p
    ]
    for path in download_candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue

    return ImageFont.load_default()


def _create_doughnut_chart(
    title: str,
    labels: list[str],
    values: list[float],
    icons: list[str | None] | None = None,
    colors: list[tuple[int, int, int]] | None = None,
    width: int = 1100,
    height: int = 700
) -> BytesIO:
    """Return BytesIO of a doughnut (ring) chart image for the given data.

    Uses pure Pillow to avoid extra dependencies.
    """
    from .constants import USAGE_CHART_COLORS, USAGE_CHART_COLORS_CONFIG, USAGE_CHART_CONFIG

    # Guard against empty data
    n = len(labels)
    if n == 0:
        labels = ["-"]
        values = [1.0]
        n = 1

    # Keep the provided order to preserve alignment with colors and flags
    values = [float(v or 0.0) for v in values]
    n = len(labels)
    total = sum(values) or 0.0
    # Avoid division by zero – render as empty ring if total == 0
    safe_total = total if total > 0 else 1.0

    # Colors palette (cycled)
    palette = USAGE_CHART_COLORS

    bg_color = USAGE_CHART_COLORS_CONFIG["bg_color"]
    fg_text = USAGE_CHART_COLORS_CONFIG["fg_text"]
    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    # Scale font sizes with canvas height for better quality (larger legend and center)
    title_font_size = max(22, int(height * USAGE_CHART_CONFIG["title_font_size_ratio"]))
    center_font_size = max(20, int(height * USAGE_CHART_CONFIG["center_font_size_ratio"]))
    legend_font_size = max(20, int(height * USAGE_CHART_CONFIG["legend_font_size_ratio"]))

    font_title = _load_font(title_font_size, prefer_latin=False)
    font_center = _load_font(center_font_size, prefer_latin=True)
    font_legend = _load_font(legend_font_size, prefer_latin=True)

    # Draw title only if provided (allow disabling by sending empty string)
    if title and title.strip():
        title_w, title_h = _measure_text(draw, title, font_title)
        draw.text(((width - title_w) // 2, 18), title, fill=fg_text, font=font_title)

    # Chart area
    margin = USAGE_CHART_CONFIG["margin"]
    legend_w = USAGE_CHART_CONFIG["legend_width"]
    diameter = min(width - legend_w - margin * 3, height - margin * 2)
    left = margin
    top = (height - diameter) // 2
    right = left + diameter
    bottom = top + diameter
    bbox = (left, top, right, bottom)

    # Start angle at 270 (top) and fix rounding gaps by distributing remainder
    # Compute integer extents first
    if total > 0:
        raw_angles = [360.0 * (v / safe_total) for v in values]
        extents = [max(0, int(round(a))) for a in raw_angles]
        remainder = 360 - sum(extents)
        if remainder != 0 and values:
            # Add/subtract the remainder to the largest slice to avoid a visible gap/overdraw
            target_idx = max(range(len(values)), key=lambda i: values[i])
            extents[target_idx] = max(0, extents[target_idx] + remainder)

        start_angle = -90
        for i, extent in enumerate(extents):
            if extent <= 0:
                continue
            color = colors[i] if colors and i < len(colors) else palette[i % len(palette)]
            draw.pieslice(bbox, start=start_angle, end=start_angle + extent, fill=color)
            start_angle += extent
    else:
        # No data: draw nothing (hole + legend will render)
        pass

    # Inner hole for doughnut
    hole_ratio = USAGE_CHART_CONFIG["hole_ratio"]
    hole_d = int(diameter * hole_ratio)
    hole_bbox = (
        left + (diameter - hole_d) // 2,
        top + (diameter - hole_d) // 2,
        left + (diameter + hole_d) // 2,
        top + (diameter + hole_d) // 2,
    )
    draw.ellipse(hole_bbox, fill=(30, 33, 36))

    # Center text (total)
    center_text = f"{total:.2f} GB"
    tw, th = _measure_text(draw, center_text, font_center)
    draw.text((left + diameter / 2 - tw / 2, top + diameter / 2 - th / 2), center_text, fill=(220, 220, 220), font=font_center)

    # Legend (anchored to bottom-right, larger items)
    box_size = 30
    spacing = 25
    line_h = box_size + spacing
    # Prebuild legend items and measure max width to right-align the block
    def _fmt(v: float) -> str:
        return f"{v:.2f} GB"
    legend_items: list[tuple[tuple[int, int, int], str, str | None]] = []
    max_text_w = 0
    # Build legend items strictly by index to align with labels/values/colors/icons
    for i in range(len(labels)):
        label = labels[i]
        v = values[i]
        color = colors[i] if colors and i < len(colors) else palette[i % len(palette)]
        pct = (v / total * 100) if total > 0 else 0
        text = f"{label}: {_fmt(v)}  ({pct:.1f}%)"
        w, _ = _measure_text(draw, text, font_legend)
        max_text_w = max(max_text_w, w)
        icon_path = icons[i] if icons and i < len(icons) else None
        legend_items.append((color, text, icon_path))
    # Color square (flag inside) + gap + text
    block_width = box_size + 14 + max_text_w
    legend_left = width - margin - block_width
    # Compute block height and vertically center the legend on the right side
    block_height = len(labels) * line_h
    legend_top = (height - block_height) // 2

    for i, (color, text, icon_path) in enumerate(legend_items):
        y = legend_top + i * line_h
        # Draw colored square (slice color)
        draw.rectangle([legend_left, y, legend_left + box_size, y + box_size], fill=color)
        # Draw flag INSIDE the square (centered) so color remains behind
        if icon_path:
            try:
                pad = max(2, box_size // 8)
                icon_size = max(1, box_size - pad * 2)
                flag_img = Image.open(icon_path).convert("RGB")
                flag_img = flag_img.resize((icon_size, icon_size))
                fx = legend_left + (box_size - icon_size) // 2
                fy = y + (box_size - icon_size) // 2
                img.paste(flag_img, (fx, fy))
            except Exception:
                pass
        # Center text vertically to the block using measured text height
        text_x = legend_left + box_size + 14
        tw2, th2 = _measure_text(draw, text, font_legend)
        text_y = y + (box_size - th2) // 1
        draw.text((text_x, text_y), text, fill=fg_text, font=font_legend)

    # Output as bytes
    bio = BytesIO()
    img.save(bio, format="PNG")
    bio.seek(0)
    return bio
