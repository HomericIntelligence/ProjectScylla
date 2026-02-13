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
from scylla.adapters.base_cli import BaseCliAdapter
from scylla.adapters.claude_code import ClaudeCodeAdapter
from scylla.adapters.cline import ClineAdapter
from scylla.adapters.openai_codex import OpenAICodexAdapter
from scylla.adapters.opencode import OpenCodeAdapter

__all__ = [
    "AdapterConfig",
    "AdapterError",
    "AdapterResult",
    "AdapterTimeoutError",
    "AdapterValidationError",
    "BaseAdapter",
    "BaseCliAdapter",
    "ClaudeCodeAdapter",
    "ClineAdapter",
    "OpenAICodexAdapter",
    "OpenCodeAdapter",
]
