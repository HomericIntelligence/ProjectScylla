"""Integration tests for the scylla CLI entry point and subcommand dispatch.

Tests the CLI wiring end-to-end via Click's CliRunner — verifying
subcommand dispatch, exit codes, and output rather than internal logic
(which existing unit tests already cover).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from scylla.cli.main import cli

pytestmark = pytest.mark.integration

# All subcommands registered on the top-level Click group.
_SUBCOMMANDS = ("run", "report", "list", "list-tiers", "list-models", "status", "audit")


def _make_result(tier_id: str = "T0", passed: bool = True) -> dict[str, Any]:
    """Create a minimal result.json dict for filesystem-based tests."""
    return {
        "tier_id": tier_id,
        "grading": {"pass_rate": 0.8, "composite_score": 0.75, "cost_of_pass": 1.50},
        "judgment": {"impl_rate": 0.7, "passed": passed, "letter_grade": "B"},
        "metrics": {"cost_usd": 0.05},
    }


# ---------------------------------------------------------------------------
# TestEntryPoint — top-level CLI group behaviour
# ---------------------------------------------------------------------------


class TestEntryPoint:
    """Validates CLI entry point and top-level dispatch."""

    def test_help_returns_zero_with_all_subcommands(self) -> None:
        """--help exits 0 and lists all registered subcommands."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        for subcmd in _SUBCOMMANDS:
            assert subcmd in result.output, f"subcommand {subcmd!r} missing from --help"

    def test_version_returns_version_string(self) -> None:
        """--version exits 0 and prints a version string."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_unknown_subcommand_exits_nonzero(self) -> None:
        """Invoking a non-existent subcommand exits != 0."""
        runner = CliRunner()
        result = runner.invoke(cli, ["nonexistent-subcommand"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# TestSubcommandDispatch — each subcommand is reachable
# ---------------------------------------------------------------------------


class TestSubcommandDispatch:
    """Validates that every subcommand is reachable through the CLI group."""

    @pytest.mark.parametrize("subcmd", list(_SUBCOMMANDS))
    def test_each_subcommand_help(self, subcmd: str) -> None:
        """Each subcommand's --help exits 0."""
        runner = CliRunner()
        result = runner.invoke(cli, [subcmd, "--help"])
        assert result.exit_code == 0, f"{subcmd} --help exited {result.exit_code}: {result.output}"

    def test_audit_models_help(self) -> None:
        """The nested 'audit models' subcommand is reachable via --help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["audit", "models", "--help"])
        assert result.exit_code == 0
        assert "model" in result.output.lower()

    def test_list_tiers_outputs_all_seven_tiers(self) -> None:
        """list-tiers outputs T0–T6 with their names."""
        runner = CliRunner()
        result = runner.invoke(cli, ["list-tiers"])
        assert result.exit_code == 0
        for tier_id in ("T0", "T1", "T2", "T3", "T4", "T5", "T6"):
            assert tier_id in result.output, f"{tier_id} missing from list-tiers output"

    @patch("scylla.cli.main.ConfigLoader")
    def test_list_models_outputs_configured_models(self, mock_loader_cls: MagicMock) -> None:
        """list-models shows 'Configured models:' with at least one model."""
        mock_model = MagicMock()
        mock_model.model_id = "claude-sonnet-4-6"
        mock_model.name = "Claude Sonnet"
        mock_model.provider = "anthropic"
        mock_model.cost_per_1k_input = 0.003
        mock_model.cost_per_1k_output = 0.015

        mock_loader_cls.return_value.load_all_models.return_value = {
            "claude-sonnet-4-6": mock_model,
        }

        runner = CliRunner()
        result = runner.invoke(cli, ["list-models"])
        assert result.exit_code == 0
        assert "Configured models:" in result.output
        assert "claude-sonnet-4-6" in result.output

    def test_list_shows_available_tests(self) -> None:
        """List shows 'Available tests:' heading."""
        runner = CliRunner()
        result = runner.invoke(cli, ["list"])
        assert result.exit_code == 0
        assert "Available tests:" in result.output


# ---------------------------------------------------------------------------
# TestRunCommandIntegration — run subcommand wiring
# ---------------------------------------------------------------------------


class TestRunCommandIntegration:
    """Tests that the run command dispatches to EvalOrchestrator correctly."""

    @patch("scylla.cli.main.EvalOrchestrator")
    @patch("scylla.cli.main.ConfigLoader")
    def test_run_single_dispatches_to_orchestrator(
        self,
        mock_loader_cls: MagicMock,
        mock_orch_cls: MagicMock,
    ) -> None:
        """Run with --runs 1 --tier T0 calls run_single on the orchestrator."""
        mock_loader_cls.return_value.load_defaults.return_value.default_model = "claude-sonnet-4-6"
        mock_result = MagicMock()
        mock_result.judgment.passed = True
        mock_result.judgment.letter_grade = "A"
        mock_result.metrics.cost_usd = 0.01
        mock_orch_cls.return_value.run_single.return_value = mock_result

        runner = CliRunner()
        result = runner.invoke(cli, ["run", "001-test", "--tier", "T0", "--runs", "1"])
        assert result.exit_code == 0, f"run exited {result.exit_code}: {result.output}"
        mock_orch_cls.return_value.run_single.assert_called_once()

    @patch("scylla.cli.main.EvalOrchestrator")
    @patch("scylla.cli.main.ConfigLoader")
    def test_run_multi_tier_dispatches_run_test(
        self,
        mock_loader_cls: MagicMock,
        mock_orch_cls: MagicMock,
    ) -> None:
        """Run with multiple tiers calls run_test (not run_single)."""
        mock_loader_cls.return_value.load_defaults.return_value.default_model = "claude-sonnet-4-6"
        mock_result = MagicMock()
        mock_result.judgment.passed = True
        mock_orch_cls.return_value.run_test.return_value = [mock_result]

        runner = CliRunner()
        result = runner.invoke(
            cli, ["run", "001-test", "--tier", "T0", "--tier", "T1", "--runs", "5"]
        )
        assert result.exit_code == 0, f"run exited {result.exit_code}: {result.output}"
        mock_orch_cls.return_value.run_test.assert_called_once()

    def test_run_verbose_quiet_mutual_exclusion(self) -> None:
        """--verbose and --quiet together exits non-zero."""
        runner = CliRunner()
        result = runner.invoke(cli, ["run", "001-test", "--verbose", "--quiet", "--tier", "T0"])
        assert result.exit_code != 0
        assert "Cannot use --verbose and --quiet together" in result.output


# ---------------------------------------------------------------------------
# TestReportCommandIntegration — report wiring with real filesystem
# ---------------------------------------------------------------------------


class TestReportCommandIntegration:
    """Tests report command with real disk I/O via isolated_filesystem."""

    def test_report_with_results_generates_markdown(self) -> None:
        """Report generates a markdown file when result.json files exist."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            runs_dir = Path("runs/test-001/T0/run-1")
            runs_dir.mkdir(parents=True)
            (runs_dir / "result.json").write_text(json.dumps(_make_result()))

            result = runner.invoke(cli, ["report", "test-001"])
            assert result.exit_code == 0, f"report exited {result.exit_code}: {result.output}"
            assert "Report generated" in result.output

    def test_report_no_results_exits_nonzero(self) -> None:
        """Report exits non-zero when no results are on disk."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(cli, ["report", "nonexistent-test"])
            assert result.exit_code != 0
            assert "No results found" in result.output

    def test_report_json_format_produces_valid_json(self) -> None:
        """Report --format json produces a parseable JSON file."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            runs_dir = Path("runs/test-001/T0/run-1")
            runs_dir.mkdir(parents=True)
            (runs_dir / "result.json").write_text(json.dumps(_make_result()))

            result = runner.invoke(cli, ["report", "test-001", "--format", "json"])
            assert result.exit_code == 0

            report_path = Path("reports/test-001/report.json")
            assert report_path.exists()
            content = json.loads(report_path.read_text())
            assert content["test_id"] == "test-001"

    def test_report_multiple_tiers(self) -> None:
        """Report handles results across multiple tiers."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            for tier in ("T0", "T1"):
                runs_dir = Path(f"runs/test-001/{tier}/run-1")
                runs_dir.mkdir(parents=True)
                (runs_dir / "result.json").write_text(json.dumps(_make_result(tier_id=tier)))

            result = runner.invoke(cli, ["report", "test-001"])
            assert result.exit_code == 0
            assert "T0:" in result.output
            assert "T1:" in result.output


# ---------------------------------------------------------------------------
# TestStatusCommandIntegration — status with real disk
# ---------------------------------------------------------------------------


class TestStatusCommandIntegration:
    """Tests status command with real disk I/O."""

    def test_status_with_results_shows_tier_summary(self) -> None:
        """Status shows tier summary when result.json files exist."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # The status command reads from runs/<test_id>/**/result.json
            runs_dir = Path("runs/test-001/T0/run-1")
            runs_dir.mkdir(parents=True)
            (runs_dir / "result.json").write_text(json.dumps(_make_result()))

            result = runner.invoke(cli, ["status", "test-001"])
            assert result.exit_code == 0
            assert "Total runs:" in result.output
            assert "T0:" in result.output
            assert "Pass Rate:" in result.output

    def test_status_no_results_shows_empty(self) -> None:
        """Status shows 'No results found.' when no results are on disk."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(cli, ["status", "test-001"])
            assert result.exit_code == 0
            assert "No results found" in result.output


# ---------------------------------------------------------------------------
# TestAuditModelsIntegration — audit models through the full entry point
# ---------------------------------------------------------------------------


class TestAuditModelsIntegration:
    """Tests audit models subcommand end-to-end."""

    def test_audit_models_clean(self, tmp_path: Path) -> None:
        """Audit models exits 0 when filenames match model_ids."""
        models_dir = tmp_path / "config" / "models"
        models_dir.mkdir(parents=True)

        # Create a valid config where filename stem == model_id
        (models_dir / "test-model.yaml").write_text(
            "model_id: test-model\nname: Test Model\nprovider: test\n"
            "cost_per_1k_input: 0.001\ncost_per_1k_output: 0.002\n"
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["audit", "models", "--config-dir", str(tmp_path)])
        assert result.exit_code == 0, f"audit models exited {result.exit_code}: {result.output}"
        assert "OK" in result.output

    def test_audit_models_missing_dir_exits_nonzero(self, tmp_path: Path) -> None:
        """Audit models exits non-zero when config/models/ does not exist."""
        runner = CliRunner()
        result = runner.invoke(cli, ["audit", "models", "--config-dir", str(tmp_path)])
        assert result.exit_code != 0
