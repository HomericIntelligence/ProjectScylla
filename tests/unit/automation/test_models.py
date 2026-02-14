"""Tests for automation Pydantic models."""

from datetime import datetime

from scylla.automation.models import (
    DependencyGraph,
    ImplementationPhase,
    ImplementationState,
    ImplementerOptions,
    IssueInfo,
    IssueState,
    PlannerOptions,
    PlanResult,
    WorkerResult,
)


class TestIssueInfo:
    """Tests for IssueInfo model."""

    def test_basic_creation(self):
        """Test creating a basic IssueInfo."""
        issue = IssueInfo(
            number=123,
            title="Test issue",
        )

        assert issue.number == 123
        assert issue.title == "Test issue"
        assert issue.state == IssueState.OPEN
        assert issue.labels == []
        assert issue.dependencies == []
        assert issue.priority == 0

    def test_with_dependencies(self):
        """Test IssueInfo with dependencies."""
        issue = IssueInfo(
            number=123,
            title="Test issue",
            dependencies=[100, 101, 102],
        )

        assert issue.dependencies == [100, 101, 102]

    def test_hashable(self):
        """Test IssueInfo is hashable."""
        issue1 = IssueInfo(number=123, title="Test")
        issue2 = IssueInfo(number=123, title="Different title")
        issue3 = IssueInfo(number=456, title="Test")

        # Same number should hash to same value
        assert hash(issue1) == hash(issue2)
        # Different number should hash differently (usually)
        assert hash(issue1) != hash(issue3)

        # Can be used in sets
        issues = {issue1, issue2, issue3}
        assert len(issues) == 2  # issue1 and issue2 are considered equal

    def test_equality(self):
        """Test IssueInfo equality."""
        issue1 = IssueInfo(number=123, title="Test")
        issue2 = IssueInfo(number=123, title="Different title")
        issue3 = IssueInfo(number=456, title="Test")

        assert issue1 == issue2  # Same number
        assert issue1 != issue3  # Different number


class TestImplementationState:
    """Tests for ImplementationState model."""

    def test_default_values(self):
        """Test ImplementationState default values."""
        state = ImplementationState(issue_number=123)

        assert state.issue_number == 123
        assert state.phase == ImplementationPhase.PLANNING
        assert state.worktree_path is None
        assert state.branch_name is None
        assert state.pr_number is None
        assert state.session_id is None
        assert isinstance(state.started_at, datetime)
        assert state.completed_at is None
        assert state.error is None
        assert state.attempts == 0

    def test_serialization(self):
        """Test ImplementationState JSON serialization."""
        state = ImplementationState(
            issue_number=123,
            phase=ImplementationPhase.IMPLEMENTING,
            worktree_path="/tmp/worktree",
            branch_name="123-test",
            session_id="abc123",
        )

        # Serialize to JSON
        json_str = state.model_dump_json()
        assert "123" in json_str
        assert "implementing" in json_str
        assert "abc123" in json_str

        # Deserialize from JSON
        restored = ImplementationState.model_validate_json(json_str)
        assert restored.issue_number == state.issue_number
        assert restored.phase == state.phase
        assert restored.worktree_path == state.worktree_path
        assert restored.session_id == state.session_id

    def test_retrospective_phase(self):
        """Test RETROSPECTIVE phase in ImplementationPhase enum."""
        assert ImplementationPhase.RETROSPECTIVE == "retrospective"

        # Verify it can be used in state
        state = ImplementationState(
            issue_number=123,
            phase=ImplementationPhase.RETROSPECTIVE,
        )
        assert state.phase == ImplementationPhase.RETROSPECTIVE

    def test_follow_up_issues_phase(self):
        """Test FOLLOW_UP_ISSUES phase in ImplementationPhase enum."""
        assert ImplementationPhase.FOLLOW_UP_ISSUES == "follow_up_issues"

        # Verify it can be used in state
        state = ImplementationState(
            issue_number=123,
            phase=ImplementationPhase.FOLLOW_UP_ISSUES,
        )
        assert state.phase == ImplementationPhase.FOLLOW_UP_ISSUES


class TestDependencyGraph:
    """Tests for DependencyGraph model."""

    def test_add_issue(self):
        """Test adding issues to graph."""
        graph = DependencyGraph()
        issue = IssueInfo(number=123, title="Test")

        graph.add_issue(issue)

        assert 123 in graph.issues
        assert graph.issues[123] == issue
        assert 123 in graph.edges

    def test_add_dependency(self):
        """Test adding dependency edges."""
        graph = DependencyGraph()

        # Add issues first (now required)
        graph.add_issue(IssueInfo(number=123, title="Main"))
        graph.add_issue(IssueInfo(number=100, title="Dep 1"))
        graph.add_issue(IssueInfo(number=101, title="Dep 2"))

        graph.add_dependency(123, 100)
        graph.add_dependency(123, 101)

        assert graph.get_dependencies(123) == [100, 101]

    def test_get_all_dependencies(self):
        """Test transitive dependency resolution."""
        graph = DependencyGraph()

        # Add issues first
        graph.add_issue(IssueInfo(number=123, title="Main"))
        graph.add_issue(IssueInfo(number=100, title="Mid"))
        graph.add_issue(IssueInfo(number=50, title="Base"))

        # Create chain: 123 -> 100 -> 50
        graph.add_dependency(123, 100)
        graph.add_dependency(100, 50)

        deps = graph.get_all_dependencies(123)

        assert deps == {100, 50}

    def test_get_all_dependencies_diamond(self):
        """Test transitive dependencies with diamond pattern."""
        graph = DependencyGraph()

        # Add issues first
        graph.add_issue(IssueInfo(number=123, title="Main"))
        graph.add_issue(IssueInfo(number=100, title="Mid 1"))
        graph.add_issue(IssueInfo(number=101, title="Mid 2"))
        graph.add_issue(IssueInfo(number=50, title="Base"))

        # Create diamond: 123 -> {100, 101} -> 50
        graph.add_dependency(123, 100)
        graph.add_dependency(123, 101)
        graph.add_dependency(100, 50)
        graph.add_dependency(101, 50)

        deps = graph.get_all_dependencies(123)

        assert deps == {100, 101, 50}


class TestPlanResult:
    """Tests for PlanResult model."""

    def test_successful_plan(self):
        """Test successful plan result."""
        result = PlanResult(
            issue_number=123,
            success=True,
        )

        assert result.issue_number == 123
        assert result.success is True
        assert result.error is None
        assert result.plan_already_exists is False

    def test_failed_plan(self):
        """Test failed plan result."""
        result = PlanResult(
            issue_number=123,
            success=False,
            error="Something went wrong",
        )

        assert result.success is False
        assert result.error == "Something went wrong"


class TestWorkerResult:
    """Tests for WorkerResult model."""

    def test_successful_implementation(self):
        """Test successful implementation result."""
        result = WorkerResult(
            issue_number=123,
            success=True,
            pr_number=456,
            branch_name="123-test",
            worktree_path="/tmp/worktree",
        )

        assert result.issue_number == 123
        assert result.success is True
        assert result.pr_number == 456
        assert result.branch_name == "123-test"

    def test_failed_implementation(self):
        """Test failed implementation result."""
        result = WorkerResult(
            issue_number=123,
            success=False,
            error="Implementation failed",
        )

        assert result.success is False
        assert result.error == "Implementation failed"
        assert result.pr_number is None


class TestPlannerOptions:
    """Tests for PlannerOptions model."""

    def test_default_values(self):
        """Test PlannerOptions default values."""
        options = PlannerOptions(issues=[123, 456])

        assert options.issues == [123, 456]
        assert options.dry_run is False
        assert options.force is False
        assert options.parallel == 3
        assert options.system_prompt_file is None
        assert options.skip_closed is True
        assert options.enable_advise is True

    def test_custom_values(self):
        """Test PlannerOptions with custom values."""
        from pathlib import Path

        options = PlannerOptions(
            issues=[123],
            dry_run=True,
            force=True,
            parallel=5,
            system_prompt_file=Path("/tmp/prompt.md"),
            skip_closed=False,
            enable_advise=False,
        )

        assert options.dry_run is True
        assert options.force is True
        assert options.parallel == 5
        assert options.skip_closed is False
        assert options.enable_advise is False


class TestImplementerOptions:
    """Tests for ImplementerOptions model."""

    def test_default_values(self):
        """Test ImplementerOptions default values."""
        options = ImplementerOptions(epic_number=123)

        assert options.epic_number == 123
        assert options.analyze_only is False
        assert options.health_check is False
        assert options.resume is False
        assert options.max_workers == 3
        assert options.skip_closed is True
        assert options.auto_merge is True
        assert options.dry_run is False
        assert options.enable_retrospective is False
        assert options.enable_follow_up is True  # Enabled by default

    def test_custom_values(self):
        """Test ImplementerOptions with custom values."""
        options = ImplementerOptions(
            epic_number=456,
            analyze_only=True,
            health_check=True,
            resume=True,
            max_workers=5,
            skip_closed=False,
            auto_merge=False,
            dry_run=True,
            enable_retrospective=True,
            enable_follow_up=True,
        )

        assert options.epic_number == 456
        assert options.analyze_only is True
        assert options.health_check is True
        assert options.resume is True
        assert options.max_workers == 5
        assert options.skip_closed is False
        assert options.auto_merge is False
        assert options.dry_run is True
        assert options.enable_retrospective is True
        assert options.enable_follow_up is True
