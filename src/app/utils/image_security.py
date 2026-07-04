"""Server-side image sanitisation for every user/admin upload.

Threat model
------------
A magic-byte check (the first few bytes look like a JPEG/PNG) is *not* proof
that a file is a harmless image. An attacker can craft a **polyglot**: a file
that begins with a genuine image header but carries a payload appended after
the image data, embedded in a metadata field (EXIF/XMP/ICC), or hidden in an
extra stream. Such a file sails through any header sniff, because it really is
a valid image at the start. It can also be a decompression bomb — a tiny file
that expands to gigabytes of pixels and exhausts memory.

Defence
-------
Do not trust the uploaded bytes at all. Decode the pixels with Pillow and build
a brand-new file from those pixels alone. Everything that is not pixel data —
trailing bytes, all metadata, additional frames/streams — is dropped, because
we never copy it forward. Bombs are refused by a hard pixel ceiling checked
before we allocate the full raster.

Every upload handler must route bytes through :func:`sanitize_image` and store
(and forward) only what it returns.
"""

from __future__ import annotations

import io

from PIL import Image

# Refuse absurdly large rasters before allocating buffers for them. A phone
# screenshot receipt is well under 15MP; 40MP leaves generous headroom while
# still stopping decompression-bomb inputs.
Image.MAX_IMAGE_PIXELS = 40_000_000

# Long-edge ceiling for the *output* image. Also bounds the pixel buffer we
# build during re-encode, so a valid-but-huge image can't be a memory DoS.
_MAX_DIM = 6000
_JPEG_QUALITY = 88

# Only these decoders are ever invoked. Vector formats (e.g. SVG) are absent on
# purpose: they are XML documents that can carry script and must never be
# treated as trustworthy "images".
_ALLOWED_INPUT_FORMATS = {"JPEG", "JPG", "MPO", "PNG", "WEBP"}


class ImageRejected(Exception):
    """Raised when an upload cannot be proven to be a safe raster image.

    ``code`` is a short machine-readable reason (``empty``, ``too_large``,
    ``unsupported_format``, ``too_many_pixels``, ``undecodable``,
    ``reencode_failed``) suitable for returning as an API error detail.
    """

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def sanitize_image(raw: bytes, max_bytes: int) -> tuple[bytes, str, str]:
    """Validate and re-encode ``raw`` into a clean image.

    Returns ``(clean_bytes, ext, mime)`` where ``ext`` is ``"jpg"`` or
    ``"png"`` and ``mime`` the matching type. The result is a freshly encoded
    image containing pixel data only — no source metadata and no trailing
    bytes. Raises :class:`ImageRejected` for anything that is empty, oversized,
    a non-allowed format, a decompression bomb, or otherwise not decodable.
    """
    if not raw:
        raise ImageRejected("empty")
    if len(raw) > max_bytes:
        raise ImageRejected("too_large")

    # Pass 1 — integrity/format probe. verify() detects truncated or corrupt
    # files but leaves the object unusable, so pixels are decoded in pass 2.
    try:
        with Image.open(io.BytesIO(raw)) as probe:
            fmt = (probe.format or "").upper()
            probe.verify()
    except Image.DecompressionBombError:
        raise ImageRejected("too_many_pixels")
    except Exception:
        raise ImageRejected("undecodable")

    if fmt not in _ALLOWED_INPUT_FORMATS:
        raise ImageRejected("unsupported_format")

    # Pass 2 — decode the actual pixels.
    try:
        src = Image.open(io.BytesIO(raw))
        src.load()
    except Image.DecompressionBombError:
        raise ImageRejected("too_many_pixels")
    except Exception:
        raise ImageRejected("undecodable")

    try:
        has_alpha = src.mode in ("RGBA", "LA") or (src.mode == "P" and "transparency" in src.info)
        if has_alpha:
            target_mode, out_format, ext, mime = "RGBA", "PNG", "png", "image/png"
        else:
            target_mode, out_format, ext, mime = "RGB", "JPEG", "jpg", "image/jpeg"

        try:
            converted = src.convert(target_mode)
        except Exception:
            raise ImageRejected("undecodable")

        # Bound output size (and thus the buffer built below).
        if converted.width > _MAX_DIM or converted.height > _MAX_DIM:
            converted.thumbnail((_MAX_DIM, _MAX_DIM))

        # Rebuild into a brand-new image so nothing from the source ``info``
        # dict (EXIF, ICC, PNG text chunks, ...) can ride along. paste() copies
        # the pixel buffer at the C level — unlike a getdata()/putdata() round
        # trip, it does not materialise a Python list of every pixel.
        clean = Image.new(target_mode, converted.size)
        clean.paste(converted)
    finally:
        src.close()

    out = io.BytesIO()
    try:
        if out_format == "JPEG":
            clean.save(out, format="JPEG", quality=_JPEG_QUALITY, optimize=True)
        else:
            clean.save(out, format="PNG", optimize=True)
    except Exception:
        raise ImageRejected("reencode_failed")

    data = out.getvalue()
    if not data:
        raise ImageRejected("reencode_failed")
    # Re-encoded output is normally smaller than the input; this only trips on
    # pathological inputs and keeps the on-disk guarantee identical to intake.
    if len(data) > max_bytes:
        raise ImageRejected("too_large")
    return data, ext, mime
