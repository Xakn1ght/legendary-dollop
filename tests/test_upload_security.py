"""Upload hardening: prove sanitize_image neutralises malicious uploads.

These are the attack classes a magic-byte sniff CANNOT catch, which is exactly
why every upload is now decoded and re-encoded from pixels:

- polyglots: a real image with a payload appended or embedded ("virus mixed
  with a jpeg")
- metadata payloads: script bytes hidden in EXIF/comment fields
- header spoofs: a payload wearing a JPEG/PNG magic prefix but no real pixels
- wrong/vector formats: GIF, SVG (SVG is XML that can carry script)
- decompression bombs: tiny file, enormous raster
- empty / oversized inputs

Run: PYTHONPATH=src python tests/test_upload_security.py
"""
import importlib.util
import io
import os

from PIL import Image

ROOT = os.path.join(os.path.dirname(__file__), "..", "src", "app")


def _load(rel_path, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, rel_path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sec = _load("utils/image_security.py", "image_security")
sanitize_image = sec.sanitize_image
ImageRejected = sec.ImageRejected

MAX = 8 * 1024 * 1024
PHP = b"<?php system($_GET['c']); ?>"
ZIP = b"PK\x03\x04\x14\x00malware.exe"
MARK = b"__PAYLOAD_MARKER__"


def _jpeg(w=64, h=64, color=(200, 30, 30)):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def _png(w=64, h=64, alpha=True):
    buf = io.BytesIO()
    mode = "RGBA" if alpha else "RGB"
    fill = (20, 120, 220, 255) if alpha else (20, 120, 220)
    Image.new(mode, (w, h), fill).save(buf, format="PNG")
    return buf.getvalue()


def _reopens_as(data, fmt):
    with Image.open(io.BytesIO(data)) as im:
        im.load()
        return im.format == fmt


def test_clean_jpeg_passes_and_stays_jpeg():
    clean, ext, mime = sanitize_image(_jpeg(), MAX)
    assert ext == "jpg" and mime == "image/jpeg"
    assert _reopens_as(clean, "JPEG")


def test_clean_png_with_alpha_stays_png():
    clean, ext, mime = sanitize_image(_png(alpha=True), MAX)
    assert ext == "png" and mime == "image/png"
    assert _reopens_as(clean, "PNG")


def test_opaque_png_normalises_to_jpeg():
    # No alpha channel -> smaller JPEG output is fine and expected.
    clean, ext, _ = sanitize_image(_png(alpha=False), MAX)
    assert ext == "jpg"
    assert _reopens_as(clean, "JPEG")


def test_jpeg_with_appended_php_payload_is_stripped():
    """The headline case: valid JPEG bytes with a web-shell glued on the end."""
    polyglot = _jpeg() + PHP + MARK
    clean, _, _ = sanitize_image(polyglot, MAX)
    assert PHP not in clean
    assert MARK not in clean
    assert _reopens_as(clean, "JPEG")


def test_png_with_appended_zip_payload_is_stripped():
    polyglot = _png() + ZIP + MARK
    clean, _, _ = sanitize_image(polyglot, MAX)
    assert ZIP not in clean
    assert MARK not in clean


def test_exif_embedded_payload_is_stripped():
    buf = io.BytesIO()
    exif_blob = b"Exif\x00\x00" + MARK + PHP + (b"\x00" * 32)
    Image.new("RGB", (48, 48), (10, 10, 10)).save(buf, format="JPEG", exif=exif_blob)
    raw = buf.getvalue()
    assert MARK in raw  # payload really is embedded pre-sanitize
    clean, _, _ = sanitize_image(raw, MAX)
    assert MARK not in clean
    assert PHP not in clean


def test_spoofed_jpeg_magic_without_pixels_is_rejected():
    """Old magic-byte check accepted this; decode must reject it."""
    fake = b"\xff\xd8\xff" + b"\x00" * 64 + PHP
    try:
        sanitize_image(fake, MAX)
        assert False, "spoofed header accepted"
    except ImageRejected as e:
        assert e.code in ("undecodable", "unsupported_format")


def test_svg_is_rejected():
    svg = b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>"
    try:
        sanitize_image(svg, MAX)
        assert False, "SVG accepted"
    except ImageRejected:
        pass


def test_gif_is_rejected():
    buf = io.BytesIO()
    Image.new("P", (32, 32)).save(buf, format="GIF")
    try:
        sanitize_image(buf.getvalue(), MAX)
        assert False, "GIF accepted"
    except ImageRejected as e:
        assert e.code == "unsupported_format"


def test_html_disguised_as_image_is_rejected():
    try:
        sanitize_image(b"<html><body><script>evil()</script></body></html>", MAX)
        assert False, "HTML accepted"
    except ImageRejected:
        pass


def test_empty_is_rejected():
    try:
        sanitize_image(b"", MAX)
        assert False
    except ImageRejected as e:
        assert e.code == "empty"


def test_oversized_is_rejected():
    try:
        sanitize_image(_jpeg(), 10)  # 10-byte cap
        assert False
    except ImageRejected as e:
        assert e.code == "too_large"


def test_decompression_bomb_is_rejected():
    """Temporarily lower the pixel ceiling and feed an image above it."""
    original = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = 1024  # 32x32 = 1024 is at the limit; 64x64 is over
    try:
        sanitize_image(_jpeg(64, 64), MAX)
        assert False, "bomb accepted"
    except ImageRejected as e:
        assert e.code == "too_many_pixels"
    finally:
        Image.MAX_IMAGE_PIXELS = original


def test_output_never_exceeds_cap():
    clean, _, _ = sanitize_image(_jpeg(256, 256), MAX)
    assert len(clean) <= MAX


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\nAll {len(fns)} upload-security tests passed.")
