"""Tests for scylla/e2e/agent_runner.py."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scylla.adapters.base import AdapterResult, AdapterTokenStats
from scylla.e2e.agent_runner import (
    _create_agent_model_md,
    _has_valid_agent_result,
    _load_agent_result,
    _save_agent_result,
)
from scylla.e2e.paths import AGENT_DIR, RESULT_FILE


def _make_result(
    exit_code: int = 0,
    stdout: str = "ok",
    stderr: str = "",
    input_tokens: int = 100,
    output_tokens: int = 50,
    cost_usd: float = 0.01,
    api_calls: int = 1,
) -> AdapterResult:
    """Create an AdapterResult for testing."""
    return AdapterResult(
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        token_stats=AdapterTokenStats(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        ),
        cost_usd=cost_usd,
        api_calls=api_calls,
    )


def _write_result_json(agent_dir: Path, data: dict) -> None:
    """Write result.json to agent_dir."""
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / RESULT_FILE).write_text(json.dumps(data))


class TestSaveAgentResult:
    """Tests for _save_agent_result()."""

    def test_writes_result_json(self, tmp_path: Path) -> None:
        """Result is written to agent_dir/result.json."""
        agent_dir = tmp_path / AGENT_DIR
        agent_dir.mkdir()
        result = _make_result()

        _save_agent_result(agent_dir, result)

        result_file = agent_dir / RESULT_FILE
        assert result_file.exists()

    def test_result_json_contains_required_fields(self, tmp_path: Path) -> None:
        """Saved JSON has all required fields."""
        agent_dir = tmp_path / AGENT_DIR
        agent_dir.mkdir()
        result = _make_result(exit_code=0, stdout="output", cost_usd=0.05, api_calls=3)

        _save_agent_result(agent_dir, result)

        data = json.loads((agent_dir / RESULT_FILE).read_text())
        assert data["exit_code"] == 0
        assert data["stdout"] == "output"
        assert data["cost_usd"] == 0.05
        assert data["api_calls"] == 3
        assert "token_stats" in data

    def test_token_stats_serialized(self, tmp_path: Path) -> None:
        """Token stats are serialized into result.json."""
        agent_dir = tmp_path / AGENT_DIR
        agent_dir.mkdir()
        result = _make_result(input_tokens=200, output_tokens=80)

        _save_agent_result(agent_dir, result)

        data = json.loads((agent_dir / RESULT_FILE).read_text())
        assert data["token_stats"]["input_tokens"] == 200
        assert data["token_stats"]["output_tokens"] == 80

    def test_failed_result_saved(self, tmp_path: Path) -> None:
        """Non-zero exit code result is also saved."""
        agent_dir = tmp_path / AGENT_DIR
        agent_dir.mkdir()
        result = _make_result(exit_code=1, stderr="error output")

        _save_agent_result(agent_dir, result)

        data = json.loads((agent_dir / RESULT_FILE).read_text())
        assert data["exit_code"] == 1
        assert data["stderr"] == "error output"


class TestLoadAgentResult:
    """Tests for _load_agent_result()."""

    def test_loads_result_from_json(self, tmp_path: Path) -> None:
        """Result is correctly loaded and reconstructed from JSON."""
        agent_dir = tmp_path / AGENT_DIR
        data = {
            "exit_code": 0,
            "stdout": "success output",
            "stderr": "",
            "token_stats": {
                "input_tokens": 100,
                "output_tokens": 50,
                "cache_creation_tokens": 0,
                "cache_read_tokens": 0,
            },
            "cost_usd": 0.02,
            "api_calls": 2,
        }
        _write_result_json(agent_dir, data)

        result = _load_agent_result(agent_dir)

        assert result.exit_code == 0
        assert result.stdout == "success output"
        assert result.cost_usd == 0.02
        assert result.api_calls == 2

    def test_token_stats_reconstructed(self, tmp_path: Path) -> None:
        """Token stats are reconstructed as AdapterTokenStats."""
        agent_dir = tmp_path / AGENT_DIR
        data = {
            "exit_code": 0,
            "stdout": "",
            "stderr": "",
            "token_stats": {
                "input_tokens": 150,
                "output_tokens": 75,
                "cache_creation_tokens": 10,
                "cache_read_tokens": 5,
            },
            "cost_usd": 0.0,
            "api_calls": 0,
        }
        _write_result_json(agent_dir, data)

        result = _load_agent_result(agent_dir)

        assert result.token_stats.input_tokens == 150
        assert result.token_stats.output_tokens == 75
        assert result.token_stats.cache_creation_tokens == 10
        assert result.token_stats.cache_read_tokens == 5

    def test_roundtrip_save_load(self, tmp_path: Path) -> None:
        """Save then load produces equivalent result."""
        agent_dir = tmp_path / AGENT_DIR
        agent_dir.mkdir()
        original = _make_result(
            exit_code=0,
            stdout="roundtrip",
            input_tokens=300,
            output_tokens=100,
            cost_usd=0.03,
            api_calls=5,
        )

        _save_agent_result(agent_dir, original)
        loaded = _load_agent_result(agent_dir)

        assert loaded.exit_code == original.exit_code
        assert loaded.stdout == original.stdout
        assert loaded.cost_usd == original.cost_usd
        assert loaded.api_calls == original.api_calls
        assert loaded.token_stats.input_tokens == original.token_stats.input_tokens


class TestCreateAgentModelMd:
    """Tests for _create_agent_model_md()."""

    def test_creates_model_md_file(self, tmp_path: Path) -> None:
        """MODEL.md is created in agent_dir."""
        agent_dir = tmp_path / AGENT_DIR

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="1.0.0\n")
            _create_agent_model_md(agent_dir, "claude-sonnet-4-5")

        assert (agent_dir / "MODEL.md").exists()

    def test_model_id_in_file(self, tmp_path: Path) -> None:
        """MODEL.md contains the model identifier."""
        agent_dir = tmp_path / AGENT_DIR

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="1.2.3\n")
            _create_agent_model_md(agent_dir, "claude-opus-4-5")

        content = (agent_dir / "MODEL.md").read_text()
        assert "claude-opus-4-5" in content

    def test_claude_version_captured(self, tmp_path: Path) -> None:
        """Claude Code version from subprocess is recorded."""
        agent_dir = tmp_path / AGENT_DIR

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="2.5.0\n")
            _create_agent_model_md(agent_dir, "claude-haiku-4-5")

        content = (agent_dir / "MODEL.md").read_text()
        assert "2.5.0" in content

    def test_unknown_version_when_subprocess_fails(self, tmp_path: Path) -> None:
        """VERSION shows 'unknown' if subprocess call fails."""
        agent_dir = tmp_path / AGENT_DIR

        with patch("subprocess.run", side_effect=Exception("not found")):
            _create_agent_model_md(agent_dir, "claude-haiku-4-5")

        content = (agent_dir / "MODEL.md").read_text()
        assert "unknown" in content

    def test_unknown_version_when_returncode_nonzero(self, tmp_path: Path) -> None:
        """VERSION shows 'unknown' if subprocess returns non-zero exit code."""
        agent_dir = tmp_path / AGENT_DIR

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="")
            _create_agent_model_md(agent_dir, "claude-sonnet-4-5")

        content = (agent_dir / "MODEL.md").read_text()
        assert "unknown" in content

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        """mkdir(parents=True) ensures nested directories are created."""
        agent_dir = tmp_path / "deep" / "nested" / AGENT_DIR

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="1.0.0\n")
            _create_agent_model_md(agent_dir, "claude-sonnet-4-5")

        assert (agent_dir / "MODEL.md").exists()


class TestHasValidAgentResult:
    """Tests for _has_valid_agent_result()."""

    def _make_agent_dir(self, run_dir: Path) -> Path:
        """Create and return the agent directory."""
        agent_dir = run_dir / AGENT_DIR
        agent_dir.mkdir(parents=True)
        return agent_dir

    def test_returns_false_when_no_result_file(self, tmp_path: Path) -> None:
        """False when result.json does not exist."""
        self._make_agent_dir(tmp_path)
        assert _has_valid_agent_result(tmp_path) is False

    def test_returns_true_for_valid_success_result(self, tmp_path: Path) -> None:
        """True for a valid successful run."""
        agent_dir = self._make_agent_dir(tmp_path)
        _write_result_json(
            agent_dir,
            {
                "exit_code": 0,
                "token_stats": {"input_tokens": 100, "output_tokens": 50},
                "cost_usd": 0.01,
            },
        )
        assert _has_valid_agent_result(tmp_path) is True

    def test_returns_false_for_malformed_json(self, tmp_path: Path) -> None:
        """False when result.json contains malformed JSON."""
        agent_dir = self._make_agent_dir(tmp_path)
        (agent_dir / RESULT_FILE).write_text("not valid json {{{")
        assert _has_valid_agent_result(tmp_path) is False

    def test_returns_false_when_required_field_missing(self, tmp_path: Path) -> None:
        """False when a required field (exit_code) is missing."""
        agent_dir = self._make_agent_dir(tmp_path)
        _write_result_json(
            agent_dir,
            {
                # missing "exit_code"
                "token_stats": {"input_tokens": 100},
                "cost_usd": 0.01,
            },
        )
        assert _has_valid_agent_result(tmp_path) is False

    def test_returns_false_for_incomplete_execution(self, tmp_path: Path) -> None:
        """False for exit_code=-1 with all-zero token stats (incomplete execution)."""
        agent_dir = self._make_agent_dir(tmp_path)
        _write_result_json(
            agent_dir,
            {
                "exit_code": -1,
                "token_stats": {
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cache_creation_tokens": 0,
                    "cache_read_tokens": 0,
                },
                "cost_usd": 0.0,
            },
        )
        assert _has_valid_agent_result(tmp_path) is False

    def test_returns_true_for_exit_minus_one_with_tokens(self, tmp_path: Path) -> None:
        """True for exit_code=-1 if token stats are non-zero (partial but valid execution)."""
        agent_dir = self._make_agent_dir(tmp_path)
        _write_result_json(
            agent_dir,
            {
                "exit_code": -1,
                "token_stats": {
                    "input_tokens": 500,
                    "output_tokens": 0,
                    "cache_creation_tokens": 0,
                    "cache_read_tokens": 0,
                },
                "cost_usd": 0.0,
            },
        )
        assert _has_valid_agent_result(tmp_path) is True

    def test_returns_true_for_nonzero_exit_code(self, tmp_path: Path) -> None:
        """True for non-zero exit code that is not -1 (agent ran but failed task)."""
        agent_dir = self._make_agent_dir(tmp_path)
        _write_result_json(
            agent_dir,
            {
                "exit_code": 1,
                "token_stats": {"input_tokens": 200, "output_tokens": 80},
                "cost_usd": 0.02,
            },
        )
        assert _has_valid_agent_result(tmp_path) is True

    @pytest.mark.parametrize(
        "missing_field",
        ["exit_code", "token_stats", "cost_usd"],
    )
    def test_returns_false_for_each_missing_required_field(
        self, tmp_path: Path, missing_field: str
    ) -> None:
        """False when any of the required fields is absent."""
        agent_dir = self._make_agent_dir(tmp_path)
        data = {
            "exit_code": 0,
            "token_stats": {"input_tokens": 10},
            "cost_usd": 0.001,
        }
        del data[missing_field]
        _write_result_json(agent_dir, data)
        assert _has_valid_agent_result(tmp_path) is False
