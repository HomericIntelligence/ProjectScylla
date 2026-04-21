"""Unit tests for stage_commit_agent_changes and stage_promote_to_completed."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scylla.e2e.models import TierID


def _make_ctx(
    tmp_path: Path,
    *,
    exit_code: int = 0,
    input_tokens: int = 100,
    output_tokens: int = 50,
    workspace_exists: bool = True,
) -> MagicMock:
    """Build a minimal RunContext mock for testing."""
    from scylla.adapters.base import AdapterResult, AdapterTokenStats

    ctx = MagicMock()
    ctx.tier_id = TierID.T0
    ctx.subtest = MagicMock()
    ctx.subtest.id = "00"
    ctx.run_number = 1

    run_dir = tmp_path / "in_progress" / "T0" / "00" / "run_01"
    run_dir.mkdir(parents=True, exist_ok=True)
    ctx.run_dir = run_dir

    if workspace_exists:
        workspace = run_dir / "workspace"
        workspace.mkdir()
        ctx.workspace = workspace
    else:
        ctx.workspace = run_dir / "workspace"

    ctx.agent_result = AdapterResult(
        exit_code=exit_code,
        stdout="",
        stderr="",
        token_stats=AdapterTokenStats(input_tokens=input_tokens, output_tokens=output_tokens),
        cost_usd=0.01,
        api_calls=1,
    )
    return ctx


class TestStageCommitAgentChanges:
    """Tests for stage_commit_agent_changes."""

    def test_infrastructure_failure_moves_to_failed(self, tmp_path: Path) -> None:
        """exit_code=-1 with zero tokens moves run to .failed/ and raises."""
        from scylla.e2e.stages import stage_commit_agent_changes

        ctx = _make_ctx(tmp_path, exit_code=-1, input_tokens=0, output_tokens=0)

        with pytest.raises(RuntimeError, match="Infrastructure failure"):
            stage_commit_agent_changes(ctx)

        # Run dir should have been moved to .failed/
        failed_dir = ctx.run_dir.parent / ".failed" / "run_01"
        assert failed_dir.exists()
        assert not (tmp_path / "in_progress" / "T0" / "00" / "run_01").exists()

    def test_non_infra_failure_does_not_raise(self, tmp_path: Path) -> None:
        """exit_code=1 (agent error but tokens consumed) proceeds normally."""
        from scylla.e2e.stages import stage_commit_agent_changes

        ctx = _make_ctx(tmp_path, exit_code=1, input_tokens=500, output_tokens=200)

        # Mock subprocess.run to succeed
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            stage_commit_agent_changes(ctx)

        # Should not raise, run_dir still exists
        assert ctx.run_dir.exists()

    def test_successful_commit_calls_git(self, tmp_path: Path) -> None:
        """Normal run calls git add -A then git commit."""
        from scylla.e2e.stages import stage_commit_agent_changes

        ctx = _make_ctx(tmp_path, exit_code=0, input_tokens=100, output_tokens=50)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")
            stage_commit_agent_changes(ctx)

        calls = mock_run.call_args_list
        assert len(calls) == 2
        assert calls[0][0][0] == ["git", "add", "-A"]
        assert calls[1][0][0][0:2] == ["git", "commit"]

    def test_missing_workspace_skips_commit(self, tmp_path: Path) -> None:
        """If workspace doesn't exist, commit is skipped (no error raised)."""
        from scylla.e2e.stages import stage_commit_agent_changes

        ctx = _make_ctx(
            tmp_path, exit_code=0, input_tokens=100, output_tokens=50, workspace_exists=False
        )

        with patch("subprocess.run") as mock_run:
            stage_commit_agent_changes(ctx)
            mock_run.assert_not_called()

    def test_exit_minus_one_with_tokens_is_not_infra_failure(self, tmp_path: Path) -> None:
        """exit_code=-1 but with tokens consumed is NOT an infrastructure failure."""
        from scylla.e2e.stages import stage_commit_agent_changes

        ctx = _make_ctx(tmp_path, exit_code=-1, input_tokens=500, output_tokens=200)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")
            stage_commit_agent_changes(ctx)

        # Should not raise
        assert ctx.run_dir.exists()

    def test_no_agent_result_skips_infra_check(self, tmp_path: Path) -> None:
        """If agent_result is None, infra failure check is skipped."""
        from scylla.e2e.stages import stage_commit_agent_changes

        ctx = _make_ctx(tmp_path, exit_code=0, input_tokens=100, output_tokens=50)
        ctx.agent_result = None

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")
            stage_commit_agent_changes(ctx)

        assert ctx.run_dir.exists()


class TestStagePromoteToCompleted:
    """Tests for stage_promote_to_completed."""

    def test_moves_run_dir_to_completed(self, tmp_path: Path) -> None:
        """Run directory is moved from in_progress/ to completed/."""
        from scylla.e2e.stages import stage_promote_to_completed

        ctx = _make_ctx(tmp_path, exit_code=0, input_tokens=100, output_tokens=50)
        # Set up experiment_dir structure
        experiment_dir = tmp_path
        (experiment_dir / "completed" / "T0" / "00").mkdir(parents=True, exist_ok=True)

        original_run_dir = ctx.run_dir
        stage_promote_to_completed(ctx)

        # Old location should be gone
        assert not original_run_dir.exists()
        # New location should exist
        completed_run_dir = experiment_dir / "completed" / "T0" / "00" / "run_01"
        assert completed_run_dir.exists()
        assert ctx.run_dir == completed_run_dir

    def test_updates_ctx_workspace(self, tmp_path: Path) -> None:
        """ctx.workspace is updated to point to new location after promotion."""
        from scylla.e2e.stages import stage_promote_to_completed

        ctx = _make_ctx(tmp_path, exit_code=0, input_tokens=100, output_tokens=50)
        (tmp_path / "completed" / "T0" / "00").mkdir(parents=True, exist_ok=True)

        stage_promote_to_completed(ctx)

        expected_workspace = ctx.run_dir / "workspace"
        assert ctx.workspace == expected_workspace

    def test_promotes_pipeline_baseline(self, tmp_path: Path) -> None:
        """pipeline_baseline.json is copied to completed/ subtest dir."""
        from scylla.e2e.stages import stage_promote_to_completed

        ctx = _make_ctx(tmp_path, exit_code=0, input_tokens=100, output_tokens=50)
        (tmp_path / "completed" / "T0" / "00").mkdir(parents=True, exist_ok=True)

        # Create a pipeline_baseline.json in the in_progress subtest dir
        baseline_src = tmp_path / "in_progress" / "T0" / "00" / "pipeline_baseline.json"
        baseline_src.write_text('{"baseline": true}')

        stage_promote_to_completed(ctx)

        baseline_dst = tmp_path / "completed" / "T0" / "00" / "pipeline_baseline.json"
        assert baseline_dst.exists()
        assert baseline_dst.read_text() == '{"baseline": true}'

    def test_promote_is_noop_when_already_promoted(self, tmp_path: Path) -> None:
        """promote_run_to_completed returns dest without error if already promoted."""
        from scylla.e2e.paths import promote_run_to_completed

        experiment_dir = tmp_path
        # Set up only the completed/ dir (no in_progress/ — already promoted)
        completed_run = experiment_dir / "completed" / "T0" / "00" / "run_01"
        completed_run.mkdir(parents=True)
        (completed_run / "agent").mkdir()
        (completed_run / "agent" / "result.json").write_text("{}")

        result = promote_run_to_completed(experiment_dir, "T0", "00", 1)

        assert result == completed_run
        # Directory still intact
        assert completed_run.exists()
        assert (completed_run / "agent" / "result.json").exists()

    def test_promote_overwrites_existing_completed_on_rerun(self, tmp_path: Path) -> None:
        """promote_run_to_completed replaces dst when both src and dst exist (rerun)."""
        from scylla.e2e.paths import promote_run_to_completed

        experiment_dir = tmp_path
        # Set up the old completed/ dir (stale from prior run)
        completed_run = experiment_dir / "completed" / "T0" / "00" / "run_01"
        completed_run.mkdir(parents=True)
        (completed_run / "stale.txt").write_text("old")

        # Set up fresh in_progress/ dir (new rerun)
        in_progress_run = experiment_dir / "in_progress" / "T0" / "00" / "run_01"
        in_progress_run.mkdir(parents=True)
        (in_progress_run / "agent").mkdir()
        (in_progress_run / "agent" / "result.json").write_text('{"fresh": true}')

        result = promote_run_to_completed(experiment_dir, "T0", "00", 1)

        assert result == completed_run
        # New content present, old stale content gone
        assert (completed_run / "agent" / "result.json").exists()
        assert not (completed_run / "stale.txt").exists()
