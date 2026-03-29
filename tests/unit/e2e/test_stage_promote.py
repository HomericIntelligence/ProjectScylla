"""Tests for stage_promote_to_completed — re-exported for discoverability.

The implementation tests live in test_stage_commit_agent_changes.py alongside
the commit-agent-changes tests (they share the _make_ctx fixture).  This module
re-exports the class so pytest can also discover it under the canonical filename.
"""

from __future__ import annotations

from tests.unit.e2e.test_stage_commit_agent_changes import TestStagePromoteToCompleted

__all__ = ["TestStagePromoteToCompleted"]
