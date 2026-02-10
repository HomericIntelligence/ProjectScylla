"""Dependency graph resolution for issue implementation.

Provides:
- DAG topological sorting
- Cycle detection
- Priority ordering
- Ready issue discovery
"""

import logging
from collections import defaultdict, deque

from .github_api import fetch_issue_info, prefetch_issue_states
from .models import DependencyGraph, IssueInfo, IssueState

logger = logging.getLogger(__name__)


class CyclicDependencyError(Exception):
    """Raised when a cyclic dependency is detected."""

    pass


class DependencyResolver:
    """Resolves issue dependencies and determines execution order.

    Uses topological sorting to ensure dependencies are satisfied.
    """

    def __init__(self, skip_closed: bool = True):
        """Initialize dependency resolver.

        Args:
            skip_closed: Whether to skip closed issues

        """
        self.graph = DependencyGraph()
        self.skip_closed = skip_closed
        self.completed: set[int] = set()

    def add_issue(self, issue: IssueInfo) -> None:
        """Add an issue to the dependency graph.

        Args:
            issue: IssueInfo to add

        """
        self.graph.add_issue(issue)
        for dep in issue.dependencies:
            self.graph.add_dependency(issue.number, dep)

    def load_epic(self, epic_number: int) -> None:
        """Load an epic issue and all its sub-issues.

        Args:
            epic_number: Epic issue number

        Raises:
            RuntimeError: If epic cannot be loaded

        """
        logger.info(f"Loading epic #{epic_number}")

        # Fetch epic issue
        epic = fetch_issue_info(epic_number)
        self.add_issue(epic)

        # Parse sub-issues from epic body
        sub_issues = self._parse_sub_issues(epic)

        if not sub_issues:
            logger.warning(f"Epic #{epic_number} has no sub-issues")
            return

        # Prefetch states for efficiency
        cached_states = prefetch_issue_states(sub_issues)

        # Fetch each sub-issue and its dependencies
        for issue_num in sub_issues:
            if self.skip_closed and cached_states.get(issue_num) == IssueState.CLOSED:
                logger.info(f"Skipping closed issue #{issue_num}")
                self.completed.add(issue_num)
                continue

            try:
                issue = fetch_issue_info(issue_num)
                self.add_issue(issue)

                # Recursively load dependencies
                self._load_dependencies(issue, cached_states)

            except Exception as e:
                logger.error(f"Failed to load issue #{issue_num}: {e}")

        logger.info(f"Loaded {len(self.graph.issues)} issues from epic")

    def _parse_sub_issues(self, epic: IssueInfo) -> list[int]:
        """Parse sub-issue numbers from epic body.

        Looks for:
        - Task lists: - [ ] #123
        - Links: #123
        - Depends on: #123

        Args:
            epic: Epic issue info

        Returns:
            List of sub-issue numbers

        """
        import re

        from .github_api import gh_issue_json

        sub_issues = []

        # Fetch full body from GitHub

        epic_data = gh_issue_json(epic.number)
        body = epic_data.get("body", "")

        # Pattern 1: Task list items - [ ] #123 or - [x] #123
        task_pattern = r"-\s*\[[ x]\]\s*#(\d+)"
        for match in re.finditer(task_pattern, body):
            sub_issues.append(int(match.group(1)))

        # Pattern 2: Dependencies section
        dep_pattern = r"(?:sub-?issues?|includes?):\s*#(\d+)"
        for match in re.finditer(dep_pattern, body, re.IGNORECASE):
            sub_issues.append(int(match.group(1)))

        # Pattern 3: Issue references in lists
        list_pattern = r"^\s*[-*]\s*#(\d+)"
        for match in re.finditer(list_pattern, body, re.MULTILINE):
            sub_issues.append(int(match.group(1)))

        return list(set(sub_issues))  # Remove duplicates

    def _load_dependencies(
        self,
        issue: IssueInfo,
        cached_states: dict[int, IssueState],
    ) -> None:
        """Recursively load issue dependencies.

        Args:
            issue: Issue to load dependencies for
            cached_states: Cache of issue states

        """
        for dep_num in issue.dependencies:
            if dep_num in self.graph.issues or dep_num in self.completed:
                continue

            if self.skip_closed and cached_states.get(dep_num) == IssueState.CLOSED:
                logger.info(f"Dependency #{dep_num} is closed, marking complete")
                self.completed.add(dep_num)
                continue

            try:
                dep_issue = fetch_issue_info(dep_num)
                self.add_issue(dep_issue)
                self._load_dependencies(dep_issue, cached_states)
            except Exception as e:
                logger.error(f"Failed to load dependency #{dep_num}: {e}")

    def detect_cycles(self) -> list[list[int]]:
        """Detect cyclic dependencies in the graph.

        Returns:
            List of cycles (each cycle is a list of issue numbers)

        Raises:
            CyclicDependencyError: If cycles are detected

        """
        cycles: list[list[int]] = []
        visited: set[int] = set()

        def dfs(node: int, rec_stack: set[int], path: list[int]) -> bool:
            """DFS helper to detect cycles with local state."""
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            try:
                for dep in self.graph.get_dependencies(node):
                    if dep not in visited:
                        if dfs(dep, rec_stack, path):
                            return True
                    elif dep in rec_stack:
                        # Found a cycle
                        cycle_start = path.index(dep)
                        cycles.append(path[cycle_start:] + [dep])
                        return True

                return False
            finally:
                # Always clean up recursion state
                path.pop()
                rec_stack.remove(node)

        for issue_num in self.graph.issues:
            if issue_num not in visited:
                # Use fresh local state for each DFS tree
                if dfs(issue_num, set(), []):
                    logger.error(f"Cycle detected: {cycles[-1]}")

        if cycles:
            raise CyclicDependencyError(f"Found {len(cycles)} dependency cycle(s): {cycles}")

        return cycles

    def get_ready_issues(self) -> list[IssueInfo]:
        """Get issues that are ready to be implemented.

        An issue is ready if all its dependencies are completed.

        Returns:
            List of ready issues, sorted by priority

        """
        ready: list[IssueInfo] = []

        for issue_num, issue in self.graph.issues.items():
            if issue_num in self.completed:
                continue

            # Check if all dependencies are completed
            deps = self.graph.get_dependencies(issue_num)
            if all(dep in self.completed for dep in deps):
                ready.append(issue)

        # Sort by priority (higher priority first)
        ready.sort(key=lambda x: (-x.priority, x.number))

        return ready

    def mark_completed(self, issue_number: int) -> None:
        """Mark an issue as completed.

        Args:
            issue_number: Issue number to mark complete

        """
        self.completed.add(issue_number)
        logger.debug(f"Marked issue #{issue_number} as completed")

    def topological_sort(self) -> list[int]:
        """Perform topological sort of the dependency graph.

        Returns:
            List of issue numbers in topological order

        Raises:
            CyclicDependencyError: If graph contains cycles

        """
        # First check for cycles
        self.detect_cycles()

        # Build reverse adjacency list (node -> list of nodes that depend on it)
        # This is O(E) instead of O(V²) search in the while loop
        reverse_deps: dict[int, list[int]] = defaultdict(list)
        in_degree: dict[int, int] = defaultdict(int)

        for issue_num in self.graph.issues:
            # Initialize in-degree
            if issue_num not in in_degree:
                in_degree[issue_num] = 0
            # Build reverse adjacency
            for dep in self.graph.get_dependencies(issue_num):
                reverse_deps[dep].append(issue_num)
                in_degree[issue_num] += 1

        # Find all nodes with in-degree 0 (no dependencies)
        queue: deque[int] = deque()
        for issue_num in self.graph.issues:
            if in_degree[issue_num] == 0:
                queue.append(issue_num)

        result: list[int] = []

        while queue:
            node = queue.popleft()
            result.append(node)

            # Process all issues that depend on this node (O(1) lookup now)
            for dependent in reverse_deps[node]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        if len(result) != len(self.graph.issues):
            raise CyclicDependencyError("Graph contains cycles")

        return result

    def get_stats(self) -> dict[str, int]:
        """Get statistics about the dependency graph.

        Returns:
            Dictionary with statistics

        """
        return {
            "total_issues": len(self.graph.issues),
            "completed_issues": len(self.completed),
            "remaining_issues": len(self.graph.issues) - len(self.completed),
            "ready_issues": len(self.get_ready_issues()),
        }
