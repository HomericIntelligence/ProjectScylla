"""Tests for BaseCliAdapter class."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scylla.adapters.base import AdapterConfig, AdapterError
from scylla.adapters.base_cli import BaseCliAdapter


class TestCliAdapter(BaseCliAdapter):
    """Concrete test implementation of BaseCliAdapter."""

    CLI_EXECUTABLE = "test-cli"
    _api_call_fallback_pattern = r"test_pattern"

    def _build_command(self, config: AdapterConfig, prompt: str, tier_config) -> list[str]:
        """Build test command."""
        return [self.CLI_EXECUTABLE, "--model", config.model, prompt]

    def _parse_token_counts(self, stdout: str, stderr: str) -> tuple[int, int]:
        """Parse test token counts."""
        return (100, 200)


class TestBaseCliAdapter:
    """Tests for BaseCliAdapter abstract class."""

    def test_cannot_instantiate_abstract_class(self) -> None:
        """Test that BaseCliAdapter cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseCliAdapter()  # type: ignore

    def test_concrete_implementation_instantiates(self) -> None:
        """Test that concrete implementation can be instantiated."""
        adapter = TestCliAdapter()
        assert adapter is not None
        assert adapter.CLI_EXECUTABLE == "test-cli"


class TestRun:
    """Tests for run() method execution flow."""

    @patch("scylla.adapters.base_cli.subprocess.run")
    def test_successful_run(self, mock_run: MagicMock, adapter_config: AdapterConfig) -> None:
        """Test successful CLI execution."""
        # Setup mock
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Success"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        # Execute
        adapter = TestCliAdapter()
        result = adapter.run(adapter_config)

        # Verify
        assert result.exit_code == 0
        assert result.stdout == "Success"
        assert result.stderr == ""
        assert result.timed_out is False
        assert result.token_stats.input_tokens == 100
        assert result.token_stats.output_tokens == 200
        assert result.duration_seconds > 0

    @patch("scylla.adapters.base_cli.subprocess.run")
    def test_run_with_nonzero_exit(
        self, mock_run: MagicMock, adapter_config: AdapterConfig
    ) -> None:
        """Test CLI execution with non-zero exit code."""
        # Setup mock
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Error occurred"
        mock_run.return_value = mock_result

        # Execute
        adapter = TestCliAdapter()
        result = adapter.run(adapter_config)

        # Verify
        assert result.exit_code == 1
        assert result.stderr == "Error occurred"
        assert result.timed_out is False

    @patch("scylla.adapters.base_cli.subprocess.run")
    def test_run_timeout(self, mock_run: MagicMock, adapter_config: AdapterConfig) -> None:
        """Test CLI execution timeout."""
        # Setup mock to raise TimeoutExpired
        mock_run.side_effect = subprocess.TimeoutExpired(
            cmd=["test-cli"], timeout=3600, output=b"Partial output", stderr=b""
        )

        # Execute
        adapter = TestCliAdapter()
        result = adapter.run(adapter_config)

        # Verify
        assert result.exit_code == -1
        assert result.timed_out is True
        assert "timed out" in result.error_message.lower()
        assert result.stdout == "Partial output"

    @patch("scylla.adapters.base_cli.subprocess.run")
    def test_run_cli_not_found(self, mock_run: MagicMock, adapter_config: AdapterConfig) -> None:
        """Test CLI executable not found."""
        mock_run.side_effect = FileNotFoundError()

        adapter = TestCliAdapter()
        with pytest.raises(AdapterError) as exc_info:
            adapter.run(adapter_config)

        assert "not found" in str(exc_info.value).lower()
        assert "test-cli" in str(exc_info.value)

    @patch("scylla.adapters.base_cli.subprocess.run")
    def test_run_subprocess_error(self, mock_run: MagicMock, adapter_config: AdapterConfig) -> None:
        """Test subprocess error handling."""
        mock_run.side_effect = subprocess.SubprocessError("Subprocess failed")

        adapter = TestCliAdapter()
        with pytest.raises(AdapterError) as exc_info:
            adapter.run(adapter_config)

        assert "failed" in str(exc_info.value).lower()

    @patch("scylla.adapters.base_cli.subprocess.run")
    def test_run_writes_logs(self, mock_run: MagicMock, adapter_config: AdapterConfig) -> None:
        """Test that logs are written to output directory."""
        # Setup mock
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Test stdout"
        mock_result.stderr = "Test stderr"
        mock_run.return_value = mock_result

        # Execute
        adapter = TestCliAdapter()
        adapter.run(adapter_config)

        # Verify logs were written
        assert (adapter_config.output_dir / "stdout.log").exists()
        assert (adapter_config.output_dir / "stderr.log").exists()
        assert (adapter_config.output_dir / "stdout.log").read_text() == "Test stdout"
        assert (adapter_config.output_dir / "stderr.log").read_text() == "Test stderr"


class TestPrepareEnv:
    """Tests for _prepare_env() method."""

    def test_prepare_env_copies_environment(self, adapter_config: AdapterConfig) -> None:
        """Test that _prepare_env copies os.environ."""
        adapter = TestCliAdapter()
        env = adapter._prepare_env(adapter_config)

        # Should include system env vars
        assert "PATH" in env

    def test_prepare_env_merges_config_vars(self, temp_workspace: Path, prompt_file: Path) -> None:
        """Test that _prepare_env merges config env_vars."""
        config = AdapterConfig(
            model="gpt-4",
            prompt_file=prompt_file,
            workspace=temp_workspace,
            output_dir=temp_workspace,
            env_vars={"CUSTOM_KEY": "custom_value", "API_KEY": "secret"},
        )

        adapter = TestCliAdapter()
        env = adapter._prepare_env(config)

        assert env["CUSTOM_KEY"] == "custom_value"
        assert env["API_KEY"] == "secret"


class TestParseApiCalls:
    """Tests for _parse_api_calls() method."""

    def test_parse_api_calls_explicit_count(self) -> None:
        """Test parsing explicit API call count."""
        adapter = TestCliAdapter()
        stdout = "API calls: 5\nOther output"
        stderr = ""

        count = adapter._parse_api_calls(stdout, stderr)
        assert count == 5

    def test_parse_api_calls_count_prefix(self) -> None:
        """Test parsing API call count with prefix."""
        adapter = TestCliAdapter()
        stdout = "Made 3 API calls"
        stderr = ""

        count = adapter._parse_api_calls(stdout, stderr)
        assert count == 3

    def test_parse_api_calls_fallback_pattern(self) -> None:
        """Test parsing API calls using fallback pattern."""
        adapter = TestCliAdapter()
        stdout = "test_pattern\ntest_pattern\ntest_pattern"
        stderr = ""

        count = adapter._parse_api_calls(stdout, stderr)
        assert count == 3

    def test_parse_api_calls_default_for_long_output(self) -> None:
        """Test default API call count for long output."""
        adapter = TestCliAdapter()
        stdout = "x" * 150  # More than 100 characters
        stderr = ""

        count = adapter._parse_api_calls(stdout, stderr)
        assert count == 1

    def test_parse_api_calls_zero_for_short_output(self) -> None:
        """Test zero API calls for short output."""
        adapter = TestCliAdapter()
        stdout = "short"
        stderr = ""

        count = adapter._parse_api_calls(stdout, stderr)
        assert count == 0


class TestAbstractMethods:
    """Tests for abstract method requirements."""

    def test_build_command_must_be_implemented(self) -> None:
        """Test that _build_command must be implemented."""

        class IncompleteAdapter(BaseCliAdapter):
            CLI_EXECUTABLE = "incomplete"

            def _parse_token_counts(self, stdout: str, stderr: str) -> tuple[int, int]:
                return (0, 0)

        with pytest.raises(TypeError):
            IncompleteAdapter()  # type: ignore

    def test_parse_token_counts_must_be_implemented(self) -> None:
        """Test that _parse_token_counts must be implemented."""

        class IncompleteAdapter(BaseCliAdapter):
            CLI_EXECUTABLE = "incomplete"

            def _build_command(self, config: AdapterConfig, prompt: str, tier_config) -> list[str]:
                return ["cmd"]

        with pytest.raises(TypeError):
            IncompleteAdapter()  # type: ignore
