"""Solvela balance monitor — background USDC-SPL balance poller."""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)


class BalanceMonitor:
    """Polls USDC-SPL balance on a schedule, fires callback on low-balance transition."""

    def __init__(
        self,
        fetch_balance: Callable[[], Awaitable[float]],
        poll_interval: float = 30.0,
        low_balance_threshold: float | None = None,
        on_low_balance: Callable[[float], None] | None = None,
    ) -> None:
        self._fetch_balance = fetch_balance
        self._poll_interval = poll_interval
        self._threshold = low_balance_threshold
        self._on_low_balance = on_low_balance
        self._balance: float | None = None
        self._was_low = False
        self._task: asyncio.Task[None] | None = None
        self._stopped = False

    def start(self) -> None:
        """Start the polling loop as a background task."""
        self._stopped = False
        self._task = asyncio.create_task(self._run())

    def stop(self) -> None:
        """Stop the polling loop. Idempotent."""
        self._stopped = True
        if self._task is not None and not self._task.done():
            self._task.cancel()
            self._task = None

    def last_known_balance(self) -> float | None:
        """Get the last polled balance, or None if never polled."""
        return self._balance

    async def _run(self) -> None:
        while not self._stopped:
            try:
                balance = await self._fetch_balance()
                self._balance = balance

                # Transition-debounced low balance callback
                if self._threshold is not None and self._on_low_balance is not None:
                    is_low = balance < self._threshold
                    if is_low and not self._was_low:
                        self._on_low_balance(balance)
                    self._was_low = is_low
            except asyncio.CancelledError:
                break
            except Exception:
                # Surface poll errors at WARNING level. A silent failure (the
                # previous DEBUG default) would leave last_known_balance() stuck
                # at None and silently disable any free-fallback-model guard
                # downstream. Mirrors the warn-on-poll-error fix in the TS SDK.
                logger.warning("Balance fetch failed", exc_info=True)

            try:
                await asyncio.sleep(self._poll_interval)
            except asyncio.CancelledError:
                break
