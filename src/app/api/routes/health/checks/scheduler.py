"""APScheduler probe."""

from typing import Any, Dict

from aiohttp import web


async def check_scheduler_health(request: web.Request) -> Dict[str, Any]:
    """Check scheduler status and pending jobs."""
    try:
        scheduler = request.app.get("scheduler")

        if not scheduler:
            return {
                "status": "unavailable",
                "error": "Scheduler not found",
            }

        is_running = scheduler.running

        jobs = scheduler.get_jobs()
        pending_jobs = len(jobs)

        job_list = []
        for job in jobs:
            job_list.append(
                {
                    "id": job.id,
                    "name": job.name or job.id,
                    "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                }
            )

        return {
            "status": "running" if is_running else "stopped",
            "pending_jobs": pending_jobs,
            "jobs": job_list[:5],
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "pending_jobs": 0,
        }
