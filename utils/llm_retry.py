"""Retry helpers for transient Gemini / Google AI errors (503, 429, overload)."""
from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")


def is_transient_gemini_error(exc: BaseException) -> bool:
    """True if retrying the same request may succeed."""
    s = str(exc).lower()
    if any(x in s for x in ("503", "429", "502", "504")):
        return True
    if "unavailable" in s and ("model" in s or "service" in s):
        return True
    if "resource_exhausted" in s:
        return True
    if "rate" in s and "limit" in s:
        return True
    if "overloaded" in s or "try again later" in s:
        return True

    code = getattr(exc, "status_code", None)
    if code in (429, 502, 503, 504):
        return True

    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        err = body.get("error") or {}
        status = (err.get("status") or "").upper()
        if status in ("UNAVAILABLE", "RESOURCE_EXHAUSTED", "DEADLINE_EXCEEDED"):
            return True
        msg = str(err.get("message", "")).lower()
        if "try again" in msg or "high demand" in msg:
            return True
    return False


async def async_retry_llm(
    factory: Callable[[], Awaitable[T]],
    *,
    max_attempts: int = 6,
    base_delay: float = 1.5,
    max_delay: float = 45.0,
) -> T:
    """Retry an async LLM call with exponential backoff + jitter."""
    last: BaseException | None = None
    for attempt in range(max_attempts):
        try:
            return await factory()
        except Exception as e:
            last = e
            if not is_transient_gemini_error(e) or attempt == max_attempts - 1:
                raise
            delay = min(max_delay, base_delay * (2**attempt) + random.uniform(0, 0.75))
            await asyncio.sleep(delay)
    assert last is not None
    raise last


def sync_retry_llm(
    factory: Callable[[], T],
    *,
    max_attempts: int = 6,
    base_delay: float = 1.5,
    max_delay: float = 45.0,
) -> T:
    """Retry a sync LLM call with exponential backoff + jitter."""
    last: BaseException | None = None
    for attempt in range(max_attempts):
        try:
            return factory()
        except Exception as e:
            last = e
            if not is_transient_gemini_error(e) or attempt == max_attempts - 1:
                raise
            delay = min(max_delay, base_delay * (2**attempt) + random.uniform(0, 0.75))
            time.sleep(delay)
    assert last is not None
    raise last
