"""Tests for Claude Code CLI adapter.

Python justification: Required for pytest testing framework.
"""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import pytest

from scylla.adapters.base import AdapterConfig, AdapterError
from scylla.adapters.claude_code import ClaudeCodeAdapter


class TestClaudeCodeAdapter:
    """Tests for ClaudeCodeAdapter class."""

    def test_get_name(self) -> None:
        """Test adapter name."""
        adapter = ClaudeCodeAdapter()
        assert adapter.get_name() == "ClaudeCodeAdapter"

    def test_cli_executable(self) -> None:
        """Test CLI executable constant."""
        assert ClaudeCodeAdapter.CLI_EXECUTABLE == "claude"


class TestBuildCommand:
    """Tests for command building."""

    def test_basic_command(self) -> None:
        """Test basic command structure."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            prompt_file = tmppath / "prompt.md"
            prompt_file.write_text("Test prompt")

            adapter = ClaudeCodeAdapter()
            config = AdapterConfig(
                model="claude-sonnet-4-20250514",
                prompt_file=prompt_file,
                workspace=tmppath,
                output_dir=tmppath,
            )

            cmd = adapter._build_command(config, "Test prompt", None)

            assert cmd[0] == "claude"
            assert "--model" in cmd
            assert "claude-sonnet-4-20250514" in cmd
            assert "--print" in cmd
            assert "--dangerously-skip-permissions" in cmd
            assert "Test prompt" == cmd[-1]

    def test_command_with_tools_disabled(self) -> None:
        """Test command with tools disabled."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            prompt_file = tmppath / "prompt.md"
            prompt_file.write_text("Test prompt")

            adapter = ClaudeCodeAdapter()
            config = AdapterConfig(
                model="claude-sonnet-4-20250514",
                prompt_file=prompt_file,
                workspace=tmppath,
                output_dir=tmppath,
            )

            tier_config = MagicMock()
            tier_config.tools_enabled = False
            tier_config.delegation_enabled = None

            cmd = adapter._build_command(config, "Test prompt", tier_config)

            assert "--no-tools" in cmd

    def test_command_with_tools_enabled(self) -> None:
        """Test command with tools enabled (no --no-tools flag)."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            prompt_file = tmppath / "prompt.md"
            prompt_file.write_text("Test prompt")

            adapter = ClaudeCodeAdapter()
            config = AdapterConfig(
                model="claude-sonnet-4-20250514",
                prompt_file=prompt_file,
                workspace=tmppath,
                output_dir=tmppath,
            )

            tier_config = MagicMock()
            tier_config.tools_enabled = True
            tier_config.delegation_enabled = None

            cmd = adapter._build_command(config, "Test prompt", tier_config)

            assert "--no-tools" not in cmd

    def test_command_with_extra_args(self) -> None:
        """Test command with extra arguments."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            prompt_file = tmppath / "prompt.md"
            prompt_file.write_text("Test prompt")

            adapter = ClaudeCodeAdapter()
            config = AdapterConfig(
                model="claude-sonnet-4-20250514",
                prompt_file=prompt_file,
                workspace=tmppath,
                output_dir=tmppath,
                extra_args=["--verbose", "--max-turns", "5"],
            )

            cmd = adapter._build_command(config, "Test prompt", None)

            assert "--verbose" in cmd
            assert "--max-turns" in cmd
            assert "5" in cmd


class TestParseTokenCounts:
    """Tests for token count parsing."""

    def test_parse_input_tokens_pattern(self) -> None:
        """Test parsing 'Input tokens: N' pattern."""
        adapter = ClaudeCodeAdapter()
        stdout = "Input tokens: 1234\nOutput tokens: 567"
        stderr = ""

        tokens_in, tokens_out = adapter._parse_token_counts(stdout, stderr)

        assert tokens_in == 1234
        assert tokens_out == 567

    def test_parse_combined_pattern(self) -> None:
        """Test parsing '1234 input, 567 output' pattern."""
        adapter = ClaudeCodeAdapter()
        stdout = "Used 1000 input, 500 output tokens"
        stderr = ""

        tokens_in, tokens_out = adapter._parse_token_counts(stdout, stderr)

        assert tokens_in == 1000
        assert tokens_out == 500

    def test_parse_parenthetical_pattern(self) -> None:
        """Test parsing '(1234 input, 567 output)' pattern."""
        adapter = ClaudeCodeAdapter()
        stdout = "Total: 1801 tokens (1234 input, 567 output)"
        stderr = ""

        tokens_in, tokens_out = adapter._parse_token_counts(stdout, stderr)

        assert tokens_in == 1234
        assert tokens_out == 567

    def test_parse_from_stderr(self) -> None:
        """Test parsing token counts from stderr."""
        adapter = ClaudeCodeAdapter()
        stdout = ""
        stderr = "Input tokens: 100\nOutput tokens: 50"

        tokens_in, tokens_out = adapter._parse_token_counts(stdout, stderr)

        assert tokens_in == 100
        assert tokens_out == 50

    def test_parse_no_tokens(self) -> None:
        """Test parsing with no token information."""
        adapter = ClaudeCodeAdapter()
        stdout = "Just some output"
        stderr = ""

        tokens_in, tokens_out = adapter._parse_token_counts(stdout, stderr)

        assert tokens_in == 0
        assert tokens_out == 0

    def test_parse_case_insensitive(self) -> None:
        """Test that parsing is case insensitive."""
        adapter = ClaudeCodeAdapter()
        stdout = "INPUT TOKENS: 200\noutput tokens: 100"
        stderr = ""

        tokens_in, tokens_out = adapter._parse_token_counts(stdout, stderr)

        assert tokens_in == 200
        assert tokens_out == 100


class TestParseApiCalls:
    """Tests for API call count parsing."""

    def test_parse_api_calls_pattern(self) -> None:
        """Test parsing 'API calls: N' pattern."""
        adapter = ClaudeCodeAdapter()
        stdout = "API calls: 5"
        stderr = ""

        count = adapter._parse_api_calls(stdout, stderr)

        assert count == 5

    def test_parse_n_api_calls_pattern(self) -> None:
        """Test parsing 'N API calls' pattern."""
        adapter = ClaudeCodeAdapter()
        stdout = "Made 3 API calls"
        stderr = ""

        count = adapter._parse_api_calls(stdout, stderr)

        assert count == 3

    def test_parse_response_markers(self) -> None:
        """Test counting response markers."""
        adapter = ClaudeCodeAdapter()
        stdout = "Response: foo\nResponse: bar\nCompletion: baz"
        stderr = ""

        count = adapter._parse_api_calls(stdout, stderr)

        assert count == 3

    def test_parse_meaningful_output(self) -> None:
        """Test default count for meaningful output."""
        adapter = ClaudeCodeAdapter()
        stdout = "A" * 200  # Long output without markers
        stderr = ""

        count = adapter._parse_api_calls(stdout, stderr)

        assert count == 1

    def test_parse_empty_output(self) -> None:
        """Test zero count for empty output."""
        adapter = ClaudeCodeAdapter()
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

            adapter = ClaudeCodeAdapter()
            config = AdapterConfig(
                model="test",
                prompt_file=tmppath / "prompt.md",
                workspace=tmppath,
                output_dir=tmppath,
                env_vars={},
            )

            env = adapter._prepare_env(config)

            # Should have inherited environment
            assert "PATH" in env or len(env) > 0

    def test_prepare_env_adds_custom_vars(self) -> None:
        """Test that custom env vars are added."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            adapter = ClaudeCodeAdapter()
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

            adapter = ClaudeCodeAdapter()
            config = AdapterConfig(
                model="claude-sonnet-4-20250514",
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
            assert result.stdout == mock_result.stdout

    def test_run_with_tier_config(self) -> None:
        """Test execution with tier configuration."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            prompt_file = tmppath / "prompt.md"
            prompt_file.write_text("Test prompt")

            adapter = ClaudeCodeAdapter()
            config = AdapterConfig(
                model="claude-sonnet-4-20250514",
                prompt_file=prompt_file,
                workspace=tmppath,
                output_dir=tmppath,
            )

            tier_config = MagicMock()
            tier_config.tier_id = "T1"
            tier_config.prompt_content = "Think step by step"
            tier_config.tools_enabled = False
            tier_config.delegation_enabled = None

            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "Success"
            mock_result.stderr = ""

            with patch("subprocess.run", return_value=mock_result) as mock_run:
                result = adapter.run(config, tier_config)

            # Check that the command included the tier prompt
            call_args = mock_run.call_args
            cmd = call_args[0][0]
            assert "--no-tools" in cmd
            # Prompt should include tier content
            assert "Think step by step" in cmd[-1]

    def test_run_timeout(self) -> None:
        """Test execution timeout."""
        import subprocess

        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            prompt_file = tmppath / "prompt.md"
            prompt_file.write_text("Test prompt")

            adapter = ClaudeCodeAdapter()
            config = AdapterConfig(
                model="claude-sonnet-4-20250514",
                prompt_file=prompt_file,
                workspace=tmppath,
                output_dir=tmppath,
                timeout=30,
            )

            timeout_error = subprocess.TimeoutExpired(
                cmd=["claude"],
                timeout=30,
                output=b"partial output",
                stderr=b"partial error",
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

            adapter = ClaudeCodeAdapter()
            config = AdapterConfig(
                model="claude-sonnet-4-20250514",
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

            adapter = ClaudeCodeAdapter()
            config = AdapterConfig(
                model="claude-sonnet-4-20250514",
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

            logs_dir = tmppath / "logs"
            assert logs_dir.exists()
            assert (logs_dir / "stdout.log").read_text() == "stdout content"
            assert (logs_dir / "stderr.log").read_text() == "stderr content"

    def test_run_calculates_cost(self) -> None:
        """Test that cost is calculated correctly."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            prompt_file = tmppath / "prompt.md"
            prompt_file.write_text("Test prompt")

            adapter = ClaudeCodeAdapter()
            config = AdapterConfig(
                model="claude-sonnet-4-20250514",
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

            adapter = ClaudeCodeAdapter()
            config = AdapterConfig(
                model="test",
                prompt_file=tmppath / "nonexistent.md",
                workspace=tmppath,
                output_dir=tmppath,
            )

            with pytest.raises(Exception, match="Prompt file not found"):
                adapter.run(config)

    def test_validates_workspace(self) -> None:
        """Test that missing workspace raises error."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            prompt_file = tmppath / "prompt.md"
            prompt_file.write_text("Test")

            adapter = ClaudeCodeAdapter()
            config = AdapterConfig(
                model="test",
                prompt_file=prompt_file,
                workspace=Path("/nonexistent"),
                output_dir=tmppath,
            )

            with pytest.raises(Exception, match="Workspace directory not found"):
                adapter.run(config)
