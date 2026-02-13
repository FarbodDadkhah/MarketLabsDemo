from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

import httpx

from src.services.exceptions import AITimeoutError

T = TypeVar("T")

logger = logging.getLogger(__name__)


async def retry_with_backoff(
    func: Callable[..., Awaitable[T]],
    *args: object,
    max_retries: int = 3,
    base_delay: float = 1.0,
    retryable_exceptions: tuple[type[BaseException], ...] = (
        AITimeoutError,
        httpx.HTTPStatusError,
    ),
    **kwargs: object,
) -> T:
    last_exception: BaseException | None = None

    for attempt in range(max_retries):
        try:
            return await func(*args, **kwargs)
        except retryable_exceptions as exc:
            last_exception = exc
            delay = base_delay * (2 ** attempt)
            logger.warning(
                "Attempt %d/%d failed (%s: %s), retrying in %.1fs",
                attempt + 1,
                max_retries,
                type(exc).__name__,
                exc,
                delay,
            )
            await asyncio.sleep(delay)

    raise last_exception  # type: ignore[misc]
