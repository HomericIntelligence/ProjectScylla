"""Automation module for bulk GitHub issue planning and implementation.

This module provides tools for:
- Bulk planning of GitHub issues using Claude Code
- Bulk implementation of issues with dependency resolution
- Git worktree management for parallel execution
- Rate limiting and error handling for API calls
- Retry logic with exponential backoff
"""

from scylla.automation.dependency_resolver import DependencyResolver
from scylla.automation.implementer import IssueImplementer
from scylla.automation.models import (
    DependencyGraph,
    ImplementationState,
    ImplementerOptions,
    IssueInfo,
    IssueState,
    PlannerOptions,
    PlanResult,
    WorkerResult,
)
from scylla.automation.planner import Planner
from scylla.automation.retry import retry_on_network_error, retry_with_backoff
from scylla.automation.status_tracker import StatusTracker
from scylla.automation.worktree_manager import WorktreeManager

__all__ = [
    # Main classes
    "IssueImplementer",
    "Planner",
    "DependencyResolver",
    "StatusTracker",
    "WorktreeManager",
    # Data models
    "IssueInfo",
    "IssueState",
    "DependencyGraph",
    "ImplementationState",
    "PlannerOptions",
    "ImplementerOptions",
    "PlanResult",
    "WorkerResult",
    # Retry utilities
    "retry_with_backoff",
    "retry_on_network_error",
]
