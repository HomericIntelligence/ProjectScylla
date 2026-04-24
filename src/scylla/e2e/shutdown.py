"""Shutdown coordination for E2E experiment runner.

Extracted from runner.py to break a circular import:
  runner -> tier_action_builder -> subtest_executor -> parallel_executor
  -> rate_limit -> (was) runner

By moving shutdown state here, rate_limit, stages, and state machines can
import from this lightweight module without pulling in all of runner.py.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Global shutdown coordination
_shutdown_requested = False


class ShutdownInterruptedError(Exception):
    """Raised when an in-progress stage is interrupted by a shutdown signal (Ctrl+C).

    Unlike a generic Exception, this is caught separately by StateMachine.advance_to_completion()
    so the run is NOT marked as FAILED.  The run state stays at its last successfully
    checkpointed value, allowing clean resume on the next invocation.
    """


def request_shutdown() -> None:
    """Request graceful shutdown of the experiment.

    This is typically called by signal handlers (SIGINT, SIGTERM).
    """
    global _shutdown_requested
    _shutdown_requested = True
    logger.warning("Graceful shutdown requested")


def is_shutdown_requested() -> bool:
    """Check if shutdown has been requested.

    Returns:
        True if shutdown is requested, False otherwise

    """
    return _shutdown_requested
