import asyncio
import logging

from backend.worker.service import WorkerService


def run_worker() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    service = WorkerService()

    async def _run() -> None:
        try:
            await service.start()
        except asyncio.CancelledError:
            await service.shutdown()

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        logging.info("Worker stopped by user")
