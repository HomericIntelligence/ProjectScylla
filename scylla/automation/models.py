"""Pydantic models for automation workflows.

Defines data structures for:
- Issue information and dependencies
- Planning and implementation state
- Worker results and options
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field


class IssueState(str, Enum):
    """GitHub issue state."""

    OPEN = "OPEN"
    CLOSED = "CLOSED"


class IssueInfo(BaseModel):
    """Information about a GitHub issue."""

    number: int
    title: str
    state: IssueState = IssueState.OPEN
    labels: list[str] = Field(default_factory=list)
    dependencies: list[int] = Field(default_factory=list)
    priority: int = 0

    def __hash__(self) -> int:
        """Make IssueInfo hashable for use in sets."""
        return hash(self.number)

    def __eq__(self, other: object) -> bool:
        """Compare issues by number."""
        if not isinstance(other, IssueInfo):
            return NotImplemented
        return self.number == other.number


class ImplementationPhase(str, Enum):
    """Phase of issue implementation."""

    PLANNING = "planning"
    IMPLEMENTING = "implementing"
    TESTING = "testing"
    COMMITTING = "committing"
    PUSHING = "pushing"
    CREATING_PR = "creating_pr"
    COMPLETED = "completed"
    FAILED = "failed"


class ImplementationState(BaseModel):
    """State tracking for issue implementation."""

    issue_number: int
    phase: ImplementationPhase = ImplementationPhase.PLANNING
    worktree_path: str | None = None
    branch_name: str | None = None
    pr_number: int | None = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    error: str | None = None
    attempts: int = 0


class WorkerResult(BaseModel):
    """Result from a worker thread."""

    issue_number: int
    success: bool
    error: str | None = None
    pr_number: int | None = None
    branch_name: str | None = None
    worktree_path: str | None = None


class PlanResult(BaseModel):
    """Result from planning an issue."""

    issue_number: int
    success: bool
    error: str | None = None
    plan_already_exists: bool = False


class PlannerOptions(BaseModel):
    """Options for the Planner."""

    issues: list[int]
    dry_run: bool = False
    force: bool = False
    parallel: int = 3
    system_prompt_file: Path | None = None
    skip_closed: bool = True
    enable_advise: bool = True


class ImplementerOptions(BaseModel):
    """Options for the Implementer."""

    epic_number: int
    analyze_only: bool = False
    health_check: bool = False
    resume: bool = False
    max_workers: int = 3
    skip_closed: bool = True
    auto_merge: bool = True
    dry_run: bool = False


class DependencyGraph(BaseModel):
    """Dependency graph for issues."""

    issues: dict[int, IssueInfo] = Field(default_factory=dict)
    edges: dict[int, list[int]] = Field(default_factory=dict)  # issue_number -> dependencies

    def add_issue(self, issue: IssueInfo) -> None:
        """Add an issue to the graph."""
        self.issues[issue.number] = issue
        if issue.number not in self.edges:
            self.edges[issue.number] = []

    def add_dependency(self, issue_number: int, depends_on: int) -> None:
        """Add a dependency edge.

        Args:
            issue_number: Issue that depends on another
            depends_on: Issue that must be completed first

        Raises:
            ValueError: If source issue doesn't exist in the graph

        Note:
            Dependency issue doesn't need to exist yet - it may be added later.
            This allows building the graph incrementally.

        """
        if issue_number not in self.issues:
            raise ValueError(f"Issue #{issue_number} not in graph")

        if issue_number not in self.edges:
            self.edges[issue_number] = []
        if depends_on not in self.edges[issue_number]:
            self.edges[issue_number].append(depends_on)

    def get_dependencies(self, issue_number: int) -> list[int]:
        """Get direct dependencies for an issue."""
        return self.edges.get(issue_number, [])

    def get_all_dependencies(self, issue_number: int) -> set[int]:
        """Get all transitive dependencies for an issue."""
        deps: set[int] = set()
        to_visit = [issue_number]
        visited: set[int] = set()

        while to_visit:
            current = to_visit.pop()
            if current in visited:
                continue
            visited.add(current)

            for dep in self.get_dependencies(current):
                deps.add(dep)
                to_visit.append(dep)

        return deps
