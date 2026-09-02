import asyncio
from concurrent.futures import ProcessPoolExecutor
from typing import Any, Dict

_executor: ProcessPoolExecutor | None = None


def _ensure_executor() -> ProcessPoolExecutor:
    global _executor
    if _executor is None:
        # Small pool to avoid CPU starvation
        _executor = ProcessPoolExecutor(max_workers=2)
    return _executor


def _render_subscription_photo_task(kwargs: Dict[str, Any]) -> bytes:
    # Imported inside the child process to avoid forking heavy state
    from app.handlers.user.my_services.chart_generator import generate_subscription_photo
    return generate_subscription_photo(
        kwargs["used_gb"],
        kwargs["limit_gb"],
        kwargs["days_remaining"],
        kwargs["carry_gb"],
        kwargs["status_str"],
        kwargs["username"],
        expire_ts=kwargs.get("expire_ts") or 0,
    )


async def render_subscription_photo_async(**kwargs: Any) -> bytes:
    loop = asyncio.get_running_loop()
    executor = _ensure_executor()
    return await loop.run_in_executor(executor, _render_subscription_photo_task, kwargs)


def _warm_task() -> bool:
    """Import the renderer inside the worker so the first real one is cheap."""
    from app.handlers.user.my_services import chart_generator  # noqa: F401
    return True


async def warm_up() -> None:
    """Boot the render pool before a customer needs it.

    The pool starts lazily, and with the `forkserver` start method the first
    call spawns a fresh interpreter that re-imports the app: measured 7.2s,
    against 0.35s once warm. Opening a subscription awaits this render, so
    without warming, the first person to open one after every restart waits
    seven seconds. Called as a background task at startup; failure is
    harmless, the pool just stays cold.
    """
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(_ensure_executor(), _warm_task)
