"""Unit tests for subtest executor functions."""

from __future__ import annotations

from pathlib import Path

from scylla.e2e.models import JudgeResultSummary
from scylla.e2e.subtest_executor import SubTestExecutor, _move_to_failed


class TestMoveToFailed:
    """Tests for _move_to_failed function."""

    def test_move_creates_failed_dir(self, tmp_path: Path) -> None:
        """Test that .failed/ directory is created."""
        run_dir = tmp_path / "subtest" / "run_01"
        run_dir.mkdir(parents=True)
        (run_dir / "output.txt").write_text("test output")

        new_path = _move_to_failed(run_dir)

        assert (tmp_path / "subtest" / ".failed").exists()
        assert new_path.name == "run_01_attempt_01"
        assert not run_dir.exists()
        assert (new_path / "output.txt").exists()

    def test_move_increments_attempt(self, tmp_path: Path) -> None:
        """Test that attempt number increments."""
        subtest_dir = tmp_path / "subtest"
        failed_dir = subtest_dir / ".failed"
        failed_dir.mkdir(parents=True)
        (failed_dir / "run_01_attempt_01").mkdir()

        run_dir = subtest_dir / "run_01"
        run_dir.mkdir()

        new_path = _move_to_failed(run_dir)

        assert new_path.name == "run_01_attempt_02"

    def test_move_preserves_contents(self, tmp_path: Path) -> None:
        """Test that all contents are preserved during move."""
        run_dir = tmp_path / "subtest" / "run_03"
        run_dir.mkdir(parents=True)
        (run_dir / "output.txt").write_text("agent output")
        (run_dir / "stderr.log").write_text("error log")
        (run_dir / "run_result.json").write_text('{"exit_code": -1}')

        new_path = _move_to_failed(run_dir)

        assert (new_path / "output.txt").read_text() == "agent output"
        assert (new_path / "stderr.log").read_text() == "error log"
        assert (new_path / "run_result.json").read_text() == '{"exit_code": -1}'

    def test_move_with_custom_attempt(self, tmp_path: Path) -> None:
        """Test move with custom attempt number."""
        run_dir = tmp_path / "subtest" / "run_01"
        run_dir.mkdir(parents=True)

        new_path = _move_to_failed(run_dir, attempt=5)

        assert new_path.name == "run_01_attempt_05"

    def test_move_multiple_increments(self, tmp_path: Path) -> None:
        """Test that multiple attempts increment correctly."""
        subtest_dir = tmp_path / "subtest"
        failed_dir = subtest_dir / ".failed"
        failed_dir.mkdir(parents=True)

        # Create attempts 01-03
        (failed_dir / "run_01_attempt_01").mkdir()
        (failed_dir / "run_01_attempt_02").mkdir()
        (failed_dir / "run_01_attempt_03").mkdir()

        run_dir = subtest_dir / "run_01"
        run_dir.mkdir()

        new_path = _move_to_failed(run_dir)

        assert new_path.name == "run_01_attempt_04"


class TestComputeJudgeConsensus:
    """Tests for _compute_judge_consensus method."""

    def test_consensus_all_valid_judges(self) -> None:
        """Test consensus computation with all valid judges."""
        from unittest.mock import MagicMock

        from scylla.e2e.models import ExperimentConfig, TierID

        config = ExperimentConfig(
            experiment_id="test-consensus",
            task_repo="https://github.com/test/repo",
            task_commit="abc123",
            task_prompt_file=Path("prompt.md"),
            language="python",
            tiers_to_run=[TierID.T0],
        )

        # Create executor with mocked dependencies
        executor = SubTestExecutor(config, MagicMock(), MagicMock())

        judges = [
            JudgeResultSummary(
                model="claude-sonnet-4-5",
                score=0.8,
                passed=True,
                grade="B",
                reasoning="Good work",
                judge_number=1,
                is_valid=True,
            ),
            JudgeResultSummary(
                model="claude-opus-4-6",
                score=0.9,
                passed=True,
                grade="A",
                reasoning="Excellent",
                judge_number=2,
                is_valid=True,
            ),
        ]

        score, passed, grade = executor._compute_judge_consensus(judges)

        assert abs(score - 0.85) < 0.001  # Average of 0.8 and 0.9
        assert passed is True
        assert grade == "A"  # Grade for 0.85 (>= 0.80)

    def test_consensus_with_invalid_judge(self) -> None:
        """Test consensus computation with one invalid judge (heuristic fallback)."""
        from unittest.mock import MagicMock

        from scylla.e2e.models import ExperimentConfig, TierID

        config = ExperimentConfig(
            experiment_id="test-consensus",
            task_repo="https://github.com/test/repo",
            task_commit="abc123",
            task_prompt_file=Path("prompt.md"),
            language="python",
            tiers_to_run=[TierID.T0],
        )

        executor = SubTestExecutor(config, MagicMock(), MagicMock())

        judges = [
            JudgeResultSummary(
                model="claude-sonnet-4-5",
                score=0.9,
                passed=True,
                grade="A",
                reasoning="Valid judgment",
                judge_number=1,
                is_valid=True,
            ),
            JudgeResultSummary(
                model="claude-haiku-4-5",
                score=0.0,
                passed=False,
                grade="F",
                reasoning="Heuristic fallback",
                judge_number=2,
                is_valid=False,
            ),
        ]

        score, passed, grade = executor._compute_judge_consensus(judges)

        # Both judges included in consensus computation (we compute score from all)
        # Note: _compute_judge_consensus doesn't filter by is_valid
        # The filtering happens in _regenerate_consensus
        assert abs(score - 0.45) < 0.001  # Average of 0.9 and 0.0
        assert passed is False  # 1 passed, 1 failed
        assert grade == "C"  # Grade for 0.45 (0.40 <= 0.45 < 0.60)

    def test_consensus_no_judges(self) -> None:
        """Test consensus computation with no judges."""
        from unittest.mock import MagicMock

        from scylla.e2e.models import ExperimentConfig, TierID

        config = ExperimentConfig(
            experiment_id="test-consensus",
            task_repo="https://github.com/test/repo",
            task_commit="abc123",
            task_prompt_file=Path("prompt.md"),
            language="python",
            tiers_to_run=[TierID.T0],
        )

        executor = SubTestExecutor(config, MagicMock(), MagicMock())

        score, passed, grade = executor._compute_judge_consensus([])

        assert score is None
        assert passed is None
        assert grade is None
