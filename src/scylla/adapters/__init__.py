"""Adapters module for agent implementations.

This module provides adapters that bridge the Scylla test runner
and specific AI agent implementations.
"""

from scylla.adapters.base import (
    AdapterConfig,
    AdapterError,
    AdapterResult,
    AdapterTimeoutError,
    AdapterValidationError,
    BaseAdapter,
)

__all__ = [
    "AdapterConfig",
    "AdapterError",
    "AdapterResult",
    "AdapterTimeoutError",
    "AdapterValidationError",
    "BaseAdapter",
]
