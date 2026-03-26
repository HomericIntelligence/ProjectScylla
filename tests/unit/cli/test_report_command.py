"""Tests for the scylla report CLI command."""

import json
import tempfile
from pathlib import Path

from click.testing import CliRunner

from scylla.cli.main import cli


class TestReportCommandHelp:
    """Tests for report command help and argument validation."""

    def test_report_help(self) -> None:
        """Test report --help shows usage."""
        runner = CliRunner()
        result = runner.invoke(cli, ["report", "--help"])
        assert result.exit_code == 0
        assert "TEST_ID" in result.output
        assert "--format" in result.output
        assert "--output" in result.output

    def test_report_missing_test_id(self) -> None:
        """Test report without test_id shows error."""
        runner = CliRunner()
        result = runner.invoke(cli, ["report"])
        assert result.exit_code != 0

    def test_report_invalid_format(self) -> None:
        """Test report with invalid format is rejected."""
        runner = CliRunner()
        result = runner.invoke(cli, ["report", "001-test", "--format", "html"])
        assert result.exit_code != 0
        assert "Invalid value" in result.output


class TestReportJsonStdout:
    """Tests for --format json --output - (the core feature)."""

    def test_json_to_stdout(self) -> None:
        """Test --format json --output - writes valid JSON to stdout."""
        runner = CliRunner()
        result = runner.invoke(cli, ["report", "001-test", "-f", "json", "-o", "-"])
        assert result.exit_code == 0

        parsed = json.loads(result.output)
        assert parsed["test_id"] == "001-test"
        assert "tiers" in parsed

    def test_json_to_stdout_is_pure_json(self) -> None:
        """Test --output - stdout contains only valid JSON, no status messages."""
        runner = CliRunner()
        result = runner.invoke(cli, ["report", "001-test", "-f", "json", "-o", "-"])
        assert result.exit_code == 0

        # stdout should be pure JSON — json.loads would fail if status
        # messages were mixed into the output stream.
        parsed = json.loads(result.output)
        assert isinstance(parsed, dict)
        assert parsed["test_id"] == "001-test"


class TestReportMarkdownStdout:
    """Tests for --format markdown --output -."""

    def test_markdown_to_stdout(self) -> None:
        """Test --format markdown --output - writes markdown to stdout."""
        runner = CliRunner()
        result = runner.invoke(cli, ["report", "001-test", "-f", "markdown", "-o", "-"])
        assert result.exit_code == 0
        assert "# Evaluation Report:" in result.output


class TestReportFileOutput:
    """Tests for writing reports to files."""

    def test_json_to_explicit_file(self) -> None:
        """Test --format json --output <path> writes JSON to the specified file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            outfile = Path(tmpdir) / "out.json"
            runner = CliRunner()
            result = runner.invoke(cli, ["report", "001-test", "-f", "json", "-o", str(outfile)])
            assert result.exit_code == 0
            assert outfile.exists()

            parsed = json.loads(outfile.read_text())
            assert parsed["test_id"] == "001-test"

    def test_markdown_to_explicit_file(self) -> None:
        """Test --format markdown --output <path> writes markdown to the specified file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            outfile = Path(tmpdir) / "out.md"
            runner = CliRunner()
            result = runner.invoke(
                cli, ["report", "001-test", "-f", "markdown", "-o", str(outfile)]
            )
            assert result.exit_code == 0
            assert outfile.exists()
            assert "# Evaluation Report:" in outfile.read_text()

    def test_json_default_file(self) -> None:
        """Test --format json without --output writes to default path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = CliRunner()
            result = runner.invoke(
                cli,
                ["report", "001-test", "-f", "json", "--base-path", tmpdir],
            )
            assert result.exit_code == 0

            expected = Path(tmpdir) / "001-test" / "report.json"
            assert expected.exists()

            parsed = json.loads(expected.read_text())
            assert parsed["test_id"] == "001-test"

    def test_markdown_default_file(self) -> None:
        """Test --format markdown without --output writes to default path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = CliRunner()
            result = runner.invoke(
                cli,
                ["report", "001-test", "-f", "markdown", "--base-path", tmpdir],
            )
            assert result.exit_code == 0

            expected = Path(tmpdir) / "001-test" / "report.md"
            assert expected.exists()
            assert "# Evaluation Report:" in expected.read_text()

    def test_output_file_creates_parent_dirs(self) -> None:
        """Test --output creates parent directories if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            outfile = Path(tmpdir) / "nested" / "dir" / "report.json"
            runner = CliRunner()
            result = runner.invoke(cli, ["report", "001-test", "-f", "json", "-o", str(outfile)])
            assert result.exit_code == 0
            assert outfile.exists()
