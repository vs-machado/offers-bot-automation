import asyncio
import logging

from backend.worker.service import WorkerService


def run_worker() -> None:
    """Configure logging and run worker until cancellation or keyboard interrupt."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    service = WorkerService()

    async def _run() -> None:
        try:
            await service.start()
        except asyncio.CancelledError:
            raise
        finally:
            await service.shutdown()

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        logging.info("Worker stopped by user")


if __name__ == "__main__":
    run_worker()
