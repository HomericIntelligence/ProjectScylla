"""Repository type detection utilities for E2E framework.

This module provides centralized repository type detection logic to enable
reusable detection across the E2E framework and support multiple repository
types (Mojo/modular, Maven, Gradle, npm, Poetry, etc.).

Detection functions are pure and accept a workspace Path parameter, making
them easy to test and cache. Optional LRU caching reduces repeated filesystem
checks during script generation.
"""

from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=128)
def is_modular_repo(workspace: Path) -> bool:
    """Check if workspace is the modular/mojo monorepo.

    The modular repo has a specific structure:
    - bazelw script at root
    - mojo/ subdirectory with its own pixi.toml

    Args:
        workspace: Path to the workspace directory

    Returns:
        True if this is the modular repo, False otherwise.

    """
    return (workspace / "bazelw").exists() and (workspace / "mojo").is_dir()


@lru_cache(maxsize=128)
def is_maven_repo(workspace: Path) -> bool:
    """Check if workspace is a Maven project.

    Maven projects have a pom.xml at the root.

    Args:
        workspace: Path to the workspace directory

    Returns:
        True if this is a Maven project, False otherwise.

    """
    return (workspace / "pom.xml").exists()


@lru_cache(maxsize=128)
def is_gradle_repo(workspace: Path) -> bool:
    """Check if workspace is a Gradle project.

    Gradle projects have either build.gradle (Groovy) or build.gradle.kts (Kotlin)
    at the root.

    Args:
        workspace: Path to the workspace directory

    Returns:
        True if this is a Gradle project, False otherwise.

    """
    return (workspace / "build.gradle").exists() or (workspace / "build.gradle.kts").exists()


@lru_cache(maxsize=128)
def is_npm_repo(workspace: Path) -> bool:
    """Check if workspace is an npm/Node.js project.

    npm projects have a package.json at the root.

    Args:
        workspace: Path to the workspace directory

    Returns:
        True if this is an npm project, False otherwise.

    """
    return (workspace / "package.json").exists()


@lru_cache(maxsize=128)
def is_poetry_repo(workspace: Path) -> bool:
    """Check if workspace is a Poetry Python project.

    Poetry projects have a pyproject.toml with [tool.poetry] section.
    This function checks for the file existence (not the section content)
    as a basic detection heuristic.

    Args:
        workspace: Path to the workspace directory

    Returns:
        True if this is likely a Poetry project, False otherwise.

    """
    pyproject = workspace / "pyproject.toml"
    if not pyproject.exists():
        return False

    # Basic heuristic: check if file contains [tool.poetry]
    try:
        content = pyproject.read_text()
        return "[tool.poetry]" in content
    except (OSError, UnicodeDecodeError):
        return False
