"""Unit tests for the parallelism scheduler module.

Tests cover:
- ParallelismScheduler initialization with correct semaphore counts
- acquire() context manager acquires and releases
- acquire_raw() / release() manual control
- Invalid memory class raises KeyError
- create_scheduler_from_config factory function
- Correct config values stored
"""

from __future__ import annotations

import threading
from multiprocessing import Manager

import pytest

from scylla.e2e.scheduler import (
    MEMORY_CLASSES,
    ParallelismConfig,
    ParallelismScheduler,
    create_scheduler_from_config,
)


@pytest.fixture(scope="module")
def mp_manager():
    """Create a multiprocessing Manager shared across tests in this module."""
    mgr = Manager()
    yield mgr
    mgr.shutdown()


@pytest.fixture
def scheduler(mp_manager) -> ParallelismScheduler:
    """Create a ParallelismScheduler with small limits for testing."""
    return ParallelismScheduler(
        manager=mp_manager,
        parallel_high=2,
        parallel_med=4,
        parallel_low=8,
    )


class TestParallelismSchedulerInit:
    """Tests for ParallelismScheduler initialisation."""

    def test_default_config_stored(self, scheduler: ParallelismScheduler) -> None:
        """Verify scheduler stores the provided config values correctly."""
        config = scheduler.get_config()
        assert config.parallel_high == 2
        assert config.parallel_med == 4
        assert config.parallel_low == 8

    def test_semaphores_created_for_all_classes(self, mp_manager) -> None:
        """All three memory class semaphores are created."""
        s = ParallelismScheduler(mp_manager, parallel_high=1, parallel_med=2, parallel_low=3)
        # Acquire and release each semaphore to verify they work
        for cls in MEMORY_CLASSES:
            s.acquire_raw(cls)
            s.release(cls)


class TestParallelismSchedulerContextManager:
    """Tests for ParallelismScheduler context manager (acquire())."""

    def test_acquire_context_manager_releases_on_exit(
        self, scheduler: ParallelismScheduler
    ) -> None:
        """acquire() releases the semaphore when the context exits normally."""
        with scheduler.acquire("high"):
            pass  # Should not raise

        # Verify we can acquire again (semaphore was released)
        with scheduler.acquire("high"):
            pass

    def test_acquire_context_manager_releases_on_exception(
        self, scheduler: ParallelismScheduler
    ) -> None:
        """acquire() releases even if an exception is raised inside the block."""
        try:
            with scheduler.acquire("high"):
                raise ValueError("simulated error")
        except ValueError:
            pass

        # Semaphore should have been released despite the exception
        with scheduler.acquire("high"):
            pass

    def test_acquire_all_classes(self, scheduler: ParallelismScheduler) -> None:
        """acquire() works for all three memory classes."""
        for cls in MEMORY_CLASSES:
            with scheduler.acquire(cls):
                pass

    def test_acquire_invalid_class_raises(self, scheduler: ParallelismScheduler) -> None:
        """Verify acquire() raises KeyError for an invalid memory class."""
        with pytest.raises(KeyError, match="Invalid memory class"):
            with scheduler.acquire("invalid"):
                pass


class TestParallelismSchedulerRawControl:
    """Tests for ParallelismScheduler raw acquire/release control."""

    def test_acquire_raw_and_release(self, scheduler: ParallelismScheduler) -> None:
        """Manual acquire/release works correctly."""
        scheduler.acquire_raw("med")
        scheduler.release("med")

    def test_acquire_raw_invalid_class_raises(self, scheduler: ParallelismScheduler) -> None:
        """Verify acquire_raw() raises KeyError for an invalid memory class."""
        with pytest.raises(KeyError, match="Invalid memory class"):
            scheduler.acquire_raw("invalid")

    def test_release_invalid_class_raises(self, scheduler: ParallelismScheduler) -> None:
        """Verify release() raises KeyError for an invalid memory class."""
        with pytest.raises(KeyError, match="Invalid memory class"):
            scheduler.release("invalid")


class TestParallelismSchedulerConcurrency:
    """Tests for ParallelismScheduler concurrency limiting."""

    def test_high_semaphore_limits_concurrency(self, mp_manager) -> None:
        """High semaphore with count 1 prevents more than 1 concurrent acquisition."""
        s = ParallelismScheduler(mp_manager, parallel_high=1, parallel_med=4, parallel_low=8)

        acquired_count = [0]
        max_concurrent = [0]
        lock = threading.Lock()

        def acquire_and_hold():
            s.acquire_raw("high")
            with lock:
                acquired_count[0] += 1
                max_concurrent[0] = max(max_concurrent[0], acquired_count[0])
            # Hold briefly
            import time

            time.sleep(0.01)
            with lock:
                acquired_count[0] -= 1
            s.release("high")

        threads = [threading.Thread(target=acquire_and_hold) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # With semaphore count 1, should never exceed 1 concurrent
        assert max_concurrent[0] == 1


class TestCreateSchedulerFromConfig:
    """Tests for create_scheduler_from_config() factory function."""

    def test_factory_creates_scheduler(self, mp_manager) -> None:
        """Verify factory creates a ParallelismScheduler with given config."""
        s = create_scheduler_from_config(
            mp_manager, parallel_high=3, parallel_med=5, parallel_low=10
        )
        assert isinstance(s, ParallelismScheduler)
        config = s.get_config()
        assert config.parallel_high == 3
        assert config.parallel_med == 5
        assert config.parallel_low == 10

    def test_factory_uses_defaults(self, mp_manager) -> None:
        """Verify factory uses default parallelism values when none provided."""
        s = create_scheduler_from_config(mp_manager)
        config = s.get_config()
        assert config.parallel_high == 2
        assert config.parallel_med == 4
        assert config.parallel_low == 8


class TestParallelismConfig:
    """Tests for ParallelismConfig dataclass defaults and validation."""

    def test_default_values(self) -> None:
        """Verify ParallelismConfig has correct default values."""
        config = ParallelismConfig()
        assert config.parallel_high == 2
        assert config.parallel_med == 4
        assert config.parallel_low == 8

    def test_custom_values(self) -> None:
        """Verify ParallelismConfig accepts custom parallelism values."""
        config = ParallelismConfig(parallel_high=1, parallel_med=2, parallel_low=4)
        assert config.parallel_high == 1
        assert config.parallel_med == 2
        assert config.parallel_low == 4
