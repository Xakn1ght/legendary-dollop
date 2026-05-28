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


def _render_subscription_video_task(kwargs: Dict[str, Any]) -> bytes:
    # Imported inside the child process to avoid forking heavy state
    from app.handlers.user.my_services.chart_generator import (
        generate_subscription_video_mp4,
    )
    return generate_subscription_video_mp4(
        kwargs["used_gb"],
        kwargs["limit_gb"],
        kwargs["days_remaining"],
        kwargs["carry_gb"],
        kwargs["status_str"],
        kwargs["username"],
    )


async def render_subscription_video_async(**kwargs: Any) -> bytes:
    loop = asyncio.get_running_loop()
    executor = _ensure_executor()
    return await loop.run_in_executor(executor, _render_subscription_video_task, kwargs)


def _render_subscription_gif_task(kwargs: Dict[str, Any]) -> bytes:
    from app.handlers.user.my_services.chart_generator import generate_subscription_chart
    return generate_subscription_chart(
        kwargs["used_gb"],
        kwargs["limit_gb"],
        kwargs["days_remaining"],
        kwargs["carry_gb"],
        kwargs["status_str"],
        kwargs["username"],
    )


async def render_subscription_gif_async(**kwargs: Any) -> bytes:
    loop = asyncio.get_running_loop()
    executor = _ensure_executor()
    return await loop.run_in_executor(executor, _render_subscription_gif_task, kwargs)


