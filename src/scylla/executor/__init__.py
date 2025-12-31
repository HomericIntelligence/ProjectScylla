"""Executor module for running agent evaluations.

This module provides workspace management, Docker container orchestration,
tier configuration, test runner orchestration, log capture, and result aggregation.
"""

from scylla.executor.capture import (
    ExecutionMetrics,
    LogCapture,
    StreamingCapture,
    aggregate_metrics,
    load_metrics,
)
from scylla.executor.docker import (
    ContainerConfig,
    ContainerError,
    ContainerResult,
    ContainerTimeoutError,
    DockerError,
    DockerExecutor,
    DockerNotAvailableError,
)
from scylla.executor.judge_container import (
    JudgeContainerConfig,
    JudgeContainerManager,
    JudgeResult,
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
    # Capture
    "ExecutionMetrics",
    "LogCapture",
    "StreamingCapture",
    "aggregate_metrics",
    "load_metrics",
    # Docker
    "ContainerConfig",
    "ContainerError",
    "ContainerResult",
    "ContainerTimeoutError",
    "DockerError",
    "DockerExecutor",
    "DockerNotAvailableError",
    # Judge container
    "JudgeContainerConfig",
    "JudgeContainerManager",
    "JudgeResult",
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
