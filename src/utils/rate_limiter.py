"""
Asynchronous rate limiter and semaphore decorator.
Enforces politeness rules (e.g. 1 request per second) and concurrency bounds.
"""

import asyncio
import logging
import functools
import time
from typing import Callable, Any, Optional

logger = logging.getLogger(__name__)

class AsyncRateLimiter:
    """
    Combines an asyncio.Semaphore with minimum-interval time tracking.
    Can be used as an instance or as a method decorator.
    """

    def __init__(self, delay_seconds: float = 1.0, max_concurrent: int = 1):
        self.delay_seconds = delay_seconds
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.lock = asyncio.Lock()
        self.last_called: float = 0.0

    async def acquire(self) -> None:
        """Wait for semaphore and enforce inter-request delay."""
        async with self.lock:
            if self.last_called > 0:
                elapsed = time.time() - self.last_called
                if elapsed < self.delay_seconds:
                    wait_time = self.delay_seconds - elapsed
                    logger.debug("Rate limiter waiting %.3fs to obey %.1fs/req policy", wait_time, self.delay_seconds)
                    await asyncio.sleep(wait_time)
            self.last_called = time.time()


def limit_it(delay_seconds: float = 1.0, max_concurrent: int = 1):
    """
    Decorator for asynchronous functions to enforce rate limits and concurrency limits.
    
    Example:
        @limit_it(delay_seconds=1.0, max_concurrent=1)
        async def fetch(url):
            ...
    """
    limiter = AsyncRateLimiter(delay_seconds=delay_seconds, max_concurrent=max_concurrent)

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            async with limiter.semaphore:
                await limiter.acquire()
                return await func(*args, **kwargs)

        return wrapper

    return decorator
