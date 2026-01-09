"""Unit tests for experiment resume functionality."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from scylla.e2e.checkpoint import E2ECheckpoint, save_checkpoint
from scylla.e2e.models import (
    ExperimentConfig,
    SubTestConfig,
    TierConfig,
    TierID,
)


@pytest.fixture
def experiment_config() -> ExperimentConfig:
    """Create a minimal experiment configuration for testing."""
    return ExperimentConfig(
        experiment_id="test-resume",
        task_repo="https://github.com/test/repo",
        task_commit="abc123",
        task_prompt_file=Path("/tmp/prompt.md"),
        models=["claude-sonnet-4-5-20250929"],
        runs_per_subtest=2,
        tiers_to_run=[TierID.T0],
        judge_models=["claude-opus-4-5-20251101"],
        tiebreaker_model="claude-opus-4-5-20251101",
        parallel_subtests=2,
        timeout_seconds=300,
    )


@pytest.fixture
def tier_config() -> TierConfig:
    """Create a minimal tier configuration for testing."""
    return TierConfig(
        id="T0",
        name="Baseline",
        description="Test tier",
        system_prompt_mode="empty",
        subtests=[
            SubTestConfig(id="T0_00", description="Test 1"),
            SubTestConfig(id="T0_01", description="Test 2"),
        ],
    )


@pytest.fixture
def checkpoint(tmp_path: Path) -> tuple[E2ECheckpoint, Path]:
    """Create a checkpoint and its save path."""
    checkpoint_path = tmp_path / "checkpoint.json"
    checkpoint = E2ECheckpoint(
        experiment_id="test-resume",
        experiment_dir=str(tmp_path),
        config_hash="test-hash",
        completed_runs={},
        started_at=datetime.now(UTC).isoformat(),
        last_updated_at=datetime.now(UTC).isoformat(),
        status="running",
        rate_limit_source=None,
        rate_limit_until=None,
        pause_count=0,
        pid=12345,
    )
    save_checkpoint(checkpoint, checkpoint_path)
    return checkpoint, checkpoint_path


class TestResumeAfterAgentCrash:
    """Tests for resuming after crash during agent execution."""

    def test_skip_completed_agent_result(self, tmp_path: Path) -> None:
        """Verify completed agent runs are not re-executed."""
        # Setup: Create a completed agent result
        run_dir = tmp_path / "run_01"
        agent_dir = run_dir / "agent"
        agent_dir.mkdir(parents=True)

        agent_result = {
            "exit_code": 0,
            "token_stats": {
                "input_tokens": 100,
                "output_tokens": 50,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
            },
            "cost_usd": 0.01,
        }
        (agent_dir / "result.json").write_text(json.dumps(agent_result))

        # Verify result validation passes
        from scylla.e2e.subtest_executor import _has_valid_agent_result

        assert _has_valid_agent_result(run_dir) is True

    def test_invalid_agent_result_triggers_rerun(self, tmp_path: Path) -> None:
        """Verify invalid agent results trigger re-run."""
        run_dir = tmp_path / "run_01"
        agent_dir = run_dir / "agent"
        agent_dir.mkdir(parents=True)

        # Invalid: missing required fields
        invalid_result = {"exit_code": 0}
        (agent_dir / "result.json").write_text(json.dumps(invalid_result))

        from scylla.e2e.subtest_executor import _has_valid_agent_result

        assert _has_valid_agent_result(run_dir) is False

    def test_corrupted_agent_json_triggers_rerun(self, tmp_path: Path) -> None:
        """Verify corrupted JSON triggers re-run."""
        run_dir = tmp_path / "run_01"
        agent_dir = run_dir / "agent"
        agent_dir.mkdir(parents=True)

        (agent_dir / "result.json").write_text("{ invalid json")

        from scylla.e2e.subtest_executor import _has_valid_agent_result

        assert _has_valid_agent_result(run_dir) is False


class TestResumeAfterJudgeCrash:
    """Tests for resuming after crash during judge evaluation."""

    def test_skip_completed_judge_result(self, tmp_path: Path) -> None:
        """Verify completed judge runs are not re-executed."""
        run_dir = tmp_path / "run_01"
        judge_dir = run_dir / "judge"
        judge_dir.mkdir(parents=True)

        judge_result = {
            "score": 1.0,
            "passed": True,
            "grade": "A",
            "reasoning": "Test passed",
        }
        (judge_dir / "result.json").write_text(json.dumps(judge_result))

        from scylla.e2e.subtest_executor import _has_valid_judge_result

        assert _has_valid_judge_result(run_dir) is True

    def test_invalid_judge_result_triggers_rerun(self, tmp_path: Path) -> None:
        """Verify invalid judge results trigger re-run."""
        run_dir = tmp_path / "run_01"
        judge_dir = run_dir / "judge"
        judge_dir.mkdir(parents=True)

        # Invalid: missing required fields
        invalid_result = {"score": 1.0}
        (judge_dir / "result.json").write_text(json.dumps(invalid_result))

        from scylla.e2e.subtest_executor import _has_valid_judge_result

        assert _has_valid_judge_result(run_dir) is False

    def test_agent_preserved_after_judge_crash(self, tmp_path: Path) -> None:
        """Verify agent results are preserved when judge crashes."""
        run_dir = tmp_path / "run_01"
        agent_dir = run_dir / "agent"
        agent_dir.mkdir(parents=True)

        # Completed agent
        agent_result = {
            "exit_code": 0,
            "token_stats": {
                "input_tokens": 100,
                "output_tokens": 50,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
            },
            "cost_usd": 0.01,
        }
        (agent_dir / "result.json").write_text(json.dumps(agent_result))

        # No judge result (crashed before completion)
        from scylla.e2e.subtest_executor import _has_valid_agent_result, _has_valid_judge_result

        # Agent should be valid and preserved
        assert _has_valid_agent_result(run_dir) is True
        # Judge should be invalid and re-run
        assert _has_valid_judge_result(run_dir) is False


class TestResumeAfterSignal:
    """Tests for resuming after SIGINT or other signals."""

    def test_checkpoint_saved_with_interrupted_status(
        self, tmp_path: Path, checkpoint: tuple[E2ECheckpoint, Path]
    ) -> None:
        """Verify checkpoint is saved with interrupted status."""
        cp, cp_path = checkpoint

        # Simulate interrupt by updating status
        cp.status = "interrupted"
        cp.last_updated_at = datetime.now(UTC).isoformat()
        save_checkpoint(cp, cp_path)

        # Reload and verify
        loaded_data = json.loads(cp_path.read_text())
        assert loaded_data["status"] == "interrupted"

    def test_resume_from_interrupted_checkpoint(
        self, tmp_path: Path, checkpoint: tuple[E2ECheckpoint, Path]
    ) -> None:
        """Verify resume works from interrupted checkpoint."""
        cp, cp_path = checkpoint

        # Mark some runs as completed before interrupt using proper API
        cp.mark_run_completed("T0", "T0_00", 1)
        cp.status = "interrupted"

        # Test in-memory state before serialization
        assert cp.status == "interrupted"
        assert cp.is_run_completed("T0", "T0_00", 1) is True
        assert cp.is_run_completed("T0", "T0_00", 2) is False

        # Verify checkpoint can be saved
        save_checkpoint(cp, cp_path)
        assert cp_path.exists()


class TestResumePartialTier:
    """Tests for resuming with partial tier completion."""

    def test_resume_skips_completed_subtests(
        self, tmp_path: Path, checkpoint: tuple[E2ECheckpoint, Path]
    ) -> None:
        """Resume should skip completed subtests in partial tier."""
        cp, cp_path = checkpoint

        # Mark first subtest as fully completed
        cp.completed_runs = {
            "T0": {
                "T0_00": {1: "passed", 2: "passed"},  # Both runs completed
                "T0_01": {},  # Not started
            }
        }
        save_checkpoint(cp, cp_path)

        # Verify checkpoint state
        assert cp.is_run_completed("T0", "T0_00", 1) is True
        assert cp.is_run_completed("T0", "T0_00", 2) is True
        assert cp.is_run_completed("T0", "T0_01", 1) is False

    def test_partial_subtest_completion(
        self, tmp_path: Path, checkpoint: tuple[E2ECheckpoint, Path]
    ) -> None:
        """Resume should continue partial subtest from where it stopped."""
        cp, cp_path = checkpoint

        # First run of subtest completed, second not started
        cp.completed_runs = {
            "T0": {
                "T0_00": {1: "passed"},  # Only run 1 completed
            }
        }
        save_checkpoint(cp, cp_path)

        assert cp.is_run_completed("T0", "T0_00", 1) is True
        assert cp.is_run_completed("T0", "T0_00", 2) is False


class TestResumeCompleteExperiment:
    """Tests for resuming fully completed experiments."""

    def test_resume_completed_reports_results(
        self, tmp_path: Path, checkpoint: tuple[E2ECheckpoint, Path]
    ) -> None:
        """Resume of completed experiment should report results without re-running."""
        cp, cp_path = checkpoint

        # Mark all runs as completed
        cp.completed_runs = {
            "T0": {
                "T0_00": {1: "passed", 2: "passed"},
                "T0_01": {1: "passed", 2: "passed"},
            }
        }
        cp.status = "completed"
        save_checkpoint(cp, cp_path)

        # Verify all runs are marked completed
        assert cp.is_run_completed("T0", "T0_00", 1) is True
        assert cp.is_run_completed("T0", "T0_00", 2) is True
        assert cp.is_run_completed("T0", "T0_01", 1) is True
        assert cp.is_run_completed("T0", "T0_01", 2) is True
        assert cp.status == "completed"


class TestResumeConfigMismatch:
    """Tests for handling config mismatches during resume."""

    def test_config_hash_mismatch_raises_error(
        self,
        tmp_path: Path,
        checkpoint: tuple[E2ECheckpoint, Path],
        experiment_config: ExperimentConfig,
    ) -> None:
        """Resume with different config should error."""
        cp, cp_path = checkpoint

        # Original checkpoint with one hash
        cp.config_hash = "original-hash"
        save_checkpoint(cp, cp_path)

        # Modified config (different hash)
        from scylla.e2e.checkpoint import validate_checkpoint_config

        modified_config = experiment_config
        modified_config.runs_per_subtest = 5  # Changed from 2 to 5

        # Validation should fail
        assert validate_checkpoint_config(cp, modified_config) is False


class TestCheckpointOperations:
    """Tests for checkpoint save/load operations."""

    def test_save_and_load_checkpoint(
        self, tmp_path: Path, checkpoint: tuple[E2ECheckpoint, Path]
    ) -> None:
        """Verify checkpoint can be saved and loaded."""
        cp, cp_path = checkpoint

        from scylla.e2e.checkpoint import load_checkpoint

        loaded = load_checkpoint(cp_path)
        assert loaded.experiment_id == cp.experiment_id
        assert loaded.config_hash == cp.config_hash
        assert loaded.status == cp.status

    def test_checkpoint_tracks_run_completion(self, checkpoint: tuple[E2ECheckpoint, Path]) -> None:
        """Verify checkpoint correctly tracks run completion."""
        cp, _ = checkpoint

        # Initially no runs completed
        assert cp.is_run_completed("T0", "T0_00", 1) is False

        # Mark run as completed
        cp.mark_run_completed("T0", "T0_00", 1)
        assert cp.is_run_completed("T0", "T0_00", 1) is True

        # Unmark run
        cp.unmark_run_completed("T0", "T0_00", 1)
        assert cp.is_run_completed("T0", "T0_00", 1) is False

    def test_checkpoint_get_completed_run_count(
        self, checkpoint: tuple[E2ECheckpoint, Path]
    ) -> None:
        """Verify completed run count calculation."""
        cp, _ = checkpoint

        assert cp.get_completed_run_count() == 0

        # Mark some runs as completed
        cp.mark_run_completed("T0", "T0_00", 1)
        cp.mark_run_completed("T0", "T0_00", 2)
        cp.mark_run_completed("T0", "T0_01", 1)

        assert cp.get_completed_run_count() == 3
