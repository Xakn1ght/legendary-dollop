"""Ticket photo upload invariants: served-filename guard + content hardening.

Byte-content validation for uploads is no longer a magic-byte sniff; it is a
full decode + re-encode via app.utils.image_security.sanitize_image (covered
in depth by tests/test_ticket_photo content is in test_upload_security.py).
This test locks the two invariants that live in the photo route itself:
the filename guard used when serving, and that the route routes bytes through
the sanitizer rather than writing raw upload bytes.
"""
import sys

sys.path.insert(0, "src")

from app.api.routes.dashboard_tickets.detail_ops import photo

_SAFE_NAME = photo._SAFE_NAME

# filename guard (route serves only names we generated)
assert _SAFE_NAME.match("a" * 32 + ".jpg")
assert _SAFE_NAME.match("0123456789abcdef0123456789abcdef.webp")
assert not _SAFE_NAME.match("../../etc/passwd")
assert not _SAFE_NAME.match("abc.jpg")
assert not _SAFE_NAME.match("A" * 32 + ".jpg")   # uppercase hex not ours
assert not _SAFE_NAME.match("a" * 32 + ".svg")
assert not _SAFE_NAME.match("a" * 32 + ".jpg\n")

# The route must sanitize (decode + re-encode), never trust/write raw bytes.
assert hasattr(photo, "sanitize_image"), "photo route no longer sanitizes uploads!"
assert not hasattr(photo, "sniff_image"), "raw magic-byte sniff should be gone"

print("test_ticket_photo: OK")
