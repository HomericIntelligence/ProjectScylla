"""Executor module for running agent evaluations.

This module provides workspace management, Docker container orchestration,
tier configuration, test runner orchestration, log capture, and result aggregation.
"""

from scylla.executor.agent_container import (
    AgentContainerConfig,
    AgentContainerManager,
)
from scylla.executor.capture import (
    ExecutionMetrics,
    LogCapture,
    StreamingCapture,
    aggregate_metrics,
    load_metrics,
)
from scylla.executor.credential_mount import (
    cleanup_stale_credential_dirs,
    temporary_credential_mount,
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
    EvalRunner,
    EvalSummary,
    ExecutionState,
    ExecutorExecutionInfo,
    ExecutorRunResult,
    InsufficientRunsError,
    JudgmentResult,
    RateLimitError,
    RunnerConfig,
    RunnerError,
    RunStatus,
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
    checkout_hash,
    cleanup_workspace,
    clone_repo,
    create_workspace,
)

__all__ = [
    "AgentContainerConfig",
    "AgentContainerManager",
    "ContainerConfig",
    "ContainerError",
    "ContainerResult",
    "ContainerTimeoutError",
    "DockerError",
    "DockerExecutor",
    "DockerNotAvailableError",
    "EvalRunner",
    "EvalSummary",
    "ExecutionMetrics",
    "ExecutionState",
    "ExecutorExecutionInfo",
    "ExecutorRunResult",
    "InsufficientRunsError",
    "JudgeContainerConfig",
    "JudgeContainerManager",
    "JudgeResult",
    "JudgmentResult",
    "LogCapture",
    "RateLimitError",
    "RunStatus",
    "RunnerConfig",
    "RunnerError",
    "StreamingCapture",
    "TierConfig",
    "TierConfigError",
    "TierConfigLoader",
    "TierDefinition",
    "TierSummary",
    "TiersDefinitionFile",
    "WorkspaceError",
    "aggregate_metrics",
    "calculate_wilson_ci",
    "checkout_hash",
    "cleanup_stale_credential_dirs",
    "cleanup_workspace",
    "clone_repo",
    "create_workspace",
    "load_metrics",
    "load_state",
    "save_state",
    "temporary_credential_mount",
]
