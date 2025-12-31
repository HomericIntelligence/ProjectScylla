"""Tests for CLI commands.

Python justification: Required for pytest testing framework and Click testing.
"""

from click.testing import CliRunner

from scylla.cli.main import cli


class TestCLIGroup:
    """Tests for main CLI group."""

    def test_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "ProjectScylla" in result.output
        assert "AI Agent Testing Framework" in result.output

    def test_version(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])

        assert result.exit_code == 0
        assert "0.1.0" in result.output


class TestRunCommand:
    """Tests for 'run' command."""

    def test_run_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["run", "--help"])

        assert result.exit_code == 0
        assert "Run evaluation for a test case" in result.output
        assert "--tier" in result.output
        assert "--model" in result.output
        assert "--runs" in result.output

    def test_run_verbose_and_quiet_error(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["run", "001-test", "--verbose", "--quiet"])

        assert result.exit_code != 0
        assert "Cannot use --verbose and --quiet together" in result.output

    def test_run_missing_test_error(self) -> None:
        """Test that running a non-existent test shows error."""
        runner = CliRunner()
        result = runner.invoke(cli, ["run", "nonexistent-test", "--tier", "T0", "--runs", "1"])

        # Should fail because test doesn't exist
        assert result.exit_code == 1
        assert "Error" in result.output


class TestReportCommand:
    """Tests for 'report' command."""

    def test_report_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["report", "--help"])

        assert result.exit_code == 0
        assert "Generate report for a completed test" in result.output
        assert "--format" in result.output

    def test_report_basic_no_results(self) -> None:
        """Test report command with no results exits with error."""
        runner = CliRunner()
        result = runner.invoke(cli, ["report", "001-test"])

        # Should fail because no results exist
        assert result.exit_code == 1
        assert "Generating markdown report for: 001-test" in result.output
        assert "No results found" in result.output

    def test_report_with_format_no_results(self) -> None:
        """Test report command with format option and no results."""
        runner = CliRunner()
        result = runner.invoke(cli, ["report", "001-test", "--format", "json"])

        # Should fail because no results exist
        assert result.exit_code == 1
        assert "Generating json report for: 001-test" in result.output
        assert "No results found" in result.output


class TestListCommand:
    """Tests for 'list' command."""

    def test_list_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["list", "--help"])

        assert result.exit_code == 0
        assert "List available test cases" in result.output

    def test_list_basic(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["list"])

        assert result.exit_code == 0
        assert "Available tests:" in result.output
        assert "001-justfile-to-makefile" in result.output

    def test_list_verbose(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["list", "--verbose"])

        assert result.exit_code == 0
        assert "Description:" in result.output


class TestListTiersCommand:
    """Tests for 'list-tiers' command."""

    def test_list_tiers_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["list-tiers", "--help"])

        assert result.exit_code == 0
        assert "List available evaluation tiers" in result.output

    def test_list_tiers(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["list-tiers"])

        assert result.exit_code == 0
        assert "Evaluation tiers:" in result.output
        assert "T0 (Vanilla)" in result.output
        assert "T1 (Prompted)" in result.output
        assert "T2 (Skills)" in result.output
        assert "T3 (Tooling)" in result.output


class TestListModelsCommand:
    """Tests for 'list-models' command."""

    def test_list_models_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["list-models", "--help"])

        assert result.exit_code == 0
        assert "List configured models" in result.output

    def test_list_models(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["list-models"])

        assert result.exit_code == 0
        assert "Configured models:" in result.output
        assert "claude-opus-4-5-20251101" in result.output


class TestStatusCommand:
    """Tests for 'status' command."""

    def test_status_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["status", "--help"])

        assert result.exit_code == 0
        assert "Show status of a test evaluation" in result.output

    def test_status_basic(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["status", "001-test"])

        assert result.exit_code == 0
        assert "Status for: 001-test" in result.output
