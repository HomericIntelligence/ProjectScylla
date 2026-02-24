"""Tests for OpenAI Codex CLI adapter."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import pytest

from scylla.adapters.base import AdapterConfig, AdapterError
from scylla.adapters.openai_codex import OpenAICodexAdapter


class TestOpenAICodexAdapter:
    """Tests for OpenAICodexAdapter class."""

    def test_get_name(self) -> None:
        """Test adapter name."""
        adapter = OpenAICodexAdapter()
        assert adapter.get_name() == "OpenAICodexAdapter"

    def test_cli_executable(self) -> None:
        """Test CLI executable constant."""
        assert OpenAICodexAdapter.CLI_EXECUTABLE == "codex"


class TestBuildCommand:
    """Tests for command building."""

    def test_basic_command(self) -> None:
        """Test basic command structure."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            prompt_file = tmppath / "prompt.md"
            prompt_file.write_text("Test prompt")

            adapter = OpenAICodexAdapter()
            config = AdapterConfig(
                model="gpt-4",
                prompt_file=prompt_file,
                workspace=tmppath,
                output_dir=tmppath,
            )

            cmd = adapter._build_command(config, "Test prompt", None)

            assert cmd[0] == "codex"
            assert "--model" in cmd
            assert "gpt-4" in cmd
            assert "--quiet" in cmd
            assert cmd[-1] == "Test prompt"

    def test_command_with_tools_disabled(self) -> None:
        """Test command with tools disabled."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            prompt_file = tmppath / "prompt.md"
            prompt_file.write_text("Test prompt")

            adapter = OpenAICodexAdapter()
            config = AdapterConfig(
                model="gpt-4",
                prompt_file=prompt_file,
                workspace=tmppath,
                output_dir=tmppath,
            )

            tier_config = MagicMock()
            tier_config.tools_enabled = False
            tier_config.delegation_enabled = None

            cmd = adapter._build_command(config, "Test prompt", tier_config)

            assert "--no-tools" in cmd

    def test_command_with_extra_args(self) -> None:
        """Test command with extra arguments."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            prompt_file = tmppath / "prompt.md"
            prompt_file.write_text("Test prompt")

            adapter = OpenAICodexAdapter()
            config = AdapterConfig(
                model="gpt-4",
                prompt_file=prompt_file,
                workspace=tmppath,
                output_dir=tmppath,
                extra_args=["--temperature", "0.5"],
            )

            cmd = adapter._build_command(config, "Test prompt", None)

            assert "--temperature" in cmd
            assert "0.5" in cmd


class TestParseTokenCounts:
    """Tests for token count parsing."""

    def test_parse_json_usage(self) -> None:
        """Test parsing JSON usage format."""
        adapter = OpenAICodexAdapter()
        stdout = '{"usage": {"prompt_tokens": 100, "completion_tokens": 50}}'
        stderr = ""

        tokens_in, tokens_out = adapter._parse_token_counts(stdout, stderr)

        assert tokens_in == 100
        assert tokens_out == 50

    def test_parse_prompt_tokens_pattern(self) -> None:
        """Test parsing 'prompt_tokens: N' pattern."""
        adapter = OpenAICodexAdapter()
        stdout = "prompt_tokens: 200\ncompletion_tokens: 100"
        stderr = ""

        tokens_in, tokens_out = adapter._parse_token_counts(stdout, stderr)

        assert tokens_in == 200
        assert tokens_out == 100

    def test_parse_combined_pattern(self) -> None:
        """Test parsing 'N input, M output' pattern."""
        adapter = OpenAICodexAdapter()
        stdout = "Used 500 input, 250 output tokens"
        stderr = ""

        tokens_in, tokens_out = adapter._parse_token_counts(stdout, stderr)

        assert tokens_in == 500
        assert tokens_out == 250

    def test_parse_from_stderr(self) -> None:
        """Test parsing from stderr."""
        adapter = OpenAICodexAdapter()
        stdout = ""
        stderr = "prompt_tokens: 75\ncompletion_tokens: 25"

        tokens_in, tokens_out = adapter._parse_token_counts(stdout, stderr)

        assert tokens_in == 75
        assert tokens_out == 25

    def test_parse_no_tokens(self) -> None:
        """Test parsing with no token information."""
        adapter = OpenAICodexAdapter()
        stdout = "Just some output"
        stderr = ""

        tokens_in, tokens_out = adapter._parse_token_counts(stdout, stderr)

        assert tokens_in == 0
        assert tokens_out == 0


class TestParseApiCalls:
    """Tests for API call count parsing."""

    def test_parse_api_calls_pattern(self) -> None:
        """Test parsing 'API calls: N' pattern."""
        adapter = OpenAICodexAdapter()
        stdout = "API calls: 3"
        stderr = ""

        count = adapter._parse_api_calls(stdout, stderr)

        assert count == 3

    def test_parse_finish_reason(self) -> None:
        """Test counting finish_reason markers."""
        adapter = OpenAICodexAdapter()
        stdout = '{"finish_reason": "stop"}{"finish_reason": "stop"}'
        stderr = ""

        count = adapter._parse_api_calls(stdout, stderr)

        assert count == 2

    def test_parse_meaningful_output(self) -> None:
        """Test default count for meaningful output."""
        adapter = OpenAICodexAdapter()
        stdout = "A" * 200
        stderr = ""

        count = adapter._parse_api_calls(stdout, stderr)

        assert count == 1

    def test_parse_empty_output(self) -> None:
        """Test zero count for empty output."""
        adapter = OpenAICodexAdapter()
        stdout = ""
        stderr = ""

        count = adapter._parse_api_calls(stdout, stderr)

        assert count == 0


class TestPrepareEnv:
    """Tests for environment preparation."""

    def test_prepare_env_inherits_current(self) -> None:
        """Test that env inherits current environment."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            adapter = OpenAICodexAdapter()
            config = AdapterConfig(
                model="test",
                prompt_file=tmppath / "prompt.md",
                workspace=tmppath,
                output_dir=tmppath,
                env_vars={},
            )

            env = adapter._prepare_env(config)

            assert len(env) > 0

    def test_prepare_env_adds_custom_vars(self) -> None:
        """Test that custom env vars are added."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            adapter = OpenAICodexAdapter()
            config = AdapterConfig(
                model="test",
                prompt_file=tmppath / "prompt.md",
                workspace=tmppath,
                output_dir=tmppath,
                env_vars={"OPENAI_API_KEY": "test-key"},
            )

            env = adapter._prepare_env(config)

            assert env["OPENAI_API_KEY"] == "test-key"


class TestRun:
    """Tests for run method."""

    def test_run_success(self) -> None:
        """Test successful execution."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            prompt_file = tmppath / "prompt.md"
            prompt_file.write_text("Test prompt")

            adapter = OpenAICodexAdapter()
            config = AdapterConfig(
                model="gpt-4",
                prompt_file=prompt_file,
                workspace=tmppath,
                output_dir=tmppath,
            )

            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = '{"usage": {"prompt_tokens": 100, "completion_tokens": 50}}'
            mock_result.stderr = ""

            with patch("subprocess.run", return_value=mock_result):
                result = adapter.run(config)

            assert result.exit_code == 0
            assert result.tokens_input == 100
            assert result.tokens_output == 50
            assert result.timed_out is False

    def test_run_with_tier_config(self) -> None:
        """Test execution with tier configuration."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            prompt_file = tmppath / "prompt.md"
            prompt_file.write_text("Test prompt")

            adapter = OpenAICodexAdapter()
            config = AdapterConfig(
                model="gpt-4",
                prompt_file=prompt_file,
                workspace=tmppath,
                output_dir=tmppath,
            )

            tier_config = MagicMock()
            tier_config.tier_id = "T1"
            tier_config.tools_enabled = False
            tier_config.delegation_enabled = None

            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "Success"
            mock_result.stderr = ""

            with patch("subprocess.run", return_value=mock_result) as mock_run:
                adapter.run(config, tier_config)

            call_args = mock_run.call_args
            cmd = call_args[0][0]
            assert "--no-tools" in cmd

    def test_run_timeout(self) -> None:
        """Test execution timeout."""
        import subprocess

        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            prompt_file = tmppath / "prompt.md"
            prompt_file.write_text("Test prompt")

            adapter = OpenAICodexAdapter()
            config = AdapterConfig(
                model="gpt-4",
                prompt_file=prompt_file,
                workspace=tmppath,
                output_dir=tmppath,
                timeout=30,
            )

            timeout_error = subprocess.TimeoutExpired(
                cmd=["codex"],
                timeout=30,
                output=b"partial",
                stderr=b"error",
            )

            with patch("subprocess.run", side_effect=timeout_error):
                result = adapter.run(config)

            assert result.exit_code == -1
            assert result.timed_out is True
            assert result.error_message is not None
            assert "timed out" in result.error_message.lower()

    def test_run_cli_not_found(self) -> None:
        """Test CLI not found error."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            prompt_file = tmppath / "prompt.md"
            prompt_file.write_text("Test prompt")

            adapter = OpenAICodexAdapter()
            config = AdapterConfig(
                model="gpt-4",
                prompt_file=prompt_file,
                workspace=tmppath,
                output_dir=tmppath,
            )

            with patch("subprocess.run", side_effect=FileNotFoundError()):
                with pytest.raises(AdapterError, match="CLI not found"):
                    adapter.run(config)

    def test_run_writes_logs(self) -> None:
        """Test that logs are written on success."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            prompt_file = tmppath / "prompt.md"
            prompt_file.write_text("Test prompt")

            adapter = OpenAICodexAdapter()
            config = AdapterConfig(
                model="gpt-4",
                prompt_file=prompt_file,
                workspace=tmppath,
                output_dir=tmppath,
            )

            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "stdout content"
            mock_result.stderr = "stderr content"

            with patch("subprocess.run", return_value=mock_result):
                adapter.run(config)

            # Logs are written directly to output_dir (no logs/ subdirectory)
            assert (tmppath / "stdout.log").read_text() == "stdout content"
            assert (tmppath / "stderr.log").read_text() == "stderr content"

    def test_run_calculates_cost_gpt4(self) -> None:
        """Test cost calculation for GPT-4."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            prompt_file = tmppath / "prompt.md"
            prompt_file.write_text("Test prompt")

            adapter = OpenAICodexAdapter()
            config = AdapterConfig(
                model="gpt-4",
                prompt_file=prompt_file,
                workspace=tmppath,
                output_dir=tmppath,
            )

            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "prompt_tokens: 1000\ncompletion_tokens: 500"
            mock_result.stderr = ""

            with patch("subprocess.run", return_value=mock_result):
                result = adapter.run(config)

            # GPT-4: 0.03 per 1K input, 0.06 per 1K output
            expected_cost = (1000 / 1000 * 0.03) + (500 / 1000 * 0.06)
            assert result.cost_usd == pytest.approx(expected_cost)


class TestValidation:
    """Tests for configuration validation."""

    def test_validates_prompt_file(self) -> None:
        """Test that missing prompt file raises error."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            adapter = OpenAICodexAdapter()
            config = AdapterConfig(
                model="test",
                prompt_file=tmppath / "nonexistent.md",
                workspace=tmppath,
                output_dir=tmppath,
            )

            with pytest.raises(Exception, match="Prompt file not found"):
                adapter.run(config)
