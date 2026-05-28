import math
import os
import random
import tempfile
import time
from io import BytesIO
from typing import List

from PIL import Image, ImageDraw, ImageFont

from .constants import BG_COLOR, CHART_CONFIG, FONT_PATHS, GIF_SETTINGS, TEXT_CONFIG
from .utils import _load_font, _measure_text, _to_persian_digits


def _generate_subscription_frames(used_gb, limit_gb, days_remaining, carry_gb, status_str, username) -> List[Image.Image]:
    """Generate PIL frames for the animated subscription chart.

    Returns a list of RGB PIL.Image frames that can be encoded as GIF/MP4.
    """
    # ═══════════════════════════════════════════════════════════════
    # EASY ADJUSTMENT SETTINGS - Change these to reposition elements
    # ═══════════════════════════════════════════════════════════════
    size = CHART_CONFIG["size"]                      # Image size
    center = size // 2              # Center point
    radius = CHART_CONFIG["radius"]                    # Circle radius

    # TEXT POSITIONS (adjust these easily!)
    username_y = TEXT_CONFIG["username_y"]                 # Username Y position (higher = smaller number)
    usage_y_offset = TEXT_CONFIG["usage_y_offset"]            # Usage text distance BELOW circle edge (increase to move down)
    bottom_row_y = TEXT_CONFIG["bottom_row_y"]        # Bottom row Y position (increase to move up)
    left_padding = TEXT_CONFIG["left_padding"]               # Left side padding
    right_padding = TEXT_CONFIG["right_padding"]              # Right side padding

    # FONT SIZES
    username_size = TEXT_CONFIG["username_size"]              # Username font size (increased for better visibility)
    percentage_size = TEXT_CONFIG["percentage_size"]            # Center percentage size
    usage_size = TEXT_CONFIG["usage_size"]                 # Middle usage text size
    bottom_info_size = TEXT_CONFIG["bottom_info_size"]           # Bottom row text size

    # ═══════════════════════════════════════════════════════════════

    # Load fonts
    try:
        font_path = FONT_PATHS["primary"]
        font_title = ImageFont.truetype(font_path, username_size)
        font_large = ImageFont.truetype(font_path, percentage_size)
        font_usage = ImageFont.truetype(font_path, usage_size)
        font_info = ImageFont.truetype(font_path, bottom_info_size)
    except IOError:
        try:
            font_title = ImageFont.truetype(FONT_PATHS["fallback"], username_size)
            font_large = ImageFont.truetype(FONT_PATHS["fallback"], percentage_size)
            font_usage = ImageFont.truetype(FONT_PATHS["backup"], usage_size)
            font_info = ImageFont.truetype(FONT_PATHS["backup"], bottom_info_size)
        except IOError:
            font_title = font_large = font_usage = font_info = ImageFont.load_default()

    # Reduce frames from 30 to 20 for faster generation (still smooth)
    frames: List[Image.Image] = []
    num_frames = CHART_CONFIG["frames"]

    # Pre-generate star positions (fixed across frames) - reduce count for speed
    random.seed(42)  # Fixed seed for consistent stars across regenerations
    stars = [(random.randint(0, size), random.randint(0, size), random.randint(1, 3), random.random()) for _ in range(CHART_CONFIG["star_count"])]

    # Pre-generate bubble positions and properties for seamless loop
    # Distribute bubbles evenly across the center area
    bubbles = []
    for i in range(CHART_CONFIG["bubble_count"]):  # More bubbles for better distribution
        # Distribute horizontally - center-focused for balanced appearance
        px = random.randint(size // 4, size - size // 4)  # Centered distribution
        # Distribute vertically across the full height for better coverage
        py_base = random.randint(0, size)
        # Vary bubble sizes for visual interest
        pr = random.randint(4, 8)
        # Random phase for natural movement timing
        phase = random.random() * 2 * math.pi
        bubbles.append((px, py_base, pr, phase))
    random.seed()  # Reset seed

    unlimited = (limit_gb is None) or (isinstance(limit_gb, (int, float)) and limit_gb == 0)

    for frame_idx in range(num_frames):
        img = Image.new('RGB', (size, size), color=BG_COLOR)
        draw = ImageDraw.Draw(img)

        # Animation progress (0 to 2*pi for perfect loop)
        t = (frame_idx / num_frames) * 2 * math.pi

        # Animate stars with twinkling (seamless)
        for star in stars:
            x, y, sz, phase = star
            # Twinkling effect with phase offset for variety
            alpha = 100 + int(155 * (0.5 + 0.5 * math.sin(t + phase * 2 * math.pi)))
            draw.ellipse((x, y, x+sz, y+sz), fill=(255, 255, 255))

        # Draw liquid gradient circles with seamless pulsing
        pulse = math.sin(t) * 3
        for i in range(4):
            r = 270 - i * 10 + int(pulse * (i + 1) * 0.5)
            color_val = 50 + i * 10
            draw.ellipse((center - r, center - r, center + r, center + r),
                        fill=(color_val//2, color_val//2, color_val))

        # Calculate percentage (skip for unlimited)
        percent = (used_gb / limit_gb) if (not unlimited and limit_gb > 0) else 0

        # Animated outer glow ring (seamless pulsing) - reduce layers
        glow_offset = math.sin(t) * 2
        for j in range(5):  # Reduce from 8 to 5
            glow_r = radius + 4 + j * 2 + glow_offset
            glow_alpha = int((255 - j * 40) * (0.7 + 0.3 * math.sin(t)))
            draw.ellipse((center - glow_r, center - glow_r, center + glow_r, center + glow_r),
                        outline=(0, 255, 150), width=1)

        # Draw progress arc with seamless liquid wave effect
        # Green = remaining (unused), Dark = used
        if not unlimited:
            remaining_percent = 1 - percent
            if remaining_percent > 0:
                for layer in range(4):  # Reduce from 6 to 4
                    r = radius - layer * 6
                    # Seamless wave animation along the arc
                    angle_offset = layer * 2 + math.sin(t + layer * 0.5) * 3
                    start_angle = 90 + angle_offset
                    end_angle = start_angle - (remaining_percent * 360)
                    color_intensity = 150 + layer * 15 + int(math.sin(t * 0.8) * 10)
                    draw.pieslice((center - r, center - r, center + r, center + r),
                                start=start_angle, end=end_angle,
                                fill=(0, color_intensity, 100 + layer * 10))
        else:
            # For unlimited, draw dual soft pulsing halos to indicate active status
            glow_r1 = radius - 6 + math.sin(t) * 2
            glow_r2 = radius - 16 + math.sin(t * 1.3) * 2
            draw.ellipse((center - glow_r1, center - glow_r1, center + glow_r1, center + glow_r1),
                         outline=(50, 220, 180), width=2)
            draw.ellipse((center - glow_r2, center - glow_r2, center + glow_r2, center + glow_r2),
                         outline=(30, 150, 220), width=1)

        # Draw inner circle with gradient effect - reduce layers
        inner_radius = radius - 40
        for i in range(6):  # Reduce from 10 to 6
            ir = inner_radius - i * 2
            shade = 15 + i * 3
            draw.ellipse((center - ir, center - ir, center + ir, center + ir),
                        fill=(shade, shade, shade + 10))

        # Draw center text: bigger infinity for unlimited
        center_font = font_large
        if unlimited:
            try:
                _f = FONT_PATHS.get("fallback") or FONT_PATHS.get("backup")
                if _f:
                    center_font = ImageFont.truetype(_f, int(percentage_size * 1.2))
            except Exception:
                center_font = font_large
        percent_text = "∞" if unlimited else _to_persian_digits(f"{int(percent*100)}%")
        bbox = draw.textbbox((0, 0), percent_text, font=center_font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        text_x = center - text_width // 2
        text_y = center - text_height // 2

        # Vibrant animated glow effect
        glow_intensity = int(140 + 40 * math.sin(t))  # Dynamic glow
        for offset in [(-2,-2), (2,2), (-2,2), (2,-2)]:
            draw.text((text_x + offset[0], text_y + offset[1]), percent_text,
                     fill=(0, glow_intensity, 180), font=center_font)  # Vibrant teal glow
        # Bright main text
        draw.text((text_x, text_y), percent_text, fill=(50, 255, 180), font=center_font)  # Bright teal

        # === USERNAME (top) - premium white glow effect ===
        bbox = draw.textbbox((0, 0), username, font=font_title)
        username_width = bbox[2] - bbox[0]
        username_x = center - username_width // 2

        # Outer soft glow - creates depth
        for offset in [(3,3), (-3,-3), (3,-3), (-3,3)]:
            draw.text((username_x + offset[0], username_y + offset[1]), username,
                     fill=(40, 100, 180), font=font_title)  # Soft blue distant glow

        # Middle glow layer - adds dimension
        for offset in [(2,2), (-2,-2), (2,-2), (-2,2)]:
            draw.text((username_x + offset[0], username_y + offset[1]), username,
                     fill=(100, 160, 220), font=font_title)  # Medium blue glow

        # Inner bright glow - creates halo effect
        glow_intensity = int(180 + 50 * math.sin(t * 0.8))  # Subtle pulsing glow
        for offset in [(1,1), (-1,-1), (1,-1), (-1,1)]:
            draw.text((username_x + offset[0], username_y + offset[1]), username,
                     fill=(180, 210, glow_intensity), font=font_title)  # Bright inner glow

        # Pure white text - crisp and premium
        draw.text((username_x, username_y), username, fill=(255, 255, 255), font=font_title)  # Pure white

        # (Removed) unlimited label under username per product decision

        # === USAGE TEXT (middle - below circle) - Vibrant with elegant glow ===
        usage_y = center + radius + usage_y_offset
        if unlimited:
            # Mix fonts so the infinity symbol renders crisply
            used_part = _to_persian_digits(f"{used_gb:.1f}")
            latin_part = " / ∞ GB"
            try:
                latin_font = ImageFont.truetype(FONT_PATHS.get("fallback") or FONT_PATHS.get("backup"), usage_size)
            except Exception:
                latin_font = font_usage
            d_bbox = draw.textbbox((0, 0), used_part, font=font_usage)
            l_bbox = draw.textbbox((0, 0), latin_part, font=latin_font)
            total_w = (d_bbox[2] - d_bbox[0]) + (l_bbox[2] - l_bbox[0])
            start_x = center - total_w // 2
            for offset in [(1,1), (-1,-1)]:
                draw.text((start_x + offset[0], usage_y + offset[1]), used_part, fill=(100,160,255), font=font_usage)
                draw.text((start_x + (d_bbox[2]-d_bbox[0]) + offset[0], usage_y + offset[1]), latin_part, fill=(100,160,255), font=latin_font)
            draw.text((start_x, usage_y), used_part, fill=(180,230,255), font=font_usage)
            draw.text((start_x + (d_bbox[2]-d_bbox[0]), usage_y), latin_part, fill=(180,230,255), font=latin_font)
        else:
            usage_text = _to_persian_digits(f"{used_gb:.1f} / {limit_gb:.1f} GB")
            bbox = draw.textbbox((0, 0), usage_text, font=font_usage)
            usage_width = bbox[2] - bbox[0]
            usage_x = center - usage_width // 2
            for offset in [(1,1), (-1,-1), (1,-1), (-1,1)]:
                draw.text((usage_x + offset[0], usage_y + offset[1]), usage_text,
                         fill=(100, 160, 255), font=font_usage)
            draw.text((usage_x, usage_y), usage_text, fill=(180, 230, 255), font=font_usage)

        # === BOTTOM ROW (days left + carry GB) - vibrant colors ===
        # If days_remaining is a string like "نامحدود", show as is (no "روز")
        if isinstance(days_remaining, str):
            days_text = _to_persian_digits(days_remaining)
        else:
            days_text = _to_persian_digits(f"{days_remaining} روز")
        # Add vibrant glow effect
        for offset in [(1,1), (-1,-1)]:
            draw.text((left_padding + offset[0], bottom_row_y + offset[1]), days_text,
                     fill=(230, 180, 80), font=font_info, anchor="ls")  # Golden glow
        draw.text((left_padding, bottom_row_y), days_text, fill=(255, 220, 120), font=font_info, anchor="ls")  # Warm gold

        # Hide carry for unlimited
        if not unlimited:
            carry_text = _to_persian_digits(f"{carry_gb:.1f} GB")
            # Add vibrant glow effect
            for offset in [(1,1), (-1,-1)]:
                bbox_carry = draw.textbbox((0, 0), carry_text, font=font_info)
                carry_width = bbox_carry[2] - bbox_carry[0]
                draw.text((size - right_padding + offset[0], bottom_row_y + offset[1]), carry_text,
                         fill=(80, 200, 220), font=font_info, anchor="rs")  # Turquoise glow
            draw.text((size - right_padding, bottom_row_y), carry_text, fill=(130, 240, 255), font=font_info, anchor="rs")  # Bright cyan

        # Seamless floating bubbles (constant speed, perfect loop)
        for idx, bubble in enumerate(bubbles):
            px, py_base, pr, phase = bubble
            # Calculate position based on normalized time (0 to 1) for perfect loop
            progress = (frame_idx / num_frames + phase / (2 * math.pi)) % 1.0
            # Linear vertical movement for seamless loop
            animated_y = py_base - (progress * size)
            # Wrap around seamlessly
            if animated_y < -pr:
                animated_y += size + pr * 2
            # Horizontal sway for organic feel (also seamless)
            sway = math.sin(t * 2 + phase) * 10
            # More colorful bubbles - different colors based on position
            bubble_color = (
                100 + int(50 * math.sin(phase * 3)),
                180 + int(70 * math.sin(t + phase)),
                220 + int(35 * math.sin(t * 1.5 + phase))
            )
            draw.ellipse((px + sway, animated_y, px + pr + sway, animated_y + pr),
                        fill=bubble_color)

        # Add colorful corner accents - all four corners with different colors
        accent_size = TEXT_CONFIG["accent_size"]

        # Animated corner colors for visual interest
        corner_r = 100 + int(50 * math.sin(t * 0.7))
        corner_g = 180 + int(70 * math.sin(t * 1.3))
        corner_b = 220 + int(35 * math.sin(t))

        # Top-left corner - magenta
        draw.arc((13, 13, 13 + accent_size, 13 + accent_size),
                start=180, end=270, fill=(220, 100, 255), width=2)
        # Top-right corner - cyan
        draw.arc((size - accent_size - 13, 13, size - 13, 13 + accent_size),
                start=270, end=360, fill=(0, 220, 255), width=2)
        # Bottom-left corner - gold
        draw.arc((13, size - accent_size - 13, 13 + accent_size, size - 13),
                start=90, end=180, fill=(255, 200, 100), width=2)
        # Bottom-right corner - animated color
        draw.arc((size - accent_size - 13, size - accent_size - 13, size - 13, size - 13),
                start=0, end=90, fill=(corner_r, corner_g, corner_b), width=2)

        # Footer: last update time
        try:
            ts = time.strftime("%H:%M:%S")
            foot = _to_persian_digits(f"به‌روزرسانی: {ts}")
            fnt = ImageFont.truetype(FONT_PATHS.get("backup") or FONT_PATHS.get("fallback"), 18) if FONT_PATHS.get("backup") or FONT_PATHS.get("fallback") else font_info
            draw.text((14, size - 24), foot, fill=(120, 140, 160), font=fnt)
        except Exception:
            pass

        frames.append(img)

    return frames


def generate_subscription_chart(used_gb, limit_gb, days_remaining, carry_gb, status_str, username):
    """Generate an animated GIF for the subscription chart (backward compatible)."""
    frames = _generate_subscription_frames(
        used_gb, limit_gb, days_remaining, carry_gb, status_str, username
    )
    img_io = BytesIO()
    frames[0].save(
        img_io,
        format='GIF',
        save_all=True,
        append_images=frames[1:],
        duration=GIF_SETTINGS["duration"],
        loop=GIF_SETTINGS["loop"],
        optimize=GIF_SETTINGS["optimize"],
        disposal=GIF_SETTINGS["disposal"]
    )
    img_io.seek(0)
    return img_io.getvalue()


def generate_subscription_video_mp4(used_gb, limit_gb, days_remaining, carry_gb, status_str, username) -> bytes:
    """Generate an MP4 (H.264) animation for the subscription chart.

    Encodes frames with imageio-ffmpeg to a temporary file and returns bytes.
    """
    import imageio
    import numpy as np

    frames = _generate_subscription_frames(
        used_gb, limit_gb, days_remaining, carry_gb, status_str, username
    )

    fps = int(1000 / max(1, GIF_SETTINGS["duration"]))  # duration ms per frame -> fps

    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = os.path.join(tmpdir, "chart.mp4")
        writer = imageio.get_writer(
            out_path,
            fps=fps,
            codec="libx264",
            quality=9,
            pixelformat="yuv420p",
        )
        try:
            for frame in frames:
                writer.append_data(np.array(frame))
        finally:
            writer.close()

        with open(out_path, "rb") as f:
            return f.read()
