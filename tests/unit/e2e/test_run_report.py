"""Unit tests for E2E run report generation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from scylla.e2e.models import (
    ExperimentConfig,
    ExperimentResult,
    JudgeResultSummary,
    RunResult,
    SubTestResult,
    TierID,
    TierResult,
    TokenStats,
)
from scylla.e2e.run_report import (
    _get_workspace_files,
    generate_experiment_summary_table,
    generate_run_report,
    generate_tier_summary_table,
    save_experiment_report,
    save_run_report,
    save_run_report_json,
    save_subtest_report,
    save_tier_report,
)


class TestGenerateRunReport:
    """Tests for generate_run_report function."""

    def test_basic_report_generation(self, tmp_path: Path) -> None:
        """Test basic run report generation with minimal parameters."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        report = generate_run_report(
            tier_id="T0",
            subtest_id="baseline",
            run_number=1,
            score=0.85,
            grade="A",
            passed=True,
            reasoning="Good work",
            cost_usd=0.0042,
            duration_seconds=12.5,
            tokens_input=1000,
            tokens_output=500,
            exit_code=0,
            task_prompt="Test task",
            workspace_path=workspace,
        )

        assert "# Run Report: T0/baseline/run_01" in report
        assert "✓ PASS" in report
        assert "0.850" in report
        assert "A" in report
        assert "$0.0042" in report
        assert "12.50s" in report
        assert "1,000 in / 500 out" in report

    def test_failed_run_report(self, tmp_path: Path) -> None:
        """Test report generation for failed run."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        report = generate_run_report(
            tier_id="T1",
            subtest_id="01",
            run_number=2,
            score=0.45,
            grade="D",
            passed=False,
            reasoning="Did not meet requirements",
            cost_usd=0.0015,
            duration_seconds=8.2,
            tokens_input=500,
            tokens_output=200,
            exit_code=1,
            task_prompt="Test task",
            workspace_path=workspace,
        )

        assert "# Run Report: T1/01/run_02" in report
        assert "✗ FAIL" in report
        assert "0.450" in report
        assert "D" in report
        assert "Exit Code | 1" in report

    def test_report_with_token_stats(self, tmp_path: Path) -> None:
        """Test report with detailed token statistics."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        token_stats = {
            "input_tokens": 1000,
            "output_tokens": 500,
            "cache_read_tokens": 2000,
            "cache_creation_tokens": 300,
        }

        report = generate_run_report(
            tier_id="T0",
            subtest_id="baseline",
            run_number=1,
            score=0.85,
            grade="A",
            passed=True,
            reasoning="Good work",
            cost_usd=0.0042,
            duration_seconds=12.5,
            tokens_input=1000,
            tokens_output=500,
            exit_code=0,
            task_prompt="Test task",
            workspace_path=workspace,
            token_stats=token_stats,
        )

        assert "Token Breakdown" in report
        assert "Input (fresh) | 1,000" in report
        assert "Output | 500" in report
        assert "Cache Read | 2,000" in report
        assert "Cache Created | 300" in report
        assert "3,000 in (2,000 cached) / 500 out" in report

    def test_report_with_duration_breakdown(self, tmp_path: Path) -> None:
        """Test report with agent and judge duration breakdown."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        report = generate_run_report(
            tier_id="T0",
            subtest_id="baseline",
            run_number=1,
            score=0.85,
            grade="A",
            passed=True,
            reasoning="Good work",
            cost_usd=0.0042,
            duration_seconds=15.5,
            tokens_input=1000,
            tokens_output=500,
            exit_code=0,
            task_prompt="Test task",
            workspace_path=workspace,
            agent_duration_seconds=12.0,
            judge_duration_seconds=3.5,
        )

        assert "Duration (Total) | 15.50s" in report
        assert "- Agent | 12.00s" in report
        assert "- Judge | 3.50s" in report

    def test_report_with_criteria_scores(self, tmp_path: Path) -> None:
        """Test report with detailed criteria scores."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        criteria_scores = {
            "correctness": {"score": 0.9, "explanation": "Implementation is correct"},
            "efficiency": {"score": 0.8, "explanation": "Could be more efficient"},
            "style": {"score": 0.85, "explanation": "Good code style"},
        }

        report = generate_run_report(
            tier_id="T0",
            subtest_id="baseline",
            run_number=1,
            score=0.85,
            grade="A",
            passed=True,
            reasoning="Good work",
            cost_usd=0.0042,
            duration_seconds=12.5,
            tokens_input=1000,
            tokens_output=500,
            exit_code=0,
            task_prompt="Test task",
            workspace_path=workspace,
            criteria_scores=criteria_scores,
        )

        assert "Criteria Scores" in report
        assert "correctness" in report
        assert "0.90" in report
        assert "Detailed Explanations" in report
        assert "Implementation is correct" in report

    def test_report_with_legacy_criteria_format(self, tmp_path: Path) -> None:
        """Test report with legacy criteria scores (just numbers)."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        criteria_scores = {
            "correctness": 0.9,
            "efficiency": 0.8,
        }

        report = generate_run_report(
            tier_id="T0",
            subtest_id="baseline",
            run_number=1,
            score=0.85,
            grade="A",
            passed=True,
            reasoning="Good work",
            cost_usd=0.0042,
            duration_seconds=12.5,
            tokens_input=1000,
            tokens_output=500,
            exit_code=0,
            task_prompt="Test task",
            workspace_path=workspace,
            criteria_scores=criteria_scores,
        )

        assert "correctness | 0.90 | -" in report
        assert "efficiency | 0.80 | -" in report

    def test_report_with_multiple_judges(self, tmp_path: Path) -> None:
        """Test report with multiple judge results."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        judges = [
            JudgeResultSummary(
                judge_number=1,
                model="claude-opus-4",
                score=0.85,
                grade="A",
                passed=True,
                reasoning="Good implementation",
            ),
            JudgeResultSummary(
                judge_number=2,
                model="claude-sonnet-4-5",
                score=0.80,
                grade="B",
                passed=True,
                reasoning="Acceptable work",
            ),
        ]

        report = generate_run_report(
            tier_id="T0",
            subtest_id="baseline",
            run_number=1,
            score=0.825,
            grade="B",
            passed=True,
            reasoning="Consensus: Good overall",
            cost_usd=0.0042,
            duration_seconds=12.5,
            tokens_input=1000,
            tokens_output=500,
            exit_code=0,
            task_prompt="Test task",
            workspace_path=workspace,
            judges=judges,
        )

        assert "Judge Evaluation (Consensus)" in report
        assert "Individual Judges" in report
        assert "Judge 1: claude-opus-4" in report
        assert "Judge 2: claude-sonnet-4-5" in report
        assert "0.850" in report
        assert "0.800" in report


class TestSaveRunReport:
    """Tests for save_run_report function."""

    def test_save_run_report_creates_directories(self, tmp_path: Path) -> None:
        """Test that save_run_report creates necessary directories."""
        output_path = tmp_path / "logs" / "tier" / "subtest" / "report.md"
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        save_run_report(
            output_path=output_path,
            tier_id="T0",
            subtest_id="baseline",
            run_number=1,
            score=0.85,
            grade="A",
            passed=True,
            reasoning="Good work",
            cost_usd=0.0042,
            duration_seconds=12.5,
            tokens_input=1000,
            tokens_output=500,
            exit_code=0,
            task_prompt="Test task",
            workspace_path=workspace,
        )

        assert output_path.exists()
        assert output_path.is_file()
        content = output_path.read_text()
        assert "# Run Report: T0/baseline/run_01" in content


class TestSaveRunReportJson:
    """Tests for save_run_report_json function."""

    def test_save_run_report_json(self, tmp_path: Path) -> None:
        """Test saving JSON run report."""
        run_dir = tmp_path / "run_01"
        run_dir.mkdir()

        save_run_report_json(
            run_dir=run_dir,
            run_number=1,
            score=0.85,
            grade="A",
            passed=True,
            cost_usd=0.0042,
            duration_seconds=12.5,
        )

        json_file = run_dir / "report.json"
        assert json_file.exists()

        data = json.loads(json_file.read_text())
        assert data["run_number"] == 1
        assert data["score"] == 0.85
        assert data["grade"] == "A"
        assert data["passed"] is True
        assert data["cost_usd"] == 0.0042
        assert data["duration_seconds"] == 12.5
        assert "generated_at" in data


class TestGetWorkspaceFiles:
    """Tests for _get_workspace_files helper function."""

    def test_no_workspace_returns_empty_list(self) -> None:
        """Test that missing workspace returns empty list."""
        result = _get_workspace_files(Path("/nonexistent"))
        assert result == []

    def test_git_error_returns_empty_list(self, tmp_path: Path) -> None:
        """Test that git errors return empty list."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        # Not a git repo, should handle gracefully
        result = _get_workspace_files(workspace)
        assert result == []

    @patch("subprocess.run")
    def test_committed_files_detected(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test detection of committed files."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        # Mock git diff to show committed files
        diff_result = MagicMock()
        diff_result.returncode = 0
        diff_result.stdout = "file1.py\nfile2.txt\n"

        # Mock git status to show no uncommitted changes
        status_result = MagicMock()
        status_result.returncode = 0
        status_result.stdout = ""

        mock_run.side_effect = [diff_result, status_result]

        result = _get_workspace_files(workspace)

        assert len(result) == 2
        assert ("file1.py", "committed") in result
        assert ("file2.txt", "committed") in result

    @patch("subprocess.run")
    def test_uncommitted_files_detected(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test detection of uncommitted files."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        # Mock git diff to show no committed files
        diff_result = MagicMock()
        diff_result.returncode = 0
        diff_result.stdout = ""

        # Mock git status to show uncommitted changes
        status_result = MagicMock()
        status_result.returncode = 0
        status_result.stdout = "?? new_file.py\n M modified.txt\n"

        mock_run.side_effect = [diff_result, status_result]

        result = _get_workspace_files(workspace)

        assert len(result) == 2
        assert ("new_file.py", "uncommitted") in result
        assert ("modified.txt", "uncommitted") in result

    @patch("subprocess.run")
    def test_test_config_files_excluded(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test that test config files are excluded."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        # Mock git diff to show committed files including CLAUDE.md (which should be filtered)
        diff_result = MagicMock()
        diff_result.returncode = 0
        diff_result.stdout = "file1.py\nCLAUDE.md\n.claude/agents/test.md\n"

        # Mock git status
        status_result = MagicMock()
        status_result.returncode = 0
        status_result.stdout = ""

        mock_run.side_effect = [diff_result, status_result]

        result = _get_workspace_files(workspace)

        # Only file1.py should be included (CLAUDE.md and .claude/ are filtered)
        assert len(result) == 1
        assert ("file1.py", "committed") in result


class TestSaveSubtestReport:
    """Tests for save_subtest_report function."""

    def test_save_subtest_report_json_and_markdown(self, tmp_path: Path) -> None:
        """Test saving both JSON and markdown subtest reports."""
        subtest_dir = tmp_path / "subtest"

        # Create mock subtest result
        result = SubTestResult(
            tier_id=TierID.T0,
            subtest_id="baseline",
            runs=[
                RunResult(
                    run_number=1,
                    exit_code=0,
                    judge_score=0.85,
                    judge_grade="A",
                    judge_passed=True,
                    judge_reasoning="Good work",
                    cost_usd=0.004,
                    duration_seconds=10.0,
                    agent_duration_seconds=8.0,
                    judge_duration_seconds=2.0,
                    workspace_path=tmp_path / "workspace1",
                    logs_path=tmp_path / "logs1",
                    token_stats=TokenStats(
                        input_tokens=1000,
                        output_tokens=500,
                        cache_read_tokens=100,
                        cache_creation_tokens=50,
                    ),
                ),
                RunResult(
                    run_number=2,
                    exit_code=0,
                    judge_score=0.90,
                    judge_grade="A",
                    judge_passed=True,
                    judge_reasoning="Excellent work",
                    cost_usd=0.005,
                    duration_seconds=12.0,
                    agent_duration_seconds=10.0,
                    judge_duration_seconds=2.0,
                    workspace_path=tmp_path / "workspace2",
                    logs_path=tmp_path / "logs2",
                    token_stats=TokenStats(
                        input_tokens=1200,
                        output_tokens=600,
                        cache_read_tokens=150,
                        cache_creation_tokens=75,
                    ),
                ),
            ],
        )

        save_subtest_report(subtest_dir, "baseline", result)

        # Check JSON report
        json_file = subtest_dir / "report.json"
        assert json_file.exists()
        json_data = json.loads(json_file.read_text())
        assert json_data["subtest_id"] == "baseline"
        assert json_data["tier_id"] == "T0"
        assert json_data["summary"]["total_runs"] == 2
        assert json_data["summary"]["passed"] == 2
        assert len(json_data["children"]) == 2

        # Check markdown report
        md_file = subtest_dir / "report.md"
        assert md_file.exists()
        md_content = md_file.read_text()
        assert "# Subtest Report: baseline" in md_content
        assert "Tier**: T0" in md_content
        assert "Total Runs | 2" in md_content
        assert "Passed | 2" in md_content

    def test_subtest_report_with_criteria_scores(self, tmp_path: Path) -> None:
        """Test subtest report includes per-criteria comparison table."""
        subtest_dir = tmp_path / "subtest"

        result = SubTestResult(
            tier_id=TierID.T0,
            subtest_id="baseline",
            runs=[
                RunResult(
                    run_number=1,
                    exit_code=0,
                    judge_score=0.85,
                    judge_grade="A",
                    judge_passed=True,
                    judge_reasoning="Good work",
                    cost_usd=0.004,
                    duration_seconds=10.0,
                    agent_duration_seconds=8.0,
                    judge_duration_seconds=2.0,
                    workspace_path=tmp_path / "workspace1",
                    logs_path=tmp_path / "logs1",
                    criteria_scores={
                        "correctness": {"score": 0.9, "explanation": "Good"},
                        "style": {"score": 0.8, "explanation": "OK"},
                    },
                    token_stats=TokenStats(
                        input_tokens=1000,
                        output_tokens=500,
                    ),
                ),
                RunResult(
                    run_number=2,
                    exit_code=0,
                    judge_score=0.90,
                    judge_grade="A",
                    judge_passed=True,
                    judge_reasoning="Excellent work",
                    cost_usd=0.005,
                    duration_seconds=12.0,
                    agent_duration_seconds=10.0,
                    judge_duration_seconds=2.0,
                    workspace_path=tmp_path / "workspace2",
                    logs_path=tmp_path / "logs2",
                    criteria_scores={
                        "correctness": {"score": 0.95, "explanation": "Excellent"},
                        "style": {"score": 0.85, "explanation": "Good"},
                    },
                    token_stats=TokenStats(
                        input_tokens=1200,
                        output_tokens=600,
                    ),
                ),
            ],
        )

        save_subtest_report(subtest_dir, "baseline", result)

        md_file = subtest_dir / "report.md"
        md_content = md_file.read_text()
        assert "Per-Criteria Scores (All Runs)" in md_content
        assert "correctness" in md_content
        assert "style" in md_content


class TestGenerateTierSummaryTable:
    """Tests for generate_tier_summary_table function."""

    def test_generate_tier_summary_table(self, tmp_path: Path) -> None:
        """Test generating tier summary table."""
        subtest_results = {
            "baseline": SubTestResult(
                tier_id=TierID.T0,
                subtest_id="baseline",
                runs=[
                    RunResult(
                        run_number=1,
                        exit_code=0,
                        judge_score=0.85,
                        judge_grade="A",
                        judge_passed=True,
                        judge_reasoning="Good work",
                        cost_usd=0.004,
                        duration_seconds=10.0,
                        agent_duration_seconds=8.0,
                        judge_duration_seconds=2.0,
                        workspace_path=tmp_path / "workspace1",
                        logs_path=tmp_path / "logs1",
                        token_stats=TokenStats(
                            input_tokens=1000,
                            output_tokens=500,
                        ),
                    ),
                ],
            ),
            "01": SubTestResult(
                tier_id=TierID.T0,
                subtest_id="01",
                runs=[
                    RunResult(
                        run_number=1,
                        exit_code=0,
                        judge_score=0.90,
                        judge_grade="A",
                        judge_passed=True,
                        judge_reasoning="Excellent work",
                        cost_usd=0.005,
                        duration_seconds=12.0,
                        agent_duration_seconds=10.0,
                        judge_duration_seconds=2.0,
                        workspace_path=tmp_path / "workspace2",
                        logs_path=tmp_path / "logs2",
                        token_stats=TokenStats(
                            input_tokens=1200,
                            output_tokens=600,
                        ),
                    ),
                ],
            ),
        }

        table = generate_tier_summary_table("T0", subtest_results)

        assert "# T0 Subtest Summary" in table
        assert "baseline" in table
        assert "01" in table
        assert "0.85" in table
        assert "0.90" in table
        assert "[View](./baseline/report.md)" in table
        assert "[View](./01/report.md)" in table


class TestSaveTierReport:
    """Tests for save_tier_report function."""

    def test_save_tier_report(self, tmp_path: Path) -> None:
        """Test saving tier report."""
        tier_dir = tmp_path / "T0"
        tier_dir.mkdir(parents=True, exist_ok=True)

        tier_result = TierResult(
            tier_id=TierID.T0,
            subtest_results={
                "baseline": SubTestResult(
                    tier_id=TierID.T0,
                    subtest_id="baseline",
                    runs=[
                        RunResult(
                            run_number=1,
                            exit_code=0,
                            judge_score=0.85,
                            judge_grade="A",
                            judge_passed=True,
                            judge_reasoning="Good work",
                            cost_usd=0.004,
                            duration_seconds=10.0,
                            agent_duration_seconds=8.0,
                            judge_duration_seconds=2.0,
                            workspace_path=tmp_path / "workspace",
                            logs_path=tmp_path / "logs",
                            token_stats=TokenStats(
                                input_tokens=1000,
                                output_tokens=500,
                            ),
                        ),
                    ],
                    selected_as_best=True,
                ),
            },
        )

        save_tier_report(tier_dir, "T0", tier_result)

        # Check JSON
        json_file = tier_dir / "report.json"
        assert json_file.exists()
        json_data = json.loads(json_file.read_text())
        assert json_data["tier"] == "T0"
        assert json_data["summary"]["total_subtests"] == 1
        # best_subtest is None when not explicitly set (TierResult defaults)
        assert json_data["best"]["subtest"] is None

        # Check markdown
        md_file = tier_dir / "report.md"
        assert md_file.exists()
        md_content = md_file.read_text()
        assert "# Tier Report: T0" in md_content
        assert "Total Subtests | 1" in md_content


class TestGenerateExperimentSummaryTable:
    """Tests for generate_experiment_summary_table function."""

    def test_generate_experiment_summary_table(self, tmp_path: Path) -> None:
        """Test generating experiment summary table."""
        tier_results = {
            TierID.T0: TierResult(
                tier_id=TierID.T0,
                subtest_results={
                    "baseline": SubTestResult(
                        tier_id=TierID.T0,
                        subtest_id="baseline",
                        runs=[
                            RunResult(
                                run_number=1,
                                exit_code=0,
                                judge_score=0.85,
                                judge_grade="A",
                                judge_passed=True,
                                judge_reasoning="Good work",
                                cost_usd=0.004,
                                duration_seconds=10.0,
                                agent_duration_seconds=8.0,
                                judge_duration_seconds=2.0,
                                workspace_path=tmp_path / "workspace1",
                                logs_path=tmp_path / "logs1",
                                token_stats=TokenStats(
                                    input_tokens=1000,
                                    output_tokens=500,
                                ),
                            ),
                        ],
                    ),
                },
            ),
            TierID.T1: TierResult(
                tier_id=TierID.T1,
                subtest_results={
                    "01": SubTestResult(
                        tier_id=TierID.T1,
                        subtest_id="01",
                        runs=[
                            RunResult(
                                run_number=1,
                                exit_code=0,
                                judge_score=0.90,
                                judge_grade="A",
                                judge_passed=True,
                                judge_reasoning="Excellent work",
                                cost_usd=0.005,
                                duration_seconds=12.0,
                                agent_duration_seconds=10.0,
                                judge_duration_seconds=2.0,
                                workspace_path=tmp_path / "workspace2",
                                logs_path=tmp_path / "logs2",
                                token_stats=TokenStats(
                                    input_tokens=1200,
                                    output_tokens=600,
                                ),
                            ),
                        ],
                    ),
                },
            ),
        }

        table = generate_experiment_summary_table(tier_results)

        assert "# Experiment Summary: All Subtests" in table
        assert "T0" in table
        assert "T1" in table
        assert "baseline" in table
        assert "01" in table
        assert "[View](./tiers/T0/baseline/report.md)" in table
        assert "[View](./tiers/T1/01/report.md)" in table


class TestSaveExperimentReport:
    """Tests for save_experiment_report function."""

    def test_save_experiment_report(self, tmp_path: Path) -> None:
        """Test saving experiment report."""
        experiment_dir = tmp_path / "experiment"
        experiment_dir.mkdir()

        config = ExperimentConfig(
            experiment_id="test-exp",
            task_repo="https://github.com/test/repo",
            task_commit="abc123",
            task_prompt_file=tmp_path / "prompt.md",
            language="python",
            runs_per_subtest=1,
            judge_models=["claude-opus-4"],
            tiers_to_run=[TierID.T0],
        )

        result = ExperimentResult(
            config=config,
            tier_results={
                TierID.T0: TierResult(
                    tier_id=TierID.T0,
                    subtest_results={
                        "baseline": SubTestResult(
                            tier_id=TierID.T0,
                            subtest_id="baseline",
                            runs=[
                                RunResult(
                                    run_number=1,
                                    exit_code=0,
                                    judge_score=0.85,
                                    judge_grade="A",
                                    judge_passed=True,
                                    judge_reasoning="Good work",
                                    cost_usd=0.004,
                                    duration_seconds=10.0,
                                    agent_duration_seconds=8.0,
                                    judge_duration_seconds=2.0,
                                    workspace_path=tmp_path / "workspace",
                                    logs_path=tmp_path / "logs",
                                    token_stats=TokenStats(
                                        input_tokens=1000,
                                        output_tokens=500,
                                    ),
                                ),
                            ],
                        ),
                    },
                ),
            },
            started_at=datetime.now(timezone.utc).isoformat(),
            completed_at=datetime.now(timezone.utc).isoformat(),
        )

        save_experiment_report(experiment_dir, result)

        # Check JSON
        json_file = experiment_dir / "report.json"
        assert json_file.exists()
        json_data = json.loads(json_file.read_text())
        assert json_data["experiment_id"] == "test-exp"
        assert json_data["summary"]["total_tiers"] == 1

        # Check markdown
        md_file = experiment_dir / "report.md"
        assert md_file.exists()
        md_content = md_file.read_text()
        assert "# E2E Experiment Report: test-exp" in md_content
        # Best tier is N/A when not computed (ExperimentResult defaults)
        assert "Best Tier**: N/A" in md_content or "Best Tier**: T0" in md_content
