"""Tests for experiment rerun functionality."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scylla.e2e.models import ExperimentConfig, SubTestConfig, TierConfig, TierID
from scylla.e2e.rerun import (
    RerunStats,
    RunStatus,
    RunToRerun,
    _classify_run_status,
    scan_runs_needing_rerun,
)


class TestRunStatus:
    """Tests for RunStatus enum."""

    def test_run_status_values(self) -> None:
        """Test RunStatus enum has expected values."""
        assert RunStatus.COMPLETED.value == "completed"
        assert RunStatus.MISSING.value == "missing"
        assert RunStatus.FAILED.value == "failed"
        assert RunStatus.PARTIAL.value == "partial"
        assert RunStatus.RESULTS.value == "results"


class TestRerunStats:
    """Tests for RerunStats dataclass."""

    def test_rerun_stats_initialization(self) -> None:
        """Test RerunStats initializes with zero values."""
        stats = RerunStats()
        assert stats.total_expected_runs == 0
        assert stats.completed == 0
        assert stats.results == 0
        assert stats.failed == 0
        assert stats.partial == 0
        assert stats.missing == 0
        assert stats.runs_rerun_success == 0
        assert stats.runs_rerun_failed == 0
        assert stats.runs_regenerated == 0
        assert stats.runs_skipped_by_filter == 0

    def test_print_summary(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test print_summary outputs expected format."""
        stats = RerunStats(
            total_expected_runs=10,
            completed=5,
            results=1,
            failed=2,
            partial=1,
            missing=1,
            runs_rerun_success=3,
            runs_rerun_failed=1,
            runs_regenerated=1,
        )
        stats.print_summary()

        captured = capsys.readouterr()
        assert "Total expected runs:     10" in captured.out
        assert "completed:           5" in captured.out
        assert "results:             1" in captured.out
        assert "failed:              2" in captured.out
        assert "partial:             1" in captured.out
        assert "missing:             1" in captured.out
        assert "Successfully rerun:      3" in captured.out
        assert "Failed rerun:            1" in captured.out
        assert "Regenerated:             1" in captured.out


class TestRunToRerun:
    """Tests for RunToRerun dataclass."""

    def test_run_to_rerun_creation(self, tmp_path: Path) -> None:
        """Test RunToRerun dataclass creation."""
        run_dir = tmp_path / "run_01"
        run = RunToRerun(
            tier_id="T0",
            subtest_id="00",
            run_number=1,
            run_dir=run_dir,
            status=RunStatus.MISSING,
            reason="Run never started",
        )

        assert run.tier_id == "T0"
        assert run.subtest_id == "00"
        assert run.run_number == 1
        assert run.run_dir == run_dir
        assert run.status == RunStatus.MISSING
        assert run.reason == "Run never started"


class TestClassifyRunStatus:
    """Tests for _classify_run_status function."""

    def test_classify_missing_when_dir_not_exists(self, tmp_path: Path) -> None:
        """Test _classify_run_status returns MISSING when run_dir doesn't exist."""
        run_dir = tmp_path / "run_01"
        assert _classify_run_status(run_dir) == RunStatus.MISSING

    def test_classify_completed_with_all_files(self, tmp_path: Path) -> None:
        """Test _classify_run_status returns COMPLETED when all files exist."""
        run_dir = tmp_path / "run_01"
        agent_dir = run_dir / "agent"
        agent_dir.mkdir(parents=True)
        judge_dir = run_dir / "judge"
        judge_dir.mkdir(parents=True)

        # Create all required files
        (agent_dir / "output.txt").write_text("output")
        (agent_dir / "result.json").write_text("{}")
        (run_dir / "run_result.json").write_text("{}")

        assert _classify_run_status(run_dir) == RunStatus.COMPLETED

    def test_classify_results_when_agent_finished_missing_result(self, tmp_path: Path) -> None:
        """Test _classify_run_status returns RESULTS when agent finished but result missing."""
        run_dir = tmp_path / "run_01"
        agent_dir = run_dir / "agent"
        agent_dir.mkdir(parents=True)

        # Create files indicating agent finished
        (agent_dir / "output.txt").write_text("output")
        (agent_dir / "timing.json").write_text("{}")
        (agent_dir / "command_log.json").write_text("{}")
        # But missing run_result.json

        assert _classify_run_status(run_dir) == RunStatus.RESULTS

    def test_classify_failed_with_stderr_no_output(self, tmp_path: Path) -> None:
        """Test _classify_run_status returns FAILED when stderr exists but no output."""
        run_dir = tmp_path / "run_01"
        agent_dir = run_dir / "agent"
        agent_dir.mkdir(parents=True)

        (agent_dir / "stderr.log").write_text("error")
        # No output.txt or empty output.txt

        assert _classify_run_status(run_dir) == RunStatus.FAILED

    def test_classify_failed_with_stderr_empty_output(self, tmp_path: Path) -> None:
        """Test _classify_run_status returns FAILED when stderr exists and output is empty."""
        run_dir = tmp_path / "run_01"
        agent_dir = run_dir / "agent"
        agent_dir.mkdir(parents=True)

        (agent_dir / "stderr.log").write_text("error")
        (agent_dir / "output.txt").write_text("")  # Empty

        assert _classify_run_status(run_dir) == RunStatus.FAILED

    def test_classify_partial_when_agent_incomplete(self, tmp_path: Path) -> None:
        """Test _classify_run_status returns PARTIAL when agent started but incomplete."""
        run_dir = tmp_path / "run_01"
        agent_dir = run_dir / "agent"
        agent_dir.mkdir(parents=True)

        # Agent dir exists but missing key files
        (agent_dir / "output.txt").write_text("partial output")
        # Missing timing.json and command_log.json

        assert _classify_run_status(run_dir) == RunStatus.PARTIAL

    def test_classify_missing_when_empty_run_dir(self, tmp_path: Path) -> None:
        """Test _classify_run_status returns MISSING when run_dir exists but empty."""
        run_dir = tmp_path / "run_01"
        run_dir.mkdir()

        assert _classify_run_status(run_dir) == RunStatus.MISSING


class TestScanRunsNeedingRerun:
    """Tests for scan_runs_needing_rerun function."""

    def create_mock_config(
        self, tiers: list[TierID], runs_per_subtest: int = 3
    ) -> ExperimentConfig:
        """Create mock ExperimentConfig for testing."""
        config = MagicMock(spec=ExperimentConfig)
        config.tiers_to_run = tiers
        config.runs_per_subtest = runs_per_subtest
        config.max_subtests = None
        return config

    def create_mock_tier_manager(self, tier_configs: dict[TierID, TierConfig]) -> MagicMock:
        """Create mock TierManager for testing."""
        tier_manager = MagicMock()

        def load_tier_config(tier_id: TierID) -> TierConfig:
            return tier_configs.get(tier_id, TierConfig(tier_id=tier_id, subtests=[]))

        tier_manager.load_tier_config = load_tier_config
        return tier_manager

    def test_scan_empty_experiment(self, tmp_path: Path) -> None:
        """Test scan_runs_needing_rerun with empty experiment directory."""
        config = self.create_mock_config([TierID.T0])

        subtest = SubTestConfig(id="00", name="Test", description="Test subtest")
        tier_config = TierConfig(tier_id=TierID.T0, subtests=[subtest])
        tier_manager = self.create_mock_tier_manager({TierID.T0: tier_config})

        stats = RerunStats()
        _ = scan_runs_needing_rerun(
            experiment_dir=tmp_path,
            config=config,
            tier_manager=tier_manager,
            stats=stats,
        )

        assert stats.total_expected_runs == 3  # runs_per_subtest default
        assert stats.missing == 3

    def test_scan_with_tier_filter(self, tmp_path: Path) -> None:
        """Test scan_runs_needing_rerun with tier filter."""
        config = self.create_mock_config([TierID.T0, TierID.T1], runs_per_subtest=2)

        subtest = SubTestConfig(id="00", name="Test", description="Test subtest")
        tier_configs = {
            TierID.T0: TierConfig(tier_id=TierID.T0, subtests=[subtest]),
            TierID.T1: TierConfig(tier_id=TierID.T1, subtests=[subtest]),
        }
        tier_manager = self.create_mock_tier_manager(tier_configs)

        stats = RerunStats()
        _ = scan_runs_needing_rerun(
            experiment_dir=tmp_path,
            config=config,
            tier_manager=tier_manager,
            tier_filter=["T0"],  # Only T0
            stats=stats,
        )

        assert stats.total_expected_runs == 2  # Only T0, 2 runs
        assert stats.missing == 2

    def test_scan_with_subtest_filter(self, tmp_path: Path) -> None:
        """Test scan_runs_needing_rerun with subtest filter."""
        config = self.create_mock_config([TierID.T0], runs_per_subtest=1)

        subtests = [
            SubTestConfig(id="00", name="Test1", description="Test subtest 1"),
            SubTestConfig(id="01", name="Test2", description="Test subtest 2"),
        ]
        tier_config = TierConfig(tier_id=TierID.T0, subtests=subtests)
        tier_manager = self.create_mock_tier_manager({TierID.T0: tier_config})

        stats = RerunStats()
        _ = scan_runs_needing_rerun(
            experiment_dir=tmp_path,
            config=config,
            tier_manager=tier_manager,
            subtest_filter=["00"],  # Only subtest 00
            stats=stats,
        )

        assert stats.total_expected_runs == 1  # Only 00, 1 run
        assert stats.missing == 1

    def test_scan_with_run_filter(self, tmp_path: Path) -> None:
        """Test scan_runs_needing_rerun with run number filter."""
        config = self.create_mock_config([TierID.T0], runs_per_subtest=5)

        subtest = SubTestConfig(id="00", name="Test", description="Test subtest")
        tier_config = TierConfig(tier_id=TierID.T0, subtests=[subtest])
        tier_manager = self.create_mock_tier_manager({TierID.T0: tier_config})

        stats = RerunStats()
        _ = scan_runs_needing_rerun(
            experiment_dir=tmp_path,
            config=config,
            tier_manager=tier_manager,
            run_filter=[1, 3, 5],  # Only runs 1, 3, 5
            stats=stats,
        )

        assert stats.total_expected_runs == 3  # Only 3 runs
        assert stats.runs_skipped_by_filter == 2  # Runs 2, 4 skipped
        assert stats.missing == 3

    def test_scan_with_status_filter(self, tmp_path: Path) -> None:
        """Test scan_runs_needing_rerun with status filter."""
        config = self.create_mock_config([TierID.T0], runs_per_subtest=2)

        subtest = SubTestConfig(id="00", name="Test", description="Test subtest")
        tier_config = TierConfig(tier_id=TierID.T0, subtests=[subtest])
        tier_manager = self.create_mock_tier_manager({TierID.T0: tier_config})

        # Create one completed run and one missing
        tier_dir = tmp_path / "T0"
        subtest_dir = tier_dir / "00"
        run1_dir = subtest_dir / "run_01"
        agent_dir = run1_dir / "agent"
        agent_dir.mkdir(parents=True)
        judge_dir = run1_dir / "judge"
        judge_dir.mkdir(parents=True)
        (agent_dir / "output.txt").write_text("output")
        (agent_dir / "result.json").write_text("{}")
        (run1_dir / "run_result.json").write_text("{}")

        stats = RerunStats()
        runs_by_status = scan_runs_needing_rerun(
            experiment_dir=tmp_path,
            config=config,
            tier_manager=tier_manager,
            status_filter=[RunStatus.MISSING],  # Only missing runs
            stats=stats,
        )

        # Total stats should include all runs
        assert stats.total_expected_runs == 2
        assert stats.completed == 1
        assert stats.missing == 1
        # But only missing runs in result
        assert len(runs_by_status[RunStatus.MISSING]) == 1
        assert len(runs_by_status[RunStatus.COMPLETED]) == 0

    def test_scan_identifies_all_statuses(self, tmp_path: Path) -> None:
        """Test scan_runs_needing_rerun identifies all run statuses correctly."""
        config = self.create_mock_config([TierID.T0], runs_per_subtest=5)

        subtest = SubTestConfig(id="00", name="Test", description="Test subtest")
        tier_config = TierConfig(tier_id=TierID.T0, subtests=[subtest])
        tier_manager = self.create_mock_tier_manager({TierID.T0: tier_config})

        tier_dir = tmp_path / "T0"
        subtest_dir = tier_dir / "00"

        # Run 1: COMPLETED
        run1_dir = subtest_dir / "run_01"
        agent1_dir = run1_dir / "agent"
        agent1_dir.mkdir(parents=True)
        judge1_dir = run1_dir / "judge"
        judge1_dir.mkdir(parents=True)
        (agent1_dir / "output.txt").write_text("output")
        (agent1_dir / "result.json").write_text("{}")
        (run1_dir / "run_result.json").write_text("{}")

        # Run 2: RESULTS (agent finished but missing run_result.json)
        run2_dir = subtest_dir / "run_02"
        agent2_dir = run2_dir / "agent"
        agent2_dir.mkdir(parents=True)
        (agent2_dir / "output.txt").write_text("output")
        (agent2_dir / "timing.json").write_text("{}")
        (agent2_dir / "command_log.json").write_text("{}")

        # Run 3: FAILED (stderr but no output)
        run3_dir = subtest_dir / "run_03"
        agent3_dir = run3_dir / "agent"
        agent3_dir.mkdir(parents=True)
        (agent3_dir / "stderr.log").write_text("error")

        # Run 4: PARTIAL (output but missing timing)
        run4_dir = subtest_dir / "run_04"
        agent4_dir = run4_dir / "agent"
        agent4_dir.mkdir(parents=True)
        (agent4_dir / "output.txt").write_text("partial")

        # Run 5: MISSING (doesn't exist)

        stats = RerunStats()
        runs_by_status = scan_runs_needing_rerun(
            experiment_dir=tmp_path,
            config=config,
            tier_manager=tier_manager,
            stats=stats,
        )

        assert stats.total_expected_runs == 5
        assert stats.completed == 1
        assert stats.results == 1
        assert stats.failed == 1
        assert stats.partial == 1
        assert stats.missing == 1

        assert len(runs_by_status[RunStatus.COMPLETED]) == 1
        assert len(runs_by_status[RunStatus.RESULTS]) == 1
        assert len(runs_by_status[RunStatus.FAILED]) == 1
        assert len(runs_by_status[RunStatus.PARTIAL]) == 1
        assert len(runs_by_status[RunStatus.MISSING]) == 1

    def test_scan_respects_max_subtests(self, tmp_path: Path) -> None:
        """Test scan_runs_needing_rerun respects max_subtests config."""
        config = self.create_mock_config([TierID.T0], runs_per_subtest=1)
        config.max_subtests = 2

        subtests = [
            SubTestConfig(id="00", name="Test1", description="Test subtest 1"),
            SubTestConfig(id="01", name="Test2", description="Test subtest 2"),
            SubTestConfig(id="02", name="Test3", description="Test subtest 3"),
        ]
        tier_config = TierConfig(tier_id=TierID.T0, subtests=subtests)
        tier_manager = self.create_mock_tier_manager({TierID.T0: tier_config})

        stats = RerunStats()
        _ = scan_runs_needing_rerun(
            experiment_dir=tmp_path,
            config=config,
            tier_manager=tier_manager,
            stats=stats,
        )

        # Should only process first 2 subtests
        assert stats.total_expected_runs == 2
        assert stats.missing == 2

    def test_scan_assigns_correct_reasons(self, tmp_path: Path) -> None:
        """Test scan_runs_needing_rerun assigns correct human-readable reasons."""
        config = self.create_mock_config([TierID.T0], runs_per_subtest=1)

        subtest = SubTestConfig(id="00", name="Test", description="Test subtest")
        tier_config = TierConfig(tier_id=TierID.T0, subtests=[subtest])
        tier_manager = self.create_mock_tier_manager({TierID.T0: tier_config})

        runs_by_status = scan_runs_needing_rerun(
            experiment_dir=tmp_path,
            config=config,
            tier_manager=tier_manager,
        )

        missing_runs = runs_by_status[RunStatus.MISSING]
        assert len(missing_runs) == 1
        assert missing_runs[0].reason == "Run never started"


class TestRerunSingleRun:
    """Tests for rerun_single_run function."""

    def test_rerun_single_run_refuses_completed_status(self, tmp_path: Path) -> None:
        """Test rerun_single_run refuses to rerun COMPLETED runs."""
        from scylla.e2e.rerun import rerun_single_run

        run_dir = tmp_path / "run_01"
        run_dir.mkdir()

        run_info = RunToRerun(
            tier_id="T0",
            subtest_id="00",
            run_number=1,
            run_dir=run_dir,
            status=RunStatus.COMPLETED,
            reason="Already completed",
        )

        config = MagicMock(spec=ExperimentConfig)
        tier_manager = MagicMock()
        workspace_manager = MagicMock()

        result = rerun_single_run(
            run_info=run_info,
            experiment_dir=tmp_path,
            config=config,
            tier_manager=tier_manager,
            workspace_manager=workspace_manager,
            baseline=None,
        )

        assert result is None

    def test_rerun_single_run_refuses_results_status(self, tmp_path: Path) -> None:
        """Test rerun_single_run refuses to rerun RESULTS runs."""
        from scylla.e2e.rerun import rerun_single_run

        run_dir = tmp_path / "run_01"
        run_dir.mkdir()

        run_info = RunToRerun(
            tier_id="T0",
            subtest_id="00",
            run_number=1,
            run_dir=run_dir,
            status=RunStatus.RESULTS,
            reason="Missing results only",
        )

        config = MagicMock(spec=ExperimentConfig)
        tier_manager = MagicMock()
        workspace_manager = MagicMock()

        result = rerun_single_run(
            run_info=run_info,
            experiment_dir=tmp_path,
            config=config,
            tier_manager=tier_manager,
            workspace_manager=workspace_manager,
            baseline=None,
        )

        assert result is None

    def test_rerun_single_run_moves_existing_to_failed(self, tmp_path: Path) -> None:
        """Test rerun_single_run moves existing run to .failed directory."""
        from scylla.e2e.rerun import rerun_single_run

        run_dir = tmp_path / "T0" / "00" / "run_01"
        run_dir.mkdir(parents=True)
        (run_dir / "old_file.txt").write_text("old data")

        run_info = RunToRerun(
            tier_id="T0",
            subtest_id="00",
            run_number=1,
            run_dir=run_dir,
            status=RunStatus.FAILED,
            reason="Agent failed",
        )

        # Create minimal mocks
        config = MagicMock(spec=ExperimentConfig)
        config.task_prompt_file = tmp_path / "task.md"
        config.task_prompt_file.write_text("Task prompt")
        config.thinking_mode = None
        config.task_commit = "abc123"

        subtest = SubTestConfig(id="00", name="Test", description="Test subtest")
        tier_config = TierConfig(tier_id=TierID.T0, subtests=[subtest])

        tier_manager = MagicMock()
        tier_manager.load_tier_config.return_value = tier_config
        tier_manager.prepare_workspace = MagicMock()

        workspace_manager = MagicMock()

        # Mock SubTestExecutor and _setup_workspace to avoid actual execution
        with (
            patch("scylla.e2e.rerun.SubTestExecutor") as mock_executor_class,
            patch("scylla.e2e.workspace_setup._setup_workspace"),
        ):
            mock_executor = MagicMock()
            mock_executor_class.return_value = mock_executor
            mock_executor._execute_single_run.return_value = None

            rerun_single_run(
                run_info=run_info,
                experiment_dir=tmp_path,
                config=config,
                tier_manager=tier_manager,
                workspace_manager=workspace_manager,
                baseline=None,
            )

        # Verify old run was moved to .failed
        failed_dir = tmp_path / "T0" / "00" / ".failed" / "run_01"
        assert failed_dir.exists()
        assert (failed_dir / "old_file.txt").read_text() == "old data"

    def test_rerun_single_run_returns_none_on_missing_subtest(self, tmp_path: Path) -> None:
        """Test rerun_single_run returns None when subtest not found in tier."""
        from scylla.e2e.rerun import rerun_single_run

        run_dir = tmp_path / "run_01"

        run_info = RunToRerun(
            tier_id="T0",
            subtest_id="99",  # Non-existent
            run_number=1,
            run_dir=run_dir,
            status=RunStatus.MISSING,
            reason="Never started",
        )

        config = MagicMock(spec=ExperimentConfig)
        tier_config = TierConfig(tier_id=TierID.T0, subtests=[])  # Empty

        tier_manager = MagicMock()
        tier_manager.load_tier_config.return_value = tier_config

        workspace_manager = MagicMock()

        result = rerun_single_run(
            run_info=run_info,
            experiment_dir=tmp_path,
            config=config,
            tier_manager=tier_manager,
            workspace_manager=workspace_manager,
            baseline=None,
        )

        assert result is None
