"""Tests for base adapter class."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock

import pytest

from scylla.adapters.base import (
    AdapterConfig,
    AdapterError,
    AdapterResult,
    AdapterTokenStats,
    AdapterValidationError,
    BaseAdapter,
)


class ConcreteAdapter(BaseAdapter):
    """Concrete implementation for testing."""

    def run(self, config, tier_config=None):
        """Return success result."""
        return AdapterResult(exit_code=0, stdout="success", stderr="")


class TestAdapterResult:
    """Tests for AdapterResult model."""

    def test_default_values(self) -> None:
        """Test default values."""
        result = AdapterResult(exit_code=0)
        assert result.exit_code == 0
        assert result.stdout == ""
        assert result.stderr == ""
        assert result.tokens_input == 0
        assert result.tokens_output == 0
        assert result.cost_usd == 0.0
        assert result.timed_out is False

    def test_with_values(self) -> None:
        """Test result with all values."""
        result = AdapterResult(
            exit_code=1,
            stdout="output",
            stderr="error",
            duration_seconds=10.5,
            token_stats=AdapterTokenStats(
                input_tokens=100,
                output_tokens=50,
                cache_creation_tokens=0,
                cache_read_tokens=0,
            ),
            cost_usd=0.05,
            api_calls=3,
            timed_out=False,
            error_message="Something failed",
        )
        assert result.exit_code == 1
        assert result.tokens_input == 100  # Uses legacy property
        assert result.tokens_output == 50  # Uses legacy property
        assert result.token_stats.input_tokens == 100
        assert result.cost_usd == 0.05


class TestAdapterConfig:
    """Tests for AdapterConfig dataclass."""

    def test_basic_config(self) -> None:
        """Test creating basic config."""
        config = AdapterConfig(
            model="test-model",
            prompt_file=Path("/prompt.md"),
            workspace=Path("/workspace"),
            output_dir=Path("/output"),
        )
        assert config.model == "test-model"
        assert config.timeout == 3600  # Default
        assert config.env_vars == {}
        assert config.extra_args == []

    def test_config_with_options(self) -> None:
        """Test config with all options."""
        config = AdapterConfig(
            model="test-model",
            prompt_file=Path("/prompt.md"),
            workspace=Path("/workspace"),
            output_dir=Path("/output"),
            timeout=600,
            env_vars={"KEY": "value"},
            extra_args=["--verbose"],
        )
        assert config.timeout == 600
        assert config.env_vars == {"KEY": "value"}
        assert config.extra_args == ["--verbose"]


class TestBaseAdapter:
    """Tests for BaseAdapter class."""

    def test_get_name(self) -> None:
        """Test get_name returns class name."""
        adapter = ConcreteAdapter()
        assert adapter.get_name() == "ConcreteAdapter"

    def test_validate_config_missing_prompt(self) -> None:
        """Test validation fails for missing prompt file."""
        adapter = ConcreteAdapter()
        config = AdapterConfig(
            model="test",
            prompt_file=Path("/nonexistent.md"),
            workspace=Path("."),
            output_dir=Path("."),
        )
        with pytest.raises(AdapterValidationError, match="Prompt file not found"):
            adapter.validate_config(config)

    def test_validate_config_missing_workspace(self) -> None:
        """Test validation fails for missing workspace."""
        with TemporaryDirectory() as tmpdir:
            prompt = Path(tmpdir) / "prompt.md"
            prompt.write_text("test prompt")

            adapter = ConcreteAdapter()
            config = AdapterConfig(
                model="test",
                prompt_file=prompt,
                workspace=Path("/nonexistent"),
                output_dir=Path("."),
            )
            with pytest.raises(AdapterValidationError, match="Workspace directory not found"):
                adapter.validate_config(config)

    def test_validate_config_invalid_timeout(self) -> None:
        """Test validation fails for invalid timeout."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            prompt = tmppath / "prompt.md"
            prompt.write_text("test prompt")

            adapter = ConcreteAdapter()
            config = AdapterConfig(
                model="test",
                prompt_file=prompt,
                workspace=tmppath,
                output_dir=tmppath,
                timeout=-1,
            )
            with pytest.raises(AdapterValidationError, match="Invalid timeout"):
                adapter.validate_config(config)

    def test_validate_config_success(self) -> None:
        """Test validation succeeds for valid config."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            prompt = tmppath / "prompt.md"
            prompt.write_text("test prompt")

            adapter = ConcreteAdapter()
            config = AdapterConfig(
                model="test",
                prompt_file=prompt,
                workspace=tmppath,
                output_dir=tmppath,
            )
            # Should not raise
            adapter.validate_config(config)


class TestTierPromptInjection:
    """Tests for tier prompt injection."""

    def test_no_tier_config(self) -> None:
        """Test returns task prompt unchanged when tier_config is None."""
        adapter = ConcreteAdapter()
        result = adapter.inject_tier_prompt("Task prompt", None)
        assert result == "Task prompt"

    def test_with_tier_config_returns_unchanged(self) -> None:
        """Test returns task prompt unchanged regardless of tier config."""
        adapter = ConcreteAdapter()
        tier_config = MagicMock()
        tier_config.tier_id = "T1"

        result = adapter.inject_tier_prompt("Task prompt", tier_config)
        assert result == "Task prompt"


class TestTierSettings:
    """Tests for tier settings extraction."""

    def test_no_tier_config(self) -> None:
        """Test settings when no tier config."""
        adapter = ConcreteAdapter()
        settings = adapter.get_tier_settings(None)
        assert settings["tools_enabled"] is None
        assert settings["delegation_enabled"] is None

    def test_with_tier_config(self) -> None:
        """Test settings from tier config."""
        adapter = ConcreteAdapter()
        tier_config = MagicMock()
        tier_config.tools_enabled = True
        tier_config.delegation_enabled = False

        settings = adapter.get_tier_settings(tier_config)
        assert settings["tools_enabled"] is True
        assert settings["delegation_enabled"] is False


class TestLogWriting:
    """Tests for log writing functionality."""

    def test_write_logs_basic(self) -> None:
        """Test writing stdout and stderr logs."""
        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            adapter = ConcreteAdapter()

            adapter.write_logs(output_dir, "stdout content", "stderr content")

            # Logs are written directly to output_dir (no logs/ subdirectory)
            assert output_dir.exists()
            assert (output_dir / "stdout.log").read_text() == "stdout content"
            assert (output_dir / "stderr.log").read_text() == "stderr content"

    def test_write_logs_with_agent_log(self) -> None:
        """Test writing with agent log."""
        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            adapter = ConcreteAdapter()

            adapter.write_logs(output_dir, "stdout", "stderr", agent_log="agent activity")

            # Logs are written directly to output_dir
            assert (output_dir / "agent.log").read_text() == "agent activity"

    def test_write_logs_creates_directory(self) -> None:
        """Test that output directory is created if it doesn't exist."""
        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "new_dir"
            adapter = ConcreteAdapter()

            adapter.write_logs(output_dir, "out", "err")

            # Output directory should be created
            assert output_dir.exists()
            assert (output_dir / "stdout.log").read_text() == "out"


class TestCostCalculation:
    """Tests for cost calculation."""

    def test_calculate_cost_default(self) -> None:
        """Test cost calculation with defaults."""
        adapter = ConcreteAdapter()
        cost = adapter.calculate_cost(1000, 500)

        # Default: 0.003 per 1K input, 0.015 per 1K output
        expected = (1000 / 1000 * 0.003) + (500 / 1000 * 0.015)
        assert cost == pytest.approx(expected)

    def test_calculate_cost_claude_sonnet(self) -> None:
        """Test cost calculation for Claude Sonnet."""
        adapter = ConcreteAdapter()
        cost = adapter.calculate_cost(1000, 500, model="claude-sonnet-4-5-20250929")

        # Sonnet: 0.003 per 1K input, 0.015 per 1K output
        expected = (1000 / 1000 * 0.003) + (500 / 1000 * 0.015)
        assert cost == pytest.approx(expected)

    def test_calculate_cost_claude_opus(self) -> None:
        """Test cost calculation for Claude Opus."""
        adapter = ConcreteAdapter()
        cost = adapter.calculate_cost(1000, 500, model="claude-opus-4-5-20251101")

        # Opus 4.5: 0.005 per 1K input, 0.025 per 1K output
        expected = (1000 / 1000 * 0.005) + (500 / 1000 * 0.025)
        assert cost == pytest.approx(expected)

    def test_calculate_cost_zero_tokens(self) -> None:
        """Test cost calculation with zero tokens."""
        adapter = ConcreteAdapter()
        cost = adapter.calculate_cost(0, 0)
        assert cost == 0.0


class TestLoadPrompt:
    """Tests for prompt loading."""

    def test_load_prompt_success(self) -> None:
        """Test loading prompt from file."""
        with TemporaryDirectory() as tmpdir:
            prompt_path = Path(tmpdir) / "prompt.md"
            prompt_path.write_text("This is the task")

            adapter = ConcreteAdapter()
            content = adapter.load_prompt(prompt_path)
            assert content == "This is the task"

    def test_load_prompt_not_found(self) -> None:
        """Test loading from nonexistent file."""
        adapter = ConcreteAdapter()
        with pytest.raises(AdapterError, match="Failed to read prompt file"):
            adapter.load_prompt(Path("/nonexistent/prompt.md"))
