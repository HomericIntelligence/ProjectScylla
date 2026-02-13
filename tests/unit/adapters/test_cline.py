"""Tests for Cline CLI adapter."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import pytest

from scylla.adapters.base import AdapterConfig, AdapterError
from scylla.adapters.cline import ClineAdapter


class TestClineAdapter:
    """Tests for ClineAdapter class."""

    def test_get_name(self) -> None:
        """Test adapter name."""
        adapter = ClineAdapter()
        assert adapter.get_name() == "ClineAdapter"

    def test_cli_executable(self) -> None:
        """Test CLI executable constant."""
        assert ClineAdapter.CLI_EXECUTABLE == "cline"


class TestBuildCommand:
    """Tests for command building."""

    def test_basic_command(self) -> None:
        """Test basic command structure."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            prompt_file = tmppath / "prompt.md"
            prompt_file.write_text("Test prompt")

            adapter = ClineAdapter()
            config = AdapterConfig(
                model="claude-sonnet-4-5-20250929",
                prompt_file=prompt_file,
                workspace=tmppath,
                output_dir=tmppath,
            )

            cmd = adapter._build_command(config, "Test prompt", None)

            assert cmd[0] == "cline"
            assert "--model" in cmd
            assert "claude-sonnet-4-5-20250929" in cmd
            assert "--non-interactive" in cmd
            assert "--prompt" in cmd
            assert "Test prompt" in cmd

    def test_command_with_tools_disabled(self) -> None:
        """Test command with tools disabled."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            prompt_file = tmppath / "prompt.md"
            prompt_file.write_text("Test prompt")

            adapter = ClineAdapter()
            config = AdapterConfig(
                model="claude-sonnet-4-5-20250929",
                prompt_file=prompt_file,
                workspace=tmppath,
                output_dir=tmppath,
            )

            tier_config = MagicMock()
            tier_config.tools_enabled = False
            tier_config.delegation_enabled = None

            cmd = adapter._build_command(config, "Test prompt", tier_config)

            assert "--disable-tools" in cmd

    def test_command_with_extra_args(self) -> None:
        """Test command with extra arguments."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            prompt_file = tmppath / "prompt.md"
            prompt_file.write_text("Test prompt")

            adapter = ClineAdapter()
            config = AdapterConfig(
                model="claude-sonnet-4-5-20250929",
                prompt_file=prompt_file,
                workspace=tmppath,
                output_dir=tmppath,
                extra_args=["--verbose", "--debug"],
            )

            cmd = adapter._build_command(config, "Test prompt", None)

            assert "--verbose" in cmd
            assert "--debug" in cmd


class TestParseTokenCounts:
    """Tests for token count parsing."""

    def test_parse_input_tokens_pattern(self) -> None:
        """Test parsing 'Input tokens: N' pattern."""
        adapter = ClineAdapter()
        stdout = "Input tokens: 1234\nOutput tokens: 567"
        stderr = ""

        tokens_in, tokens_out = adapter._parse_token_counts(stdout, stderr)

        assert tokens_in == 1234
        assert tokens_out == 567

    def test_parse_combined_pattern(self) -> None:
        """Test parsing 'N input, M output' pattern."""
        adapter = ClineAdapter()
        stdout = "Used 1000 input, 500 output tokens"
        stderr = ""

        tokens_in, tokens_out = adapter._parse_token_counts(stdout, stderr)

        assert tokens_in == 1000
        assert tokens_out == 500

    def test_parse_parenthetical_pattern(self) -> None:
        """Test parsing '(N input, M output)' pattern."""
        adapter = ClineAdapter()
        stdout = "Total: 1500 tokens (1000 input, 500 output)"
        stderr = ""

        tokens_in, tokens_out = adapter._parse_token_counts(stdout, stderr)

        assert tokens_in == 1000
        assert tokens_out == 500

    def test_parse_from_stderr(self) -> None:
        """Test parsing from stderr."""
        adapter = ClineAdapter()
        stdout = ""
        stderr = "Input: 100\nOutput: 50"

        tokens_in, tokens_out = adapter._parse_token_counts(stdout, stderr)

        assert tokens_in == 100
        assert tokens_out == 50

    def test_parse_no_tokens(self) -> None:
        """Test parsing with no token information."""
        adapter = ClineAdapter()
        stdout = "Just some output"
        stderr = ""

        tokens_in, tokens_out = adapter._parse_token_counts(stdout, stderr)

        assert tokens_in == 0
        assert tokens_out == 0


class TestParseApiCalls:
    """Tests for API call count parsing."""

    def test_parse_api_calls_pattern(self) -> None:
        """Test parsing 'API calls: N' pattern."""
        adapter = ClineAdapter()
        stdout = "API calls: 3"
        stderr = ""

        count = adapter._parse_api_calls(stdout, stderr)

        assert count == 3

    def test_parse_request_markers(self) -> None:
        """Test counting request markers."""
        adapter = ClineAdapter()
        stdout = "Sending request...\nSending request...\nRequest sent"
        stderr = ""

        count = adapter._parse_api_calls(stdout, stderr)

        assert count == 3

    def test_parse_meaningful_output(self) -> None:
        """Test default count for meaningful output."""
        adapter = ClineAdapter()
        stdout = "A" * 200
        stderr = ""

        count = adapter._parse_api_calls(stdout, stderr)

        assert count == 1

    def test_parse_empty_output(self) -> None:
        """Test zero count for empty output."""
        adapter = ClineAdapter()
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

            adapter = ClineAdapter()
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

            adapter = ClineAdapter()
            config = AdapterConfig(
                model="test",
                prompt_file=tmppath / "prompt.md",
                workspace=tmppath,
                output_dir=tmppath,
                env_vars={"ANTHROPIC_API_KEY": "test-key"},
            )

            env = adapter._prepare_env(config)

            assert env["ANTHROPIC_API_KEY"] == "test-key"


class TestRun:
    """Tests for run method."""

    def test_run_success(self) -> None:
        """Test successful execution."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            prompt_file = tmppath / "prompt.md"
            prompt_file.write_text("Test prompt")

            adapter = ClineAdapter()
            config = AdapterConfig(
                model="claude-sonnet-4-5-20250929",
                prompt_file=prompt_file,
                workspace=tmppath,
                output_dir=tmppath,
            )

            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "Success\nInput tokens: 100\nOutput tokens: 50"
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

            adapter = ClineAdapter()
            config = AdapterConfig(
                model="claude-sonnet-4-5-20250929",
                prompt_file=prompt_file,
                workspace=tmppath,
                output_dir=tmppath,
            )

            tier_config = MagicMock()
            tier_config.tier_id = "T1"
            tier_config.prompt_content = "Be thorough"
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
            assert "--disable-tools" in cmd

    def test_run_timeout(self) -> None:
        """Test execution timeout."""
        import subprocess

        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            prompt_file = tmppath / "prompt.md"
            prompt_file.write_text("Test prompt")

            adapter = ClineAdapter()
            config = AdapterConfig(
                model="claude-sonnet-4-5-20250929",
                prompt_file=prompt_file,
                workspace=tmppath,
                output_dir=tmppath,
                timeout=30,
            )

            timeout_error = subprocess.TimeoutExpired(
                cmd=["cline"],
                timeout=30,
                output=b"partial",
                stderr=b"error",
            )

            with patch("subprocess.run", side_effect=timeout_error):
                result = adapter.run(config)

            assert result.exit_code == -1
            assert result.timed_out is True
            assert "timed out" in result.error_message.lower()

    def test_run_cli_not_found(self) -> None:
        """Test CLI not found error."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            prompt_file = tmppath / "prompt.md"
            prompt_file.write_text("Test prompt")

            adapter = ClineAdapter()
            config = AdapterConfig(
                model="claude-sonnet-4-5-20250929",
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

            adapter = ClineAdapter()
            config = AdapterConfig(
                model="claude-sonnet-4-5-20250929",
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

    def test_run_calculates_cost(self) -> None:
        """Test cost calculation."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            prompt_file = tmppath / "prompt.md"
            prompt_file.write_text("Test prompt")

            adapter = ClineAdapter()
            config = AdapterConfig(
                model="claude-sonnet-4-5-20250929",
                prompt_file=prompt_file,
                workspace=tmppath,
                output_dir=tmppath,
            )

            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "Input tokens: 1000\nOutput tokens: 500"
            mock_result.stderr = ""

            with patch("subprocess.run", return_value=mock_result):
                result = adapter.run(config)

            # Sonnet: 0.003 per 1K input, 0.015 per 1K output
            expected_cost = (1000 / 1000 * 0.003) + (500 / 1000 * 0.015)
            assert result.cost_usd == pytest.approx(expected_cost)


class TestValidation:
    """Tests for configuration validation."""

    def test_validates_prompt_file(self) -> None:
        """Test that missing prompt file raises error."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            adapter = ClineAdapter()
            config = AdapterConfig(
                model="test",
                prompt_file=tmppath / "nonexistent.md",
                workspace=tmppath,
                output_dir=tmppath,
            )

            with pytest.raises(Exception, match="Prompt file not found"):
                adapter.run(config)
