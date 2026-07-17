# Fixed country order for legend (always show, even if 0%)
COUNTRY_ORDER: list[str] = [
    "United Kingdom",
    "Netherlands",
    "Switzerland",
    "Germany",
    "Canada",
    "Turkey",
    "France",
    "Other",
    "USA",
    "UAE",
]

# Stable colors per country for both slices and legend
COUNTRY_COLORS: dict[str, tuple[int, int, int]] = {
    "Switzerland": (46, 204, 113),   # green
    "Germany": (52, 152, 219),       # blue
    "Other": (241, 196, 15),         # yellow
    "Netherlands": (231, 76, 60),    # red
    "Turkey": (155, 89, 182),        # purple
    "USA": (230, 126, 34),           # orange
    "UAE": (22, 160, 133),           # teal
    "France": (127, 140, 141),       # gray
    "United Kingdom": (189, 195, 199),
    "Canada": (26, 188, 156),
}

# Handle multiple label variants to be more forgiving (with / without emojis)
_MY_SERVICE_LABELS = {
    'سرویس های من🛍',
    'سرویس های من',
    '🎁 سرویس های من',
    '🎁سرویس های من',
    'مدیریت سرویس👨‍💻',
}

# Status mappings for subscription display
STATUS_MAP = {
    "active": "فعال ✅",
    "disabled": "غیرفعال 🚫",
    "limited": "محدود ⚠️",
    "expired": "منقضی 🔚",
    "on_hold": "در انتظار ⏳"
}

STATUS_MAP_NO_EMOJI = {
    "active": "فعال",
    "disabled": "غیرفعال",
    "limited": "محدود",
    "expired": "منقضی",
    "on_hold": "در انتظار"
}

# Usage chart dimensions and settings
USAGE_CHART_CONFIG = {
    "width": 1920,
    "height": 1080,
    "title_font_size_ratio": 0.040,
    "center_font_size_ratio": 0.034,
    "legend_font_size_ratio": 0.040,
    "margin": 40,
    "legend_width": 460,
    "hole_ratio": 0.6,
    "box_size": 30,
    "spacing": 25,
}

# Colors for usage chart legend and slices
USAGE_CHART_COLORS = [
    (46, 204, 113),  # green
    (52, 152, 219),  # blue
    (241, 196, 15),  # yellow
    (231, 76, 60),   # red
    (155, 89, 182),  # purple
    (230, 126, 34),  # orange
    (22, 160, 133),  # teal
    (127, 140, 141), # gray
]

# Background and text colors for usage chart
USAGE_CHART_COLORS_CONFIG = {
    "bg_color": (28, 31, 34),
    "fg_text": (240, 240, 240),
}
