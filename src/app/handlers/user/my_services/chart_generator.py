"""Static subscription usage card (PNG bytes).

2026-07-12, Pasha: "look in my other server the bakbot how its done i want
smth like that simple pic but matching the whole theme". This is bakbot's
usage_card.py layout — landscape glass panel, flat donut with REMAINING GB in
the center, four RTL stat rows, health-colored accent — restyled onto the
ASTROBYTE Dark Nebula tokens (tokens.css: bg #0a141b..#162a36, text #F5F2EA,
muted #8a93a3, ok/warn/bad semantics) with the dashboard's Vazirmatn type.

Pillow here is built with raqm, so Persian text shapes/bidis correctly when
drawn with direction='rtl' — raw strings in, no manual reordering.
"""
import datetime
import io
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

_FONTS_DIR = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "assets", "fonts"))
FONTS = {
    "r": os.path.join(_FONTS_DIR, "Vazirmatn-Regular.ttf"),
    "m": os.path.join(_FONTS_DIR, "Vazirmatn-Medium.ttf"),
    "b": os.path.join(_FONTS_DIR, "Vazirmatn-Bold.ttf"),
}

_FA = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")

# Theme tokens (dark) — keep in sync with webapp/dashboard/css/tokens.css.
_BG_TOP = (10, 20, 27)        # --bg-base
_BG_BOTTOM = (22, 42, 54)     # --bg-elev-2
_WHITE = (245, 242, 234)      # --text
_MUTED = (138, 147, 163)      # --text-muted
_TRACK = (42, 66, 83)         # --line-strong
_OK = (52, 211, 153)          # --ok
_WARN = (251, 191, 36)        # --warn
_BAD = (248, 113, 113)        # --bad
_BLUE = (96, 165, 250)        # --blue (unlimited)


def _fa_num(s) -> str:
    return str(s).translate(_FA)


def _fmt_gb(gb) -> str:
    if gb is None:
        return "∞"
    g = round(float(gb), 1)
    return _fa_num(int(g) if g == int(g) else g)


def _g2j(gy, gm, gd):
    """Gregorian -> Jalali (year, month, day)."""
    g_dm = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    if gy > 1600:
        jy = 979
        gy -= 1600
    else:
        jy = 0
        gy -= 621
    gy2 = gy + 1 if gm > 2 else gy
    days = (365 * gy + (gy2 + 3) // 4 - (gy2 + 99) // 100 + (gy2 + 399) // 400
            - 80 + gd + g_dm[gm - 1])
    jy += 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + days // 31
        jd = 1 + days % 31
    else:
        jm = 7 + (days - 186) // 30
        jd = 1 + (days - 186) % 30
    return jy, jm, jd


def _jalali_date(ts: int) -> str:
    try:
        import zoneinfo
        tz = zoneinfo.ZoneInfo("Asia/Tehran")
    except Exception:
        tz = datetime.timezone(datetime.timedelta(hours=3, minutes=30))
    d = datetime.datetime.fromtimestamp(int(ts), tz=tz)
    jy, jm, jd = _g2j(d.year, d.month, d.day)
    return f"{_fa_num(jy)}/{_fa_num(f'{jm:02d}')}/{_fa_num(f'{jd:02d}')}"


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _gradient(size, top, bottom):
    w, h = size
    base = Image.new("RGB", (1, h))
    for y in range(h):
        base.putpixel((0, y), _lerp(top, bottom, y / max(1, h - 1)))
    return base.resize((w, h))


def generate_subscription_photo(used_gb, limit_gb, days_remaining, carry_gb,
                                status_str, username, expire_ts=0) -> bytes:
    """Render the subscription card. Returns PNG bytes.

    days_remaining: int, or a Persian string («نامحدود» / «پایان یافته»).
    expire_ts: unix seconds for the Jalali expiry row (0/None = none).
    """
    S = 2  # supersample for crisp output
    W, H = 1000 * S, 560 * S
    M = 48 * S

    def F(sz, w="r"):
        try:
            return ImageFont.truetype(FONTS.get(w, FONTS["r"]), sz * S)
        except IOError:
            return ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", sz * S)

    unlimited = (limit_gb is None) or (isinstance(limit_gb, (int, float)) and limit_gb <= 0)
    used_gb = float(used_gb or 0)
    rem_gb = None if unlimited else max(0.0, float(limit_gb) - used_gb)
    frac_used = 0.0 if unlimited else min(1.0, used_gb / float(limit_gb))
    days_num = days_remaining if isinstance(days_remaining, (int, float)) else None
    expired = isinstance(days_remaining, str) and "پایان" in days_remaining

    # Health accent (same semantics as the dashboard's ok/warn/bad).
    if unlimited:
        accent = _BLUE
    elif expired or frac_used >= 0.9 or (days_num is not None and days_num < 3):
        accent = _BAD
    elif frac_used >= 0.7 or (days_num is not None and days_num < 7):
        accent = _WARN
    else:
        accent = _OK

    img = _gradient((W, H), _BG_TOP, _BG_BOTTOM)

    # Soft accent glow, top-right.
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([W - 360 * S, -200 * S, W + 160 * S, 320 * S], fill=accent + (38,))
    img = Image.alpha_composite(
        img.convert("RGBA"), glow.filter(ImageFilter.GaussianBlur(80 * S))).convert("RGB")
    d = ImageDraw.Draw(img, "RGBA")

    # Glass panel.
    d.rounded_rectangle([M, M, W - M, H - M], radius=36 * S, fill=(255, 255, 255, 12))
    d.rounded_rectangle([M, M, W - M, H - M], radius=36 * S,
                        outline=(255, 255, 255, 28), width=2 * S)

    # Header: sub name (right, RTL) + wordmark (left).
    pad = M + 40 * S
    d.text((W - pad, M + 46 * S), str(username), font=F(38, "b"), fill=_WHITE,
           anchor="rm", direction="rtl")
    d.text((W - pad, M + 92 * S), "مدیریت اشتراک", font=F(19, "r"), fill=_MUTED,
           anchor="rm", direction="rtl")
    d.ellipse([pad, M + 42 * S, pad + 16 * S, M + 58 * S], fill=accent)
    d.text((pad + 28 * S, M + 50 * S), "AstroByte", font=F(22, "m"),
           fill=(199, 204, 214), anchor="lm", direction="ltr")

    # Donut (left): flat track + accent arc; center shows REMAINING.
    cx, cy, R, tw = 250 * S, 350 * S, 132 * S, 30 * S
    bbox = [cx - R, cy - R, cx + R, cy + R]
    d.arc(bbox, 0, 360, fill=_TRACK, width=tw)
    if not unlimited and frac_used > 0:
        end = -90 + 360 * max(0.012, frac_used)
        d.arc(bbox, -90, end, fill=accent, width=tw)
    if unlimited:
        d.text((cx, cy - 12 * S), "∞", font=F(60, "b"), fill=_WHITE, anchor="mm", direction="rtl")
        d.text((cx, cy + 40 * S), "نامحدود", font=F(20, "r"), fill=_MUTED, anchor="mm", direction="rtl")
    else:
        d.text((cx, cy - 16 * S), _fmt_gb(rem_gb), font=F(58, "b"), fill=_WHITE,
               anchor="mm", direction="rtl")
        d.text((cx, cy + 38 * S), "گیگ مانده", font=F(21, "r"), fill=_MUTED,
               anchor="mm", direction="rtl")

    # Stat rows (right, RTL) with dividers fading toward the donut.
    if isinstance(days_remaining, str):
        days_value = days_remaining
    else:
        days_value = f"{_fa_num(int(days_remaining))} روز"
    rows = [
        ("مصرف‌شده", f"{_fmt_gb(used_gb)} از {'∞' if unlimited else _fmt_gb(limit_gb)} گیگ"),
        ("باقی‌مانده", "نامحدود" if unlimited else f"{_fmt_gb(rem_gb)} گیگ"),
        ("روزهای باقی‌مانده", days_value),
        ("تاریخ انقضا", _jalali_date(expire_ts) if expire_ts else "—"),
    ]
    rx = W - pad
    y = 200 * S
    gap = 84 * S
    x_left = M + 30 * S
    full_at = cx + R + 70 * S
    for label, value in rows:
        d.text((rx, y), label, font=F(19, "r"), fill=_MUTED, anchor="rm", direction="rtl")
        d.text((rx, y + 34 * S), value, font=F(30, "b"), fill=_WHITE, anchor="rm", direction="rtl")
        ly = y + 64 * S
        steps = 150
        for i in range(steps):
            xa = rx - (rx - x_left) * i / steps
            xb = rx - (rx - x_left) * (i + 1) / steps
            t = max(0.0, min(1.0, (xa - x_left) / (full_at - x_left)))
            a = int(24 * t)
            if a:
                d.line([xb, ly, xa, ly], fill=(255, 255, 255, a), width=1 * S)
        y += gap

    img = img.resize((W // S, H // S), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
