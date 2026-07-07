from app.utils.image_security import ImageRejected, sanitize_image

from .common import *  # noqa: F403
from .common import _UPLOAD_DIR, _load_settings, _save_settings  # underscore names aren't star-exported


async def handle_admin_ui_get_settings(request: web.Request):
    settings = _load_settings()
    return web.json_response({"ok": True, "settings": settings})


async def handle_admin_ui_set_settings(request: web.Request):
    try:
        payload = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid_json"}, status=400)

    if not isinstance(payload, dict):
        return web.json_response({"ok": False, "error": "invalid_payload"}, status=400)

    # Keep only known namespaces to avoid storing unexpected junk
    allowed_keys = {"v3"}
    incoming = {k: v for k, v in payload.items() if k in allowed_keys and isinstance(v, dict)}

    settings = _load_settings()
    settings.update(incoming)
    _save_settings(settings)
    return web.json_response({"ok": True})


async def handle_admin_ui_upload_background(request: web.Request):
    """
    Multipart upload:
      - field: file
    Returns:
      - { ok: true, url: "/admin/uploads/<name>" }

    The client-declared Content-Type is not trusted: bytes are buffered (with a
    hard cap), decoded, and re-encoded through sanitize_image, so only a clean
    raster with a server-chosen extension ever reaches disk.
    """
    max_bytes = 5 * 1024 * 1024  # 5MB
    try:
        reader = await request.multipart()
        field = await reader.next()
        if not field or field.name != "file":
            return web.json_response({"ok": False, "error": "missing_file"}, status=400)

        data = bytearray()
        while True:
            chunk = await field.read_chunk(size=64 * 1024)
            if not chunk:
                break
            data.extend(chunk)
            if len(data) > max_bytes:
                return web.json_response({"ok": False, "error": "file_too_large"}, status=400)

        try:
            clean, ext, _mime = sanitize_image(bytes(data), max_bytes)
        except ImageRejected as e:
            return web.json_response({"ok": False, "error": "unsupported_type", "detail": e.code}, status=400)

        safe_name = f"bg_{secrets.token_hex(8)}.{ext}"
        os.makedirs(_UPLOAD_DIR, exist_ok=True)
        out_path = os.path.join(_UPLOAD_DIR, safe_name)
        with open(out_path, "wb") as f:
            f.write(clean)

        return web.json_response({"ok": True, "url": f"/admin/uploads/{safe_name}"})
    except Exception:
        return web.json_response({"ok": False, "error": "upload_failed"}, status=500)

