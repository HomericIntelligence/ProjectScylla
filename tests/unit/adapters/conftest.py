"""Shared test fixtures for adapter tests."""

from collections.abc import Generator
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock

import pytest

from scylla.adapters.base import AdapterConfig


@pytest.fixture
def temp_workspace() -> Generator[Path, None, None]:
    """Create temporary workspace directory."""
    with TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def prompt_file(temp_workspace: Path) -> Path:
    """Create test prompt file."""
    prompt_file = temp_workspace / "prompt.md"
    prompt_file.write_text("Test prompt")
    return prompt_file


@pytest.fixture
def adapter_config(temp_workspace: Path, prompt_file: Path) -> AdapterConfig:
    """Create standard adapter configuration."""
    return AdapterConfig(
        model="gpt-4",
        prompt_file=prompt_file,
        workspace=temp_workspace,
        output_dir=temp_workspace,
    )


@pytest.fixture
def tier_config_tools_disabled() -> MagicMock:
    """Create tier config with tools disabled."""
    tier_config = MagicMock()
    tier_config.tools_enabled = False
    tier_config.delegation_enabled = None
    return tier_config


@pytest.fixture
def tier_config_tools_enabled() -> MagicMock:
    """Create tier config with tools enabled."""
    tier_config = MagicMock()
    tier_config.tools_enabled = True
    tier_config.delegation_enabled = None
    return tier_config


@pytest.fixture
def mock_subprocess_result() -> MagicMock:
    """Create mock subprocess result."""
    result = MagicMock()
    result.returncode = 0
    result.stdout = "Success output"
    result.stderr = ""
    return result


@pytest.fixture
def mock_subprocess_result_with_tokens() -> MagicMock:
    """Create mock subprocess result with token information."""
    result = MagicMock()
    result.returncode = 0
    result.stdout = "API calls: 2\nInput tokens: 100\nOutput tokens: 200"
    result.stderr = ""
    return result
