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
from scylla.adapters.claude_code import ClaudeCodeAdapter

__all__ = [
    "AdapterConfig",
    "AdapterError",
    "AdapterResult",
    "AdapterTimeoutError",
    "AdapterValidationError",
    "BaseAdapter",
    "ClaudeCodeAdapter",
]
