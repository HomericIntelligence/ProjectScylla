"""Tests for CLI commands."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from scylla.cli.main import cli


class TestCLIGroup:
    """Tests for main CLI group."""

    def test_help(self) -> None:
        """Test Help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "ProjectScylla" in result.output
        assert "AI Agent Testing Framework" in result.output

    def test_version(self) -> None:
        """Test Version."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])

        assert result.exit_code == 0
        assert "0.1.0" in result.output


class TestRunCommand:
    """Tests for 'run' command."""

    def test_run_help(self) -> None:
        """Test Run help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["run", "--help"])

        assert result.exit_code == 0
        assert "Run evaluation for a test case" in result.output
        assert "--tier" in result.output
        assert "--model" in result.output
        assert "--runs" in result.output

    def test_run_verbose_and_quiet_error(self) -> None:
        """Test Run verbose and quiet error."""
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

    def test_run_default_model_from_config(self) -> None:
        """Default model_id is read from ConfigLoader, not a hardcoded literal."""
        sentinel_model = "test-model-from-config"

        mock_defaults = MagicMock()
        mock_defaults.default_model = sentinel_model

        mock_loader_instance = MagicMock()
        mock_loader_instance.load_defaults.return_value = mock_defaults

        captured: dict[str, str] = {}

        mock_orchestrator_instance = MagicMock()
        mock_orchestrator_instance.run_batch.return_value = []

        def capture_config(config: object) -> MagicMock:
            captured["model"] = getattr(config, "model", None)
            return mock_orchestrator_instance

        runner = CliRunner()
        with (
            patch("scylla.cli.main.ConfigLoader", return_value=mock_loader_instance),
            patch("scylla.cli.main.EvalOrchestrator", side_effect=capture_config),
        ):
            runner.invoke(cli, ["run", "001-test", "--tier", "T0", "--runs", "1"])

        assert captured.get("model") == sentinel_model


class TestReportCommand:
    """Tests for 'report' command."""

    def test_report_help(self) -> None:
        """Test Report help."""
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
        """Test List help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["list", "--help"])

        assert result.exit_code == 0
        assert "List available test cases" in result.output

    def test_list_basic(self) -> None:
        """Test List basic."""
        runner = CliRunner()
        result = runner.invoke(cli, ["list"])

        assert result.exit_code == 0
        assert "Available tests:" in result.output
        assert "test-001" in result.output

    def test_list_verbose(self) -> None:
        """Test List verbose."""
        runner = CliRunner()
        result = runner.invoke(cli, ["list", "--verbose"])

        assert result.exit_code == 0
        assert "Description:" in result.output


class TestListTiersCommand:
    """Tests for 'list-tiers' command."""

    def test_list_tiers_help(self) -> None:
        """Test List tiers help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["list-tiers", "--help"])

        assert result.exit_code == 0
        assert "List available evaluation tiers" in result.output

    def test_list_tiers(self) -> None:
        """Test List tiers."""
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
        """Test List models help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["list-models", "--help"])

        assert result.exit_code == 0
        assert "List configured models" in result.output

    def test_list_models(self) -> None:
        """Test List models."""
        runner = CliRunner()
        result = runner.invoke(cli, ["list-models"])

        assert result.exit_code == 0
        assert "Configured models:" in result.output
        assert "claude-opus-4-5-20251101" in result.output


class TestStatusCommand:
    """Tests for 'status' command."""

    def test_status_help(self) -> None:
        """Test Status help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["status", "--help"])

        assert result.exit_code == 0
        assert "Show status of a test evaluation" in result.output

    def test_status_basic(self) -> None:
        """Test Status basic."""
        runner = CliRunner()
        result = runner.invoke(cli, ["status", "001-test"])

        assert result.exit_code == 0
        assert "Status for: 001-test" in result.output


class TestAuditModelsCommand:
    """Tests for 'audit models' command."""

    def test_audit_models_help(self) -> None:
        """Test audit models help text."""
        runner = CliRunner()
        result = runner.invoke(cli, ["audit", "models", "--help"])

        assert result.exit_code == 0
        assert "Audit model config files" in result.output
        assert "--config-dir" in result.output

    def test_audit_models_exit_zero_on_clean(self, tmp_path: Path) -> None:
        """Audit models exits 0 when all filenames match model_id."""
        models_dir = tmp_path / "config" / "models"
        models_dir.mkdir(parents=True)
        (models_dir / "claude-opus-4-1.yaml").write_text(
            "model_id: claude-opus-4-1\ncost_per_1k_input: 0.015\ncost_per_1k_output: 0.075\n"
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["audit", "models", "--config-dir", str(tmp_path)])

        assert result.exit_code == 0
        assert "OK: all model config filenames match their model_id." in result.output

    def test_audit_models_exit_nonzero_on_mismatch(self, tmp_path: Path) -> None:
        """Audit models exits 1 when a filename does not match model_id."""
        models_dir = tmp_path / "config" / "models"
        models_dir.mkdir(parents=True)
        # Filename is 'wrong-name.yaml' but model_id is 'claude-opus-4-1'
        (models_dir / "wrong-name.yaml").write_text(
            "model_id: claude-opus-4-1\ncost_per_1k_input: 0.015\ncost_per_1k_output: 0.075\n"
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["audit", "models", "--config-dir", str(tmp_path)])

        assert result.exit_code == 1
        assert "MISMATCH" in result.output

    def test_audit_models_skips_underscore_prefixed(self, tmp_path: Path) -> None:
        """Audit models skips files prefixed with _ even when model_id mismatches."""
        models_dir = tmp_path / "config" / "models"
        models_dir.mkdir(parents=True)
        # _test-fixture.yaml with mismatched model_id should be skipped
        (models_dir / "_test-fixture.yaml").write_text(
            "model_id: some-other-id\ncost_per_1k_input: 0.001\ncost_per_1k_output: 0.001\n"
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["audit", "models", "--config-dir", str(tmp_path)])

        assert result.exit_code == 0
        assert "OK: all model config filenames match their model_id." in result.output

    def test_audit_models_missing_models_dir(self, tmp_path: Path) -> None:
        """Audit models exits 1 with ERROR when config/models/ does not exist."""
        runner = CliRunner()
        result = runner.invoke(cli, ["audit", "models", "--config-dir", str(tmp_path)])

        assert result.exit_code == 1
        assert "ERROR" in result.output

    def test_audit_models_multiple_mismatches(self, tmp_path: Path) -> None:
        """Audit models reports all mismatches and exits 1."""
        models_dir = tmp_path / "config" / "models"
        models_dir.mkdir(parents=True)
        (models_dir / "bad-name-a.yaml").write_text(
            "model_id: claude-opus-4-1\ncost_per_1k_input: 0.015\ncost_per_1k_output: 0.075\n"
        )
        (models_dir / "bad-name-b.yaml").write_text(
            "model_id: claude-sonnet-4-5-20250929\n"
            "cost_per_1k_input: 0.003\ncost_per_1k_output: 0.015\n"
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["audit", "models", "--config-dir", str(tmp_path)])

        assert result.exit_code == 1
        assert result.output.count("MISMATCH") == 2

    @pytest.mark.parametrize(
        "model_id,filename",
        [
            ("claude-opus-4-1", "claude-opus-4-1.yaml"),
            ("claude-sonnet-4-5-20250929", "claude-sonnet-4-5-20250929.yaml"),
        ],
    )
    def test_audit_models_clean_parametrized(
        self, tmp_path: Path, model_id: str, filename: str
    ) -> None:
        """Audit models exits 0 for each correctly-named config file."""
        models_dir = tmp_path / "config" / "models"
        models_dir.mkdir(parents=True)
        (models_dir / filename).write_text(
            f"model_id: {model_id}\ncost_per_1k_input: 0.001\ncost_per_1k_output: 0.001\n"
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["audit", "models", "--config-dir", str(tmp_path)])

        assert result.exit_code == 0
        assert "OK" in result.output
