"""Shared constants for ProjectScylla configuration.

This module is the single source of truth for default model IDs.
Import from here rather than hardcoding model strings at call sites.
"""

DEFAULT_AGENT_MODEL: str = "claude-sonnet-4-5-20250929"
DEFAULT_JUDGE_MODEL: str = "claude-opus-4-5-20251101"
