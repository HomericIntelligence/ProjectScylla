"""Negative-path tests for the CLI run command's broad exception handler."""

from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from scylla.cli.main import cli


class TestRunCommandExceptionHandler:
    """Tests for the broad except Exception handler in the run command."""

    def test_run_orchestrator_run_test_error_exits_nonzero(self) -> None:
        """Orchestrator.run_test errors are caught and produce exit code 1."""
        runner = CliRunner()
        with patch("scylla.cli.main.EvalOrchestrator") as mock_orch_cls:
            instance = MagicMock()
            instance.run_test.side_effect = RuntimeError("orchestrator exploded")
            mock_orch_cls.return_value = instance

            result = runner.invoke(cli, ["run", "001-test"])

        assert result.exit_code == 1

    def test_run_orchestrator_run_test_error_message_in_output(self) -> None:
        """Orchestrator.run_test errors include the error message in combined output."""
        runner = CliRunner()
        with patch("scylla.cli.main.EvalOrchestrator") as mock_orch_cls:
            instance = MagicMock()
            instance.run_test.side_effect = RuntimeError("orchestrator exploded")
            mock_orch_cls.return_value = instance

            result = runner.invoke(cli, ["run", "001-test"])

        assert "orchestrator exploded" in result.output

    def test_run_orchestrator_run_single_error_exits_nonzero(self) -> None:
        """Orchestrator.run_single errors are caught and produce exit code 1."""
        runner = CliRunner()
        with patch("scylla.cli.main.EvalOrchestrator") as mock_orch_cls:
            instance = MagicMock()
            instance.run_single.side_effect = ValueError("single run failed")
            mock_orch_cls.return_value = instance

            # --runs 1 with a single tier triggers run_single path
            result = runner.invoke(cli, ["run", "001-test", "--runs", "1", "--tier", "T0"])

        assert result.exit_code == 1

    def test_run_orchestrator_run_single_error_message_in_output(self) -> None:
        """Orchestrator.run_single errors include the error message in combined output."""
        runner = CliRunner()
        with patch("scylla.cli.main.EvalOrchestrator") as mock_orch_cls:
            instance = MagicMock()
            instance.run_single.side_effect = ValueError("single run failed")
            mock_orch_cls.return_value = instance

            result = runner.invoke(cli, ["run", "001-test", "--runs", "1", "--tier", "T0"])

        assert "single run failed" in result.output
