"""Thread-safe status tracking for parallel workers.

Provides slot-based tracking with condition variables for coordination.
"""

import logging
import threading

logger = logging.getLogger(__name__)


class StatusTracker:
    """Thread-safe tracker for worker status slots.

    Manages a fixed number of worker slots with condition variable
    coordination for efficient waiting.
    """

    def __init__(self, num_slots: int):
        """Initialize status tracker.

        Args:
            num_slots: Number of worker slots to manage

        """
        self.num_slots = num_slots
        self.slots: list[str | None] = [None] * num_slots
        self.lock = threading.Lock()
        self.condition = threading.Condition(self.lock)
        logger.debug(f"Initialized StatusTracker with {num_slots} slots")

    def acquire_slot(self, timeout: float | None = None) -> int | None:
        """Acquire an available slot, waiting if necessary.

        Args:
            timeout: Optional timeout in seconds

        Returns:
            Slot index or None if timeout

        """
        with self.condition:
            while True:
                # Find available slot
                for i, slot in enumerate(self.slots):
                    if slot is None:
                        self.slots[i] = "acquired"
                        logger.debug(f"Acquired slot {i}")
                        return i

                # No slots available, wait
                if not self.condition.wait(timeout=timeout):
                    logger.warning("Slot acquisition timed out")
                    return None

    def release_slot(self, slot_id: int) -> None:
        """Release a slot.

        Args:
            slot_id: Slot index to release

        """
        with self.condition:
            if 0 <= slot_id < self.num_slots:
                self.slots[slot_id] = None
                logger.debug(f"Released slot {slot_id}")
                self.condition.notify_all()  # Wake all waiters
            else:
                logger.error(f"Invalid slot_id: {slot_id}")

    def update_slot(self, slot_id: int, status: str) -> None:
        """Update slot status message.

        Args:
            slot_id: Slot index
            status: Status message

        """
        with self.lock:
            if 0 <= slot_id < self.num_slots:
                self.slots[slot_id] = status
                logger.debug(f"Slot {slot_id}: {status}")
            else:
                logger.error(f"Invalid slot_id: {slot_id}")

    def get_status(self) -> list[str | None]:
        """Get current status of all slots.

        Returns:
            List of slot statuses

        """
        with self.lock:
            return self.slots.copy()

    def get_active_count(self) -> int:
        """Get count of active (non-None) slots.

        Returns:
            Number of active slots

        """
        with self.lock:
            return sum(1 for slot in self.slots if slot is not None)

    def wait_for_available(self, timeout: float | None = None) -> bool:
        """Wait until at least one slot is available.

        Args:
            timeout: Optional timeout in seconds

        Returns:
            True if slot became available, False on timeout

        """
        with self.condition:
            while all(slot is not None for slot in self.slots):
                if not self.condition.wait(timeout=timeout):
                    return False
            return True

    def wait_all_complete(self, timeout: float | None = None) -> bool:
        """Wait until all slots are released.

        Args:
            timeout: Optional timeout in seconds

        Returns:
            True if all complete, False on timeout

        """
        with self.condition:
            while any(slot is not None for slot in self.slots):
                if not self.condition.wait(timeout=timeout):
                    return False
            return True

    def clear(self) -> None:
        """Clear all slot statuses."""
        with self.condition:
            self.slots = [None] * self.num_slots
            logger.debug("Cleared all slots")
            self.condition.notify_all()  # Wake all waiters
