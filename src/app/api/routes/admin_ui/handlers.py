from .common import *  # noqa: F403


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
    """
    try:
        reader = await request.multipart()
        field = await reader.next()
        if not field or field.name != "file":
            return web.json_response({"ok": False, "error": "missing_file"}, status=400)

        filename = (field.filename or "").strip()
        content_type = (field.headers.get("Content-Type") or "").lower()

        # Basic validation
        allowed_types = {"image/png", "image/jpeg", "image/webp"}
        if content_type not in allowed_types:
            return web.json_response({"ok": False, "error": "unsupported_type"}, status=400)

        ext = ".png" if content_type == "image/png" else ".jpg" if content_type == "image/jpeg" else ".webp"
        safe_name = "bg_" + secrets.token_hex(8) + ext

        os.makedirs(_UPLOAD_DIR, exist_ok=True)
        out_path = os.path.join(_UPLOAD_DIR, safe_name)

        size = 0
        max_bytes = 5 * 1024 * 1024  # 5MB
        with open(out_path, "wb") as f:
            while True:
                chunk = await field.read_chunk(size=64 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    try:
                        f.close()
                    except Exception:
                        pass
                    try:
                        os.remove(out_path)
                    except Exception:
                        pass
                    return web.json_response({"ok": False, "error": "file_too_large"}, status=400)
                f.write(chunk)

        return web.json_response({"ok": True, "url": f"/admin/uploads/{safe_name}"})
    except Exception:
        return web.json_response({"ok": False, "error": "upload_failed"}, status=500)

