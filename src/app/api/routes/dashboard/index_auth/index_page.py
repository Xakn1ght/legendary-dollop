from ..common import *  # noqa: F403


async def handle_dashboard_index(request: web.Request):
    """
    Dashboard entrypoint.
    """
    # React shell (frontend/ workspace)
    # Avoid stale cached JS causing auth / UI issues
    resp = web.FileResponse(path=webapp_path("dashboard", "react", "index.html"))
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp
