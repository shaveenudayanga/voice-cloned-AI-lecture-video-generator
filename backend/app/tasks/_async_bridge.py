# SPDX-License-Identifier: Apache-2.0
"""
asyncio.run() bridge for Celery tasks.

Celery workers are synchronous by default. This module provides a thin
helper so tasks can call async service/repository code without spawning
a persistent event loop per worker (which Celery's sync model does not support).

Each task invocation gets its own short-lived event loop via asyncio.run(),
which is safe and correct for Celery's process-per-worker model.
"""
import asyncio
from collections.abc import Coroutine


def run_async[T](coro: Coroutine[object, object, T]) -> T:
    """Execute a coroutine from synchronous (Celery task) context."""
    return asyncio.run(coro)
