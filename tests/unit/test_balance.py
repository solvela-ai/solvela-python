"""Unit tests for BalanceMonitor — polling, callbacks, stop idempotency."""
from __future__ import annotations

import asyncio

import pytest

from rustyclaw.balance import BalanceMonitor


@pytest.mark.asyncio
async def test_balance_monitor_polls() -> None:
    """Verify fetch is called multiple times."""
    call_count = 0

    async def fetch() -> float:
        nonlocal call_count
        call_count += 1
        return 100.0

    monitor = BalanceMonitor(fetch_balance=fetch, poll_interval=0.01)
    monitor.start()
    await asyncio.sleep(0.05)
    monitor.stop()
    assert call_count >= 2


@pytest.mark.asyncio
async def test_balance_monitor_updates_state() -> None:
    """last_known_balance() reflects the polled value."""
    async def fetch() -> float:
        return 42.5

    monitor = BalanceMonitor(fetch_balance=fetch, poll_interval=0.01)
    assert monitor.last_known_balance() is None
    monitor.start()
    await asyncio.sleep(0.05)
    monitor.stop()
    assert monitor.last_known_balance() == 42.5


@pytest.mark.asyncio
async def test_low_balance_callback_fires_on_transition() -> None:
    """Callback fires once when crossing threshold, not every tick."""
    fired: list[float] = []
    call_count = 0

    async def fetch() -> float:
        nonlocal call_count
        call_count += 1
        return 5.0  # always below threshold

    def on_low(balance: float) -> None:
        fired.append(balance)

    monitor = BalanceMonitor(
        fetch_balance=fetch,
        poll_interval=0.01,
        low_balance_threshold=10.0,
        on_low_balance=on_low,
    )
    monitor.start()
    await asyncio.sleep(0.05)
    monitor.stop()
    # Should fire exactly once (transition from not-low to low)
    assert len(fired) == 1
    assert fired[0] == 5.0
    # But polling happened multiple times
    assert call_count >= 2


@pytest.mark.asyncio
async def test_stop_is_idempotent() -> None:
    """Calling stop() twice doesn't raise."""
    async def fetch() -> float:
        return 100.0

    monitor = BalanceMonitor(fetch_balance=fetch, poll_interval=0.01)
    monitor.start()
    await asyncio.sleep(0.02)
    monitor.stop()
    monitor.stop()  # second call should not raise


@pytest.mark.asyncio
async def test_callback_does_not_fire_when_above_threshold() -> None:
    """No callback when balance stays above threshold."""
    fired: list[float] = []

    async def fetch() -> float:
        return 100.0

    def on_low(balance: float) -> None:
        fired.append(balance)

    monitor = BalanceMonitor(
        fetch_balance=fetch,
        poll_interval=0.01,
        low_balance_threshold=10.0,
        on_low_balance=on_low,
    )
    monitor.start()
    await asyncio.sleep(0.05)
    monitor.stop()
    assert len(fired) == 0
