"""Tests for DependencyResolver."""

import pytest

from scylla.automation.dependency_resolver import (
    CyclicDependencyError,
    DependencyResolver,
)
from scylla.automation.models import IssueInfo


class TestDependencyResolver:
    """Tests for DependencyResolver class."""

    def test_add_issue(self):
        """Test adding issues to resolver."""
        resolver = DependencyResolver()

        issue = IssueInfo(number=123, title="Test")
        resolver.add_issue(issue)

        assert 123 in resolver.graph.issues
        assert resolver.graph.issues[123] == issue

    def test_add_issue_with_dependencies(self):
        """Test adding issue with dependencies."""
        resolver = DependencyResolver()

        issue = IssueInfo(
            number=123,
            title="Test",
            dependencies=[100, 101],
        )
        resolver.add_issue(issue)

        assert resolver.graph.get_dependencies(123) == [100, 101]

    def test_detect_cycles_no_cycle(self):
        """Test cycle detection with no cycles."""
        resolver = DependencyResolver()

        # Linear chain: 3 -> 2 -> 1
        resolver.add_issue(IssueInfo(number=1, title="Base"))
        resolver.add_issue(IssueInfo(number=2, title="Middle", dependencies=[1]))
        resolver.add_issue(IssueInfo(number=3, title="Top", dependencies=[2]))

        cycles = resolver.detect_cycles()
        assert cycles == []

    def test_detect_cycles_with_cycle(self):
        """Test cycle detection with a cycle."""
        resolver = DependencyResolver()

        # Cycle: 1 -> 2 -> 3 -> 1
        resolver.add_issue(IssueInfo(number=1, title="A", dependencies=[3]))
        resolver.add_issue(IssueInfo(number=2, title="B", dependencies=[1]))
        resolver.add_issue(IssueInfo(number=3, title="C", dependencies=[2]))

        with pytest.raises(CyclicDependencyError):
            resolver.detect_cycles()

    def test_get_ready_issues_none_ready(self):
        """Test getting ready issues when none are ready."""
        resolver = DependencyResolver()

        # Both issues have dependencies
        resolver.add_issue(IssueInfo(number=2, title="B", dependencies=[1]))
        resolver.add_issue(IssueInfo(number=3, title="C", dependencies=[2]))

        ready = resolver.get_ready_issues()
        assert len(ready) == 0

    def test_get_ready_issues_some_ready(self):
        """Test getting ready issues when some are ready."""
        resolver = DependencyResolver()

        # Issue 1 has no dependencies (ready)
        # Issue 2 depends on 1 (not ready)
        resolver.add_issue(IssueInfo(number=1, title="A"))
        resolver.add_issue(IssueInfo(number=2, title="B", dependencies=[1]))

        ready = resolver.get_ready_issues()
        assert len(ready) == 1
        assert ready[0].number == 1

    def test_get_ready_issues_after_completion(self):
        """Test getting ready issues after marking one complete."""
        resolver = DependencyResolver()

        resolver.add_issue(IssueInfo(number=1, title="A"))
        resolver.add_issue(IssueInfo(number=2, title="B", dependencies=[1]))

        # Mark 1 as completed
        resolver.mark_completed(1)

        ready = resolver.get_ready_issues()
        assert len(ready) == 1
        assert ready[0].number == 2

    def test_get_ready_issues_priority_sorting(self):
        """Test that ready issues are sorted by priority."""
        resolver = DependencyResolver()

        resolver.add_issue(IssueInfo(number=1, title="Low", priority=1))
        resolver.add_issue(IssueInfo(number=2, title="High", priority=10))
        resolver.add_issue(IssueInfo(number=3, title="Medium", priority=5))

        ready = resolver.get_ready_issues()

        # Should be sorted by priority descending
        assert [i.number for i in ready] == [2, 3, 1]

    def test_topological_sort_linear(self):
        """Test topological sort with linear dependencies."""
        resolver = DependencyResolver()

        # Chain: 3 -> 2 -> 1
        resolver.add_issue(IssueInfo(number=1, title="Base"))
        resolver.add_issue(IssueInfo(number=2, title="Middle", dependencies=[1]))
        resolver.add_issue(IssueInfo(number=3, title="Top", dependencies=[2]))

        order = resolver.topological_sort()

        # Should be in dependency order
        assert order.index(1) < order.index(2)
        assert order.index(2) < order.index(3)

    def test_topological_sort_diamond(self):
        """Test topological sort with diamond pattern."""
        resolver = DependencyResolver()

        # Diamond: 4 -> {2, 3} -> 1
        resolver.add_issue(IssueInfo(number=1, title="Base"))
        resolver.add_issue(IssueInfo(number=2, title="Left", dependencies=[1]))
        resolver.add_issue(IssueInfo(number=3, title="Right", dependencies=[1]))
        resolver.add_issue(IssueInfo(number=4, title="Top", dependencies=[2, 3]))

        order = resolver.topological_sort()

        # 1 must come before 2 and 3
        assert order.index(1) < order.index(2)
        assert order.index(1) < order.index(3)
        # 2 and 3 must come before 4
        assert order.index(2) < order.index(4)
        assert order.index(3) < order.index(4)

    def test_topological_sort_with_cycle(self):
        """Test topological sort fails with cycle."""
        resolver = DependencyResolver()

        # Cycle: 1 -> 2 -> 1
        resolver.add_issue(IssueInfo(number=1, title="A", dependencies=[2]))
        resolver.add_issue(IssueInfo(number=2, title="B", dependencies=[1]))

        with pytest.raises(CyclicDependencyError):
            resolver.topological_sort()

    def test_get_stats(self):
        """Test getting resolver statistics."""
        resolver = DependencyResolver()

        resolver.add_issue(IssueInfo(number=1, title="A"))
        resolver.add_issue(IssueInfo(number=2, title="B", dependencies=[1]))
        resolver.add_issue(IssueInfo(number=3, title="C", dependencies=[2]))

        resolver.mark_completed(1)

        stats = resolver.get_stats()

        assert stats["total_issues"] == 3
        assert stats["completed_issues"] == 1
        assert stats["remaining_issues"] == 2
        assert stats["ready_issues"] == 1  # Issue 2 is now ready

    def test_mark_completed(self):
        """Test marking issues as completed."""
        resolver = DependencyResolver()

        resolver.add_issue(IssueInfo(number=1, title="A"))
        resolver.mark_completed(1)

        assert 1 in resolver.completed

        # Should not appear in ready issues
        ready = resolver.get_ready_issues()
        assert 1 not in [i.number for i in ready]
