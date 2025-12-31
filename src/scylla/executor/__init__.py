"""Executor module for running agent evaluations.

This module provides workspace management, Docker container orchestration,
tier configuration, test runner orchestration, and result aggregation.
"""

from scylla.executor.docker import (
    ContainerConfig,
    ContainerError,
    ContainerResult,
    ContainerTimeoutError,
    DockerError,
    DockerExecutor,
    DockerNotAvailableError,
)
from scylla.executor.runner import (
    ExecutionInfo,
    ExecutionState,
    InsufficientRunsError,
    JudgmentResult,
    RateLimitError,
    RunnerConfig,
    RunnerError,
    RunResult,
    RunStatus,
    TestRunner,
    TestSummary,
    TierSummary,
    calculate_wilson_ci,
    load_state,
    save_state,
)
from scylla.executor.tier_config import (
    TierConfig,
    TierConfigError,
    TierConfigLoader,
    TierDefinition,
    TiersDefinitionFile,
)
from scylla.executor.workspace import (
    WorkspaceError,
    WorkspaceManager,
    checkout_hash,
    cleanup_workspace,
    clone_repo,
    create_workspace,
)

__all__ = [
    # Docker
    "ContainerConfig",
    "ContainerError",
    "ContainerResult",
    "ContainerTimeoutError",
    "DockerError",
    "DockerExecutor",
    "DockerNotAvailableError",
    # Runner
    "ExecutionInfo",
    "ExecutionState",
    "InsufficientRunsError",
    "JudgmentResult",
    "RateLimitError",
    "RunnerConfig",
    "RunnerError",
    "RunResult",
    "RunStatus",
    "TestRunner",
    "TestSummary",
    "TierSummary",
    "calculate_wilson_ci",
    "load_state",
    "save_state",
    # Tier Configuration
    "TierConfig",
    "TierConfigError",
    "TierConfigLoader",
    "TierDefinition",
    "TiersDefinitionFile",
    # Workspace
    "WorkspaceError",
    "WorkspaceManager",
    "checkout_hash",
    "cleanup_workspace",
    "clone_repo",
    "create_workspace",
]
