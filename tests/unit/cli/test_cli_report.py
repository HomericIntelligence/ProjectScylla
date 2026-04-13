"""Tests for CLI report command format dispatch."""

import json
from pathlib import Path

from click.testing import CliRunner

from scylla.cli.main import FORMAT_GENERATORS, _warn_format_extension_mismatch, cli
from scylla.reporting.json_report import JsonReportGenerator
from scylla.reporting.markdown import MarkdownReportGenerator


class TestFormatGenerators:
    """Tests for the FORMAT_GENERATORS dispatch dict."""

    def test_contains_markdown(self) -> None:
        """Markdown format is registered."""
        assert "markdown" in FORMAT_GENERATORS

    def test_contains_json(self) -> None:
        """JSON format is registered."""
        assert "json" in FORMAT_GENERATORS

    def test_markdown_maps_to_correct_class(self) -> None:
        """Markdown key maps to MarkdownReportGenerator."""
        assert FORMAT_GENERATORS["markdown"] is MarkdownReportGenerator

    def test_json_maps_to_correct_class(self) -> None:
        """JSON key maps to JsonReportGenerator."""
        assert FORMAT_GENERATORS["json"] is JsonReportGenerator

    def test_all_generators_have_write_report(self) -> None:
        """All registered generators have a write_report method."""
        for fmt, cls in FORMAT_GENERATORS.items():
            assert hasattr(cls, "write_report"), f"{fmt} generator missing write_report"


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


class TestReportCommand:
    """Tests for the report CLI command."""

    def test_report_no_results_exits_error(self) -> None:
        """Report command exits with error when no results found."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(cli, ["report", "nonexistent-test"])
            assert result.exit_code != 0
            assert "No results found" in result.output

    def test_report_markdown_format(self) -> None:
        """Report command generates markdown report via dict dispatch."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Create mock result files
            result_dir = Path("runs/test-001/T0/run-1")
            result_dir.mkdir(parents=True)
            (result_dir / "result.json").write_text(json.dumps(_create_mock_result()))

            result = runner.invoke(cli, ["report", "test-001", "--format", "markdown"])
            assert result.exit_code == 0
            assert "Report generated:" in result.output
            assert Path("reports/test-001/report.md").exists()

    def test_report_json_format(self) -> None:
        """Report command generates JSON report via dict dispatch."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Create mock result files
            result_dir = Path("runs/test-001/T0/run-1")
            result_dir.mkdir(parents=True)
            (result_dir / "result.json").write_text(json.dumps(_create_mock_result()))

            result = runner.invoke(cli, ["report", "test-001", "--format", "json"])
            assert result.exit_code == 0
            assert "Report generated:" in result.output
            assert Path("reports/test-001/report.json").exists()

            # Verify it's valid JSON
            content = json.loads(Path("reports/test-001/report.json").read_text())
            assert content["test_id"] == "test-001"

    def test_report_default_format_is_markdown(self) -> None:
        """Default format is markdown when --format is not specified."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result_dir = Path("runs/test-001/T0/run-1")
            result_dir.mkdir(parents=True)
            (result_dir / "result.json").write_text(json.dumps(_create_mock_result()))

            result = runner.invoke(cli, ["report", "test-001"])
            assert result.exit_code == 0
            assert Path("reports/test-001/report.md").exists()

    def test_report_invalid_format_rejected(self) -> None:
        """Invalid format is rejected by Click's Choice validator."""
        runner = CliRunner()
        result = runner.invoke(cli, ["report", "test-001", "--format", "html"])
        assert result.exit_code != 0

    def test_report_multiple_tiers(self) -> None:
        """Report handles results across multiple tiers."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            for tier in ["T0", "T1"]:
                result_dir = Path(f"runs/test-001/{tier}/run-1")
                result_dir.mkdir(parents=True)
                (result_dir / "result.json").write_text(
                    json.dumps(_create_mock_result(tier_id=tier))
                )

            result = runner.invoke(cli, ["report", "test-001"])
            assert result.exit_code == 0
            assert "T0:" in result.output
            assert "T1:" in result.output

    def test_report_output_file_path_markdown(self) -> None:
        """--output with .md extension writes to that exact file path."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result_dir = Path("runs/test-001/T0/run-1")
            result_dir.mkdir(parents=True)
            (result_dir / "result.json").write_text(json.dumps(_create_mock_result()))

            target = Path("my-report.md")
            result = runner.invoke(cli, ["report", "test-001", "--output", str(target)])
            assert result.exit_code == 0
            assert target.exists()
            assert "# Evaluation Report:" in target.read_text()

    def test_report_output_file_path_json(self) -> None:
        """--output with .json extension writes to that exact file path."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result_dir = Path("runs/test-001/T0/run-1")
            result_dir.mkdir(parents=True)
            (result_dir / "result.json").write_text(json.dumps(_create_mock_result()))

            target = Path("my-report.json")
            result = runner.invoke(
                cli, ["report", "test-001", "--format", "json", "--output", str(target)]
            )
            assert result.exit_code == 0
            assert target.exists()
            content = json.loads(target.read_text())
            assert content["test_id"] == "test-001"

    def test_report_output_directory_uses_default_filename(self) -> None:
        """--output without extension is treated as directory, uses default filename."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result_dir = Path("runs/test-001/T0/run-1")
            result_dir.mkdir(parents=True)
            (result_dir / "result.json").write_text(json.dumps(_create_mock_result()))

            result = runner.invoke(cli, ["report", "test-001", "--output", "custom-dir"])
            assert result.exit_code == 0
            assert Path("custom-dir/test-001/report.md").exists()

    def test_report_output_nested_file_path(self) -> None:
        """--output with nested path and extension creates parent dirs."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result_dir = Path("runs/test-001/T0/run-1")
            result_dir.mkdir(parents=True)
            (result_dir / "result.json").write_text(json.dumps(_create_mock_result()))

            target = Path("deep/nested/report.md")
            result = runner.invoke(cli, ["report", "test-001", "--output", str(target)])
            assert result.exit_code == 0
            assert target.exists()

    def test_report_output_format_json_to_directory(self) -> None:
        """--output <dir> --format json writes JSON file to that directory."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result_dir = Path("runs/test-001/T0/run-1")
            result_dir.mkdir(parents=True)
            (result_dir / "result.json").write_text(json.dumps(_create_mock_result()))

            result = runner.invoke(
                cli, ["report", "test-001", "--output", "out-dir", "--format", "json"]
            )
            assert result.exit_code == 0
            assert Path("out-dir/test-001/report.json").exists()
            content = json.loads(Path("out-dir/test-001/report.json").read_text())
            assert content["test_id"] == "test-001"

    def test_report_output_nonexistent_dir_creates_parents(self, tmp_path: Path) -> None:
        """--output to a non-existent directory creates all parent directories."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result_dir = Path("runs/test-001/T0/run-1")
            result_dir.mkdir(parents=True)
            (result_dir / "result.json").write_text(json.dumps(_create_mock_result()))

            deep_dir = "a/b/c/d"
            result = runner.invoke(cli, ["report", "test-001", "--output", deep_dir])
            assert result.exit_code == 0
            assert Path(f"{deep_dir}/test-001/report.md").exists()


class TestWarnFormatExtensionMismatch:
    """Tests for _warn_format_extension_mismatch helper."""

    def test_no_warning_when_output_is_none(self) -> None:
        """No warning emitted when --output is not provided."""
        import click

        @click.command()
        def _probe() -> None:
            _warn_format_extension_mismatch(None, "markdown")

        result = CliRunner().invoke(_probe, [], catch_exceptions=False)
        assert "Warning:" not in result.output

    def test_no_warning_when_output_is_dash(self) -> None:
        """No warning emitted when --output is '-' (stdout mode)."""
        import click

        @click.command()
        def _probe() -> None:
            _warn_format_extension_mismatch("-", "json")

        result = CliRunner().invoke(_probe, [], catch_exceptions=False)
        assert "Warning:" not in result.output

    def test_no_warning_when_extensions_match_markdown(self) -> None:
        """No warning when .md extension matches markdown format."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result_dir = Path("runs/test-001/T0/run-1")
            result_dir.mkdir(parents=True)
            (result_dir / "result.json").write_text(json.dumps(_create_mock_result()))

            result = runner.invoke(
                cli,
                ["report", "test-001", "--format", "markdown", "--output", "report.md"],
            )
        assert "Warning:" not in result.output

    def test_no_warning_when_extensions_match_json(self) -> None:
        """No warning when .json extension matches json format."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result_dir = Path("runs/test-001/T0/run-1")
            result_dir.mkdir(parents=True)
            (result_dir / "result.json").write_text(json.dumps(_create_mock_result()))

            result = runner.invoke(
                cli,
                ["report", "test-001", "--format", "json", "--output", "report.json"],
            )
        assert "Warning:" not in result.output

    def test_warning_on_mismatch_markdown_format_json_ext(self) -> None:
        """Warning emitted when --format markdown but output ends with .json."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result_dir = Path("runs/test-001/T0/run-1")
            result_dir.mkdir(parents=True)
            (result_dir / "result.json").write_text(json.dumps(_create_mock_result()))

            result = runner.invoke(
                cli,
                ["report", "test-001", "--format", "markdown", "--output", "report.json"],
                catch_exceptions=False,
            )
        # CliRunner mixes stdout and stderr into result.output by default
        assert "Warning:" in result.output
        assert ".json" in result.output
        assert "markdown" in result.output

    def test_warning_on_mismatch_json_format_md_ext(self) -> None:
        """Warning emitted when --format json but output ends with .md."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result_dir = Path("runs/test-001/T0/run-1")
            result_dir.mkdir(parents=True)
            (result_dir / "result.json").write_text(json.dumps(_create_mock_result()))

            result = runner.invoke(
                cli,
                ["report", "test-001", "--format", "json", "--output", "report.md"],
                catch_exceptions=False,
            )
        # CliRunner mixes stdout and stderr into result.output by default
        assert "Warning:" in result.output
        assert ".md" in result.output
        assert "json" in result.output

    def test_warning_unit_mismatch_markdown_format_json_ext(self) -> None:
        """Unit test: _warn_format_extension_mismatch emits warning for mismatch."""
        import click

        @click.command()
        def _probe() -> None:
            _warn_format_extension_mismatch("report.json", "markdown")

        result = CliRunner().invoke(_probe, [], catch_exceptions=False)
        # CliRunner mixes stdout and stderr into result.output by default
        assert "Warning:" in result.output
        assert ".json" in result.output

    def test_warning_unit_no_mismatch_matching_ext(self) -> None:
        """Unit test: _warn_format_extension_mismatch silent for matching ext."""
        import click

        @click.command()
        def _probe() -> None:
            _warn_format_extension_mismatch("report.md", "markdown")

        result = CliRunner().invoke(_probe, [], catch_exceptions=False)
        assert "Warning:" not in result.output
