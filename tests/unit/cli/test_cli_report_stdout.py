"""Tests for --output - (stdout) support in the report command."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from scylla.cli.main import cli


def _create_mock_result(tier_id: str = "T0") -> dict[str, object]:
    """Create a mock result.json dict."""
    return {
        "tier_id": tier_id,
        "grading": {
            "pass_rate": 0.8,
            "composite_score": 0.75,
            "cost_of_pass": 1.50,
        },
        "judgment": {
            "impl_rate": 0.7,
            "passed": True,
            "letter_grade": "B",
        },
        "metrics": {
            "cost_usd": 0.05,
        },
    }


def _setup_mock_results(tier_id: str = "T0") -> None:
    """Create mock result files in an isolated filesystem."""
    result_dir = Path(f"runs/test-001/{tier_id}/run-1")
    result_dir.mkdir(parents=True)
    (result_dir / "result.json").write_text(json.dumps(_create_mock_result(tier_id)))


class TestOutputStdout:
    """Tests for --output - stdout mode."""

    def test_json_output_to_stdout(self) -> None:
        """--format json --output - prints valid JSON to stdout."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            _setup_mock_results()
            result = runner.invoke(cli, ["report", "test-001", "--format", "json", "--output", "-"])
            assert result.exit_code == 0
            parsed = json.loads(result.stdout)
            assert parsed["test_id"] == "test-001"

    def test_markdown_output_to_stdout(self) -> None:
        """--format markdown --output - prints markdown to stdout."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            _setup_mock_results()
            result = runner.invoke(
                cli, ["report", "test-001", "--format", "markdown", "--output", "-"]
            )
            assert result.exit_code == 0
            assert "# Evaluation Report" in result.stdout

    def test_stdout_mode_no_file_written(self) -> None:
        """--output - does not create a report file on disk."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            _setup_mock_results()
            result = runner.invoke(cli, ["report", "test-001", "--format", "json", "--output", "-"])
            assert result.exit_code == 0
            assert not Path("reports").exists()

    def test_stdout_status_messages_on_stderr(self) -> None:
        """Status messages go to stderr, not stdout, in stdout mode."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            _setup_mock_results()
            result = runner.invoke(cli, ["report", "test-001", "--format", "json", "--output", "-"])
            assert result.exit_code == 0
            # stdout should be pure JSON — no status messages
            json.loads(result.stdout)  # would raise if non-JSON content mixed in
            # stderr should contain status messages
            assert "Generating json report" in result.stderr
            assert "Found 1 run results" in result.stderr

    def test_stdout_json_sanitizes_special_floats(self) -> None:
        """inf/nan values are sanitized to null in stdout JSON output."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result_dir = Path("runs/test-001/T0/run-1")
            result_dir.mkdir(parents=True)
            mock = _create_mock_result()
            assert isinstance(mock["grading"], dict)
            mock["grading"]["cost_of_pass"] = float("inf")
            (result_dir / "result.json").write_text(json.dumps(mock))

            result = runner.invoke(cli, ["report", "test-001", "--format", "json", "--output", "-"])
            assert result.exit_code == 0
            parsed = json.loads(result.stdout)
            # inf should be sanitized to None
            for tier in parsed["tiers"]:
                if tier["cost_of_pass_median"] is not None:
                    assert tier["cost_of_pass_median"] != float("inf")


class TestOutputFileRegression:
    """Regression tests: existing --output <path> and default behavior still work."""

    def test_no_output_flag_writes_default(self) -> None:
        """No --output flag writes to reports/<test_id>/report.md."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            _setup_mock_results()
            result = runner.invoke(cli, ["report", "test-001"])
            assert result.exit_code == 0
            assert Path("reports/test-001/report.md").exists()

    def test_output_file_path_writes_file(self) -> None:
        """--output <path.json> writes to the exact specified file path."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            _setup_mock_results()
            result = runner.invoke(
                cli, ["report", "test-001", "--format", "json", "--output", "custom/report.json"]
            )
            assert result.exit_code == 0
            assert Path("custom/report.json").exists()

    @pytest.mark.parametrize("fmt", ["json", "markdown"])
    def test_default_format_dispatch(self, fmt: str) -> None:
        """Both formats work without --output flag."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            _setup_mock_results()
            result = runner.invoke(cli, ["report", "test-001", "--format", fmt])
            assert result.exit_code == 0
            assert "Report generated:" in result.output
