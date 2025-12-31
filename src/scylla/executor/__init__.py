"""Executor module for running agent evaluations.

This module provides workspace management, Docker container orchestration,
tier configuration, and test execution capabilities.
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
