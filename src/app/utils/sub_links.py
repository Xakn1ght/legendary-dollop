"""Public subscription-link normalization (bakbot parity, 2026-07-13).

PasarGuard returns subscription_url as a RELATIVE path ("/sub/<token>") — sent
raw to users it is a dead string (Pasha screenshot: "/sub/aDZ..."). Every
user-facing surface must host the token on the public SUBLINK domain instead,
exactly like the dashboard API and bakbot's _pasarguard_base_link do.
"""
from app.core.settings import SUBLINK


def public_sub_url(subscription_url: str | None = None, token: str | None = None) -> str | None:
    """Return https://<SUBLINK>/<token> from a token or any panel URL/path.

    Never returns the panel host — unknown/absent token yields None so the
    caller can drop the link line instead of showing something broken.
    """
    tok = (token or "").strip()
    if not tok:
        raw = str(subscription_url or "").strip().split("#", 1)[0]
        if "/sub/" in raw:
            tok = raw.split("/sub/", 1)[1].strip("/").split("/")[0]
    if not tok:
        return None
    base = (SUBLINK or "").strip().rstrip("/")
    if not base:
        return None
    if not base.startswith(("http://", "https://")):
        base = "https://" + base
    return f"{base}/{tok}"
