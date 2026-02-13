# Exercise 5.1c — Worker pseudocode
#
# This module is pseudocode per the exercise specification.
# It demonstrates the worker architecture for processing analysis jobs
# with duplicate message handling, distributed locking, and graceful shutdown.
# Dependencies like RedisQueue and Redis are illustrative, not production imports.

import asyncio
import signal
import logging
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


class LockAcquisitionError(Exception):
    """Raised when a distributed lock cannot be acquired."""


class AnalysisWorker:
    def __init__(self, queue, analysis_service, redis, db_session_factory):
        self._queue = queue
        self._service = analysis_service
        self._redis = redis
        self._db_factory = db_session_factory
        self._shutdown_event = asyncio.Event()
        self._current_task: asyncio.Task | None = None

    async def start(self):
        """Main worker loop."""
        # Register signal handlers for graceful shutdown
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._request_shutdown)

        logger.info("Worker started, listening for jobs...")

        while not self._shutdown_event.is_set():
            try:
                # Block for up to 1 second waiting for a job
                # Short timeout lets us check shutdown_event frequently
                job = await self._queue.dequeue(timeout=1.0)
                if job is None:
                    continue  # No job available, loop back

                # Process the job in a tracked task
                self._current_task = asyncio.create_task(
                    self._process_job(job)
                )
                await self._current_task
                self._current_task = None

            except asyncio.CancelledError:
                logger.info("Worker cancelled, shutting down...")
                break
            except Exception:
                logger.exception("Unexpected error in worker loop")
                await asyncio.sleep(1)  # Back off on unexpected errors

        logger.info("Worker stopped gracefully.")

    async def _process_job(self, job):
        """Process a single analysis job with deduplication and error handling."""
        document_id = job["document_id"]
        tenant_id = job["tenant_id"]
        message_id = job["message_id"]

        # ── Deduplication: skip if we've already processed this message ──
        dedup_key = f"analysis:processed:{message_id}"
        already_processed = await self._redis.set(
            dedup_key, "1", nx=True, ex=3600  # SET if Not eXists, expire in 1h
        )
        if not already_processed:
            logger.info(
                "Skipping duplicate message %s for document %s",
                message_id, document_id,
            )
            await self._queue.ack(job)  # Acknowledge to remove from queue
            return

        # ── Distributed lock: prevent concurrent analysis of same document ──
        lock_key = f"analysis:lock:{document_id}"
        try:
            async with self._redis.lock(lock_key, timeout=300):
                logger.info("Processing document %s", document_id)

                async with self._db_factory() as db_session:
                    from src.services.analysis_service import AnalysisService

                    service = AnalysisService(
                        ai_client=self._service.ai_client,
                        db_session=db_session,
                    )
                    analysis = await service.analyze_document(
                        document_id=document_id,
                        tenant_id=tenant_id,
                    )

                logger.info(
                    "Document %s analysis %s: %s",
                    document_id, analysis.id, analysis.status,
                )

        except LockAcquisitionError:
            # Another worker is already processing this document
            logger.warning(
                "Document %s is being processed by another worker, re-queuing",
                document_id,
            )
            # Re-queue with a delay to try again later
            await self._queue.requeue(job, delay=30)
            return

        except Exception:
            logger.exception("Failed to process document %s", document_id)
            # Remove dedup key so the job can be retried
            await self._redis.delete(dedup_key)

        finally:
            # Always acknowledge the message to prevent infinite redelivery
            await self._queue.ack(job)

    def _request_shutdown(self):
        """Signal handler: request graceful shutdown."""
        logger.info("Shutdown signal received. Finishing current job...")
        self._shutdown_event.set()

        # Do NOT cancel the current task — let it finish
        # The while loop will exit after the current job completes


# ── Entry point (illustrative — actual wiring depends on deployment) ──
async def main():
    from redis.asyncio import Redis
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from src.config import settings
    from src.services.ai_client import create_ai_client

    # RedisQueue is a placeholder for a real queue library (e.g. arq, rq, or custom)
    # Replace with your chosen implementation.
    from src.workers.queue import RedisQueue  # type: ignore[import-not-found]

    engine = create_async_engine(settings.DATABASE_URL)
    queue = RedisQueue(url="redis://localhost:6379/0", queue_name="analysis_jobs")
    redis = Redis.from_url("redis://localhost:6379/0")
    db_factory = async_sessionmaker(engine, expire_on_commit=False)
    ai_client = create_ai_client(provider="anthropic", api_key=settings.AI_API_KEY)

    worker = AnalysisWorker(queue, ai_client, redis, db_factory)
    await worker.start()


if __name__ == "__main__":
    asyncio.run(main())
