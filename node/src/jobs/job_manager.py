import asyncio
import logging
from typing import Callable, Awaitable

logger = logging.getLogger(__name__)


class AsyncIOJobManager:
    def __init__(self) -> None:
        self._pending_task: asyncio.Task | None = None

    def schedule_job(self, delay: float, callback: Callable[[], Awaitable[None]]) -> None:
        self.cancel_job()
        self._pending_task = asyncio.create_task(self._run_after(delay, callback))

    def cancel_job(self) -> None:
        if self._pending_task and not self._pending_task.done():
            self._pending_task.cancel()
            self._pending_task = None

    def is_job_pending(self) -> bool:
        return self._pending_task is not None and not self._pending_task.done()

    async def _run_after(self, delay: float, callback: Callable[[], Awaitable[None]]) -> None:
        try:
            await asyncio.sleep(delay)
            self._pending_task = None
            await callback()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Scheduled job error: {e}", exc_info=True)
