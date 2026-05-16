"""
Inference queue for CPU-only Vultr VM (2 vCPU / 4 GB RAM).

Why this exists:
  EfficientNet-B0 on CPU uses ~1.5 GB RAM per inference.
  With 4 GB total, allowing >2 concurrent inferences risks OOM.
  asyncio.Queue(maxsize=5) acts as a counting semaphore:
    - slots 1-2: active inference
    - slots 3-5: waiting in queue
    - slot 6+:   immediate 503 — caller retries later

Usage:
    async with inference_slot():
        result = analyzer.analyze_xray(path)
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import HTTPException

logger = logging.getLogger(__name__)

# Max concurrent + queued inference requests before returning 503
_QUEUE: asyncio.Queue[None] = asyncio.Queue(maxsize=5)


@asynccontextmanager
async def inference_slot(timeout: float = 30.0) -> AsyncIterator[None]:
    """
    Async context manager that acquires a slot in the inference queue.
    Raises HTTP 503 immediately if the queue is full.
    Releases the slot automatically on exit (success or exception).
    """
    # Non-blocking check — fail fast instead of piling up connections
    try:
        _QUEUE.put_nowait(None)
    except asyncio.QueueFull:
        queue_depth = _QUEUE.qsize()
        logger.warning("Inference queue full (depth=%d), rejecting request", queue_depth)
        raise HTTPException(
            status_code=503,
            detail={
                "error": "Server busy — inference queue full. Try again in 30 seconds.",
                "code": "QUEUE_FULL",
                "queue_depth": queue_depth,
                "retry_after_seconds": 30,
            },
        )

    try:
        yield
    finally:
        # Always drain one slot, even if inference raised an exception
        try:
            _QUEUE.get_nowait()
            _QUEUE.task_done()
        except asyncio.QueueEmpty:
            pass


def queue_status() -> dict:
    """Returns current queue depth for the /api/health endpoint."""
    return {
        "queue_depth":    _QUEUE.qsize(),
        "queue_capacity": _QUEUE.maxsize,
        "queue_available": _QUEUE.maxsize - _QUEUE.qsize(),
    }
