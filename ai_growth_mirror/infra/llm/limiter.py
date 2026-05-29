"""Shared concurrency control for LLM-backed batch work."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

_DEFAULT_RECOVERY_STREAK = 25


@dataclass(frozen=True)
class ExecutionWindow:
    initial_concurrency: int
    minimum_concurrency: int = 1
    recovery_streak: int = _DEFAULT_RECOVERY_STREAK


class ProviderExecutionPolicy:
    """Adaptive concurrency gate that reacts to provider back-pressure."""

    def __init__(
        self,
        *,
        initial: int,
        minimum: int = 1,
        recovery_streak: int = _DEFAULT_RECOVERY_STREAK,
    ) -> None:
        if initial < 1:
            raise ValueError("initial concurrency must be >= 1")
        if minimum < 1 or minimum > initial:
            raise ValueError("minimum must satisfy 1 <= minimum <= initial")
        self.window = ExecutionWindow(initial, minimum, recovery_streak)
        self._limit = initial
        self._in_flight = 0
        self._healthy_completions = 0
        self._condition = threading.Condition()

    @property
    def current_max(self) -> int:
        with self._condition:
            return self._limit

    def acquire(self) -> None:
        with self._condition:
            while self._in_flight >= self._limit:
                self._condition.wait()
            self._in_flight += 1

    def release(self) -> None:
        with self._condition:
            if self._in_flight > 0:
                self._in_flight -= 1
            self._condition.notify_all()

    def _set_limit(self, new_limit: int, *, log_level: int, message: str) -> None:
        if new_limit == self._limit:
            return
        previous = self._limit
        self._limit = new_limit
        self._condition.notify_all()
        logger.log(log_level, message, previous, new_limit)

    def on_429(self) -> None:
        with self._condition:
            self._healthy_completions = 0
            lowered = max(self.window.minimum_concurrency, self._limit - 1)
            if lowered == self._limit:
                logger.warning(
                    "Execution policy already at provider floor %d",
                    self.window.minimum_concurrency,
                )
                return
            self._set_limit(
                lowered,
                log_level=logging.WARNING,
                message="Execution policy tightened after 429: %d -> %d",
            )

    def on_success(self) -> None:
        with self._condition:
            self._healthy_completions += 1
            recovered = self._healthy_completions >= self.window.recovery_streak
            if not recovered or self._limit >= self.window.initial_concurrency:
                return
            self._healthy_completions = 0
            self._set_limit(
                self._limit + 1,
                log_level=logging.INFO,
                message="Execution policy relaxed after recovery: %d -> %d",
            )

    def __enter__(self) -> "ProviderExecutionPolicy":
        self.acquire()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.release()


AdaptiveLimiter = ProviderExecutionPolicy


def is_rate_limit_error(exc: BaseException) -> bool:
    text = str(exc).casefold()
    tokens = ("429", "qps", "rate limit", "too many requests", "qpsoverlimit")
    return any(token in text for token in tokens)


def is_transient_error(exc: BaseException) -> bool:
    if is_rate_limit_error(exc):
        return True
    text = str(exc).casefold()
    fragments = (
        "connection error",
        "connection reset",
        "connection aborted",
        "timeout",
        "timed out",
        "remote end closed",
        "temporarily unavailable",
        "503",
        "504",
        "502",
        "bad gateway",
    )
    return any(fragment in text for fragment in fragments)


def get_default_limiter(initial: int) -> Optional["AdaptiveLimiter"]:
    return AdaptiveLimiter(initial=initial)
