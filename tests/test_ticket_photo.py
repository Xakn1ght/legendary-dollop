"""Validation core of ticket photo uploads: magic-byte sniffing + filename guard."""
import sys

sys.path.insert(0, "src")

from app.api.routes.dashboard_tickets.detail_ops.photo import _SAFE_NAME, sniff_image

# magic bytes
assert sniff_image(b"\xff\xd8\xff\xe0" + b"\x00" * 12) == ("jpg", "image/jpeg")
assert sniff_image(b"\x89PNG\r\n\x1a\n" + b"\x00" * 8) == ("png", "image/png")
assert sniff_image(b"RIFF\x00\x00\x00\x00WEBPVP8 ") == ("webp", "image/webp")
assert sniff_image(b"GIF89a" + b"\x00" * 10) == (None, None)          # gif rejected
assert sniff_image(b"<svg xmlns='http://www.w3'") == (None, None)     # svg/XSS rejected
assert sniff_image(b"") == (None, None)

# filename guard (route serves only names we generated)
assert _SAFE_NAME.match("a" * 32 + ".jpg")
assert _SAFE_NAME.match("0123456789abcdef0123456789abcdef.webp")
assert not _SAFE_NAME.match("../../etc/passwd")
assert not _SAFE_NAME.match("abc.jpg")
assert not _SAFE_NAME.match("A" * 32 + ".jpg")   # uppercase hex not ours
assert not _SAFE_NAME.match("a" * 32 + ".svg")
assert not _SAFE_NAME.match("a" * 32 + ".jpg\n")

print("test_ticket_photo: OK")
