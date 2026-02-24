"""Tests for status tracker."""

import threading
import time

from scylla.automation.status_tracker import StatusTracker


class TestStatusTracker:
    """Tests for StatusTracker class."""

    def test_initialization(self):
        """Test tracker initialization."""
        tracker = StatusTracker(num_slots=3)

        assert tracker.num_slots == 3
        assert len(tracker.slots) == 3
        assert all(slot is None for slot in tracker.slots)

    def test_acquire_slot(self):
        """Test acquiring a slot."""
        tracker = StatusTracker(num_slots=2)

        slot_id = tracker.acquire_slot()

        assert slot_id is not None
        assert 0 <= slot_id < 2
        assert tracker.slots[slot_id] == "acquired"

    def test_acquire_all_slots(self):
        """Test acquiring all available slots."""
        tracker = StatusTracker(num_slots=2)

        slot1 = tracker.acquire_slot()
        slot2 = tracker.acquire_slot()

        assert slot1 is not None
        assert slot2 is not None
        assert slot1 != slot2
        assert tracker.get_active_count() == 2

    def test_acquire_slot_timeout(self):
        """Test slot acquisition timeout when all slots occupied."""
        tracker = StatusTracker(num_slots=1)

        # Acquire the only slot
        slot1 = tracker.acquire_slot()
        assert slot1 is not None

        # Try to acquire when full - should timeout
        slot2 = tracker.acquire_slot(timeout=0.1)
        assert slot2 is None

    def test_release_slot(self):
        """Test releasing a slot."""
        tracker = StatusTracker(num_slots=2)

        slot_id = tracker.acquire_slot()
        assert slot_id is not None

        tracker.release_slot(slot_id)

        assert tracker.slots[slot_id] is None
        assert tracker.get_active_count() == 0

    def test_release_invalid_slot(self):
        """Test releasing invalid slot ID."""
        tracker = StatusTracker(num_slots=2)

        # Should not crash, just log error
        tracker.release_slot(999)
        tracker.release_slot(-1)

    def test_update_slot(self):
        """Test updating slot status."""
        tracker = StatusTracker(num_slots=2)

        slot_id = tracker.acquire_slot()
        assert slot_id is not None
        tracker.update_slot(slot_id, "Processing issue #123")

        assert tracker.slots[slot_id] == "Processing issue #123"

    def test_update_invalid_slot(self):
        """Test updating invalid slot ID."""
        tracker = StatusTracker(num_slots=2)

        # Should not crash, just log error
        tracker.update_slot(999, "invalid")
        tracker.update_slot(-1, "invalid")

    def test_get_status(self):
        """Test getting status snapshot."""
        tracker = StatusTracker(num_slots=3)

        slot1 = tracker.acquire_slot()
        assert slot1 is not None
        tracker.update_slot(slot1, "Working")

        status = tracker.get_status()

        assert len(status) == 3
        assert status[slot1] == "Working"
        # Verify it's a copy
        status[slot1] = "Modified"
        assert tracker.slots[slot1] == "Working"

    def test_get_active_count(self):
        """Test getting active slot count."""
        tracker = StatusTracker(num_slots=3)

        assert tracker.get_active_count() == 0

        slot1 = tracker.acquire_slot()
        assert slot1 is not None
        assert tracker.get_active_count() == 1

        _ = tracker.acquire_slot()
        assert tracker.get_active_count() == 2

        tracker.release_slot(slot1)
        assert tracker.get_active_count() == 1

    def test_wait_for_available(self):
        """Test waiting for slot availability."""
        tracker = StatusTracker(num_slots=1)

        # Acquire the only slot
        slot_id = tracker.acquire_slot()
        assert slot_id is not None

        # Start thread that releases slot after delay
        def release_after_delay():
            time.sleep(0.1)
            tracker.release_slot(slot_id)

        thread = threading.Thread(target=release_after_delay, daemon=True)
        thread.start()

        # Wait for availability - should succeed
        result = tracker.wait_for_available(timeout=1.0)
        assert result is True

        thread.join()

    def test_wait_for_available_timeout(self):
        """Test wait_for_available timeout."""
        tracker = StatusTracker(num_slots=1)

        # Acquire the only slot and don't release
        tracker.acquire_slot()

        # Wait should timeout
        result = tracker.wait_for_available(timeout=0.1)
        assert result is False

    def test_wait_all_complete(self):
        """Test waiting for all slots to complete."""
        tracker = StatusTracker(num_slots=2)

        slot1 = tracker.acquire_slot()
        slot2 = tracker.acquire_slot()
        assert slot1 is not None
        assert slot2 is not None

        # Start thread that releases slots after delay
        def release_after_delay():
            time.sleep(0.05)
            tracker.release_slot(slot1)
            time.sleep(0.05)
            tracker.release_slot(slot2)

        thread = threading.Thread(target=release_after_delay, daemon=True)
        thread.start()

        # Wait for all to complete
        result = tracker.wait_all_complete(timeout=1.0)
        assert result is True

        thread.join()

    def test_wait_all_complete_timeout(self):
        """Test wait_all_complete timeout."""
        tracker = StatusTracker(num_slots=1)

        # Acquire slot and don't release
        tracker.acquire_slot()

        # Wait should timeout
        result = tracker.wait_all_complete(timeout=0.1)
        assert result is False

    def test_clear(self):
        """Test clearing all slots."""
        tracker = StatusTracker(num_slots=3)

        slot1 = tracker.acquire_slot()
        slot2 = tracker.acquire_slot()
        assert slot1 is not None
        assert slot2 is not None
        tracker.update_slot(slot1, "Working")
        tracker.update_slot(slot2, "Working")

        tracker.clear()

        assert all(slot is None for slot in tracker.slots)
        assert tracker.get_active_count() == 0

    def test_concurrent_acquire_release(self):
        """Test concurrent slot acquisition and release."""
        tracker = StatusTracker(num_slots=5)
        acquired_slots = []
        lock = threading.Lock()

        def worker():
            slot_id = tracker.acquire_slot(timeout=2.0)
            if slot_id is not None:
                with lock:
                    acquired_slots.append(slot_id)
                time.sleep(0.01)  # Simulate work
                tracker.release_slot(slot_id)

        # Start 10 threads competing for 5 slots
        threads = [threading.Thread(target=worker, daemon=True) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All threads should have acquired a slot at some point
        assert len(acquired_slots) == 10
        # All slots should be released
        assert tracker.get_active_count() == 0

    def test_notify_all_on_release(self):
        """Test that release_slot wakes all waiting threads."""
        tracker = StatusTracker(num_slots=1)

        # Acquire the only slot
        slot_id = tracker.acquire_slot()
        assert slot_id is not None

        results = []

        def waiter():
            # Both wait_for_available and acquire_slot should wake
            if tracker.wait_for_available(timeout=1.0):
                results.append("available")

        # Start multiple waiting threads
        threads = [threading.Thread(target=waiter, daemon=True) for _ in range(3)]
        for t in threads:
            t.start()

        # Give threads time to start waiting
        time.sleep(0.1)

        # Release should wake all waiters
        tracker.release_slot(slot_id)

        for t in threads:
            t.join()

        # All waiters should have been notified
        assert len(results) == 3

    def test_notify_all_on_clear(self):
        """Test that clear wakes waiting threads."""
        tracker = StatusTracker(num_slots=1)

        # Acquire the only slot
        tracker.acquire_slot()

        result = []

        def waiter():
            if tracker.wait_for_available(timeout=1.0):
                result.append(True)

        thread = threading.Thread(target=waiter, daemon=True)
        thread.start()

        # Give thread time to start waiting
        time.sleep(0.1)

        # Clear should wake waiter
        tracker.clear()

        thread.join()

        assert result == [True]
