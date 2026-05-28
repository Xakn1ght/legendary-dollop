def _ua_short(ua: str) -> str:
    ua = (ua or "").strip()
    if not ua:
        return "Unknown"
    return ua[:180]
