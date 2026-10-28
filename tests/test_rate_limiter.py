"""
Unit tests for AsyncRateLimiter and limit_it decorator.
"""

import time
import pytest
from src.utils.rate_limiter import AsyncRateLimiter, limit_it


@pytest.mark.asyncio
async def test_async_rate_limiter_interval():
    limiter = AsyncRateLimiter(delay_seconds=0.2, max_concurrent=1)
    
    start = time.time()
    await limiter.acquire()
    await limiter.acquire()
    elapsed = time.time() - start

    # Should have waited at least 0.2s for the second call
    assert elapsed >= 0.18, f"Expected elapsed >= 0.18s, got {elapsed:.3f}s"


@pytest.mark.asyncio
async def test_limit_it_decorator():
    call_times = []

    @limit_it(delay_seconds=0.15, max_concurrent=1)
    async def sample_task():
        call_times.append(time.time())
        return True

    await sample_task()
    await sample_task()

    assert len(call_times) == 2
    gap = call_times[1] - call_times[0]
    assert gap >= 0.14, f"Expected call gap >= 0.14s, got {gap:.3f}s"
