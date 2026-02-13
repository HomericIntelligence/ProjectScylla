"""Unit tests for E2E path utilities."""

from __future__ import annotations

from pathlib import Path

from scylla.e2e.paths import (
    AGENT_DIR,
    JUDGE_DIR,
    RESULT_FILE,
    get_agent_dir,
    get_agent_result_file,
    get_judge_dir,
    get_judge_result_file,
)


class TestConstants:
    """Tests for module-level constants."""

    def test_agent_dir_constant(self) -> None:
        """Test AGENT_DIR constant value."""
        assert AGENT_DIR == "agent"

    def test_judge_dir_constant(self) -> None:
        """Test JUDGE_DIR constant value."""
        assert JUDGE_DIR == "judge"

    def test_result_file_constant(self) -> None:
        """Test RESULT_FILE constant value."""
        assert RESULT_FILE == "result.json"


class TestGetAgentDir:
    """Tests for get_agent_dir function."""

    def test_returns_agent_subdirectory(self, tmp_path: Path) -> None:
        """Test that get_agent_dir returns run_dir/agent."""
        run_dir = tmp_path / "T0" / "00" / "run_01"
        result = get_agent_dir(run_dir)

        assert result == run_dir / "agent"
        assert result.name == "agent"
        assert result.parent == run_dir

    def test_works_with_nested_paths(self, tmp_path: Path) -> None:
        """Test with deeply nested run directory."""
        run_dir = tmp_path / "experiment" / "T5" / "42" / "run_99"
        result = get_agent_dir(run_dir)

        assert result == run_dir / "agent"

    def test_preserves_absolute_path(self, tmp_path: Path) -> None:
        """Test that absolute paths remain absolute."""
        run_dir = tmp_path / "run_01"
        result = get_agent_dir(run_dir)

        assert result.is_absolute()


class TestGetJudgeDir:
    """Tests for get_judge_dir function."""

    def test_returns_judge_subdirectory(self, tmp_path: Path) -> None:
        """Test that get_judge_dir returns run_dir/judge."""
        run_dir = tmp_path / "T0" / "00" / "run_01"
        result = get_judge_dir(run_dir)

        assert result == run_dir / "judge"
        assert result.name == "judge"
        assert result.parent == run_dir

    def test_works_with_nested_paths(self, tmp_path: Path) -> None:
        """Test with deeply nested run directory."""
        run_dir = tmp_path / "experiment" / "T5" / "42" / "run_99"
        result = get_judge_dir(run_dir)

        assert result == run_dir / "judge"

    def test_preserves_absolute_path(self, tmp_path: Path) -> None:
        """Test that absolute paths remain absolute."""
        run_dir = tmp_path / "run_01"
        result = get_judge_dir(run_dir)

        assert result.is_absolute()


class TestGetAgentResultFile:
    """Tests for get_agent_result_file function."""

    def test_returns_agent_result_json_path(self, tmp_path: Path) -> None:
        """Test that get_agent_result_file returns agent/result.json."""
        run_dir = tmp_path / "T0" / "00" / "run_01"
        result = get_agent_result_file(run_dir)

        assert result == run_dir / "agent" / "result.json"
        assert result.name == "result.json"
        assert result.parent.name == "agent"

    def test_works_with_nested_paths(self, tmp_path: Path) -> None:
        """Test with deeply nested run directory."""
        run_dir = tmp_path / "experiment" / "T5" / "42" / "run_99"
        result = get_agent_result_file(run_dir)

        expected = run_dir / "agent" / "result.json"
        assert result == expected

    def test_preserves_absolute_path(self, tmp_path: Path) -> None:
        """Test that absolute paths remain absolute."""
        run_dir = tmp_path / "run_01"
        result = get_agent_result_file(run_dir)

        assert result.is_absolute()

    def test_path_components(self, tmp_path: Path) -> None:
        """Test individual path components."""
        run_dir = tmp_path / "T0" / "00" / "run_01"
        result = get_agent_result_file(run_dir)

        # Verify path structure: run_dir/agent/result.json
        parts = result.parts
        assert parts[-1] == "result.json"
        assert parts[-2] == "agent"


class TestGetJudgeResultFile:
    """Tests for get_judge_result_file function."""

    def test_returns_judge_result_json_path(self, tmp_path: Path) -> None:
        """Test that get_judge_result_file returns judge/result.json."""
        run_dir = tmp_path / "T0" / "00" / "run_01"
        result = get_judge_result_file(run_dir)

        assert result == run_dir / "judge" / "result.json"
        assert result.name == "result.json"
        assert result.parent.name == "judge"

    def test_works_with_nested_paths(self, tmp_path: Path) -> None:
        """Test with deeply nested run directory."""
        run_dir = tmp_path / "experiment" / "T5" / "42" / "run_99"
        result = get_judge_result_file(run_dir)

        expected = run_dir / "judge" / "result.json"
        assert result == expected

    def test_preserves_absolute_path(self, tmp_path: Path) -> None:
        """Test that absolute paths remain absolute."""
        run_dir = tmp_path / "run_01"
        result = get_judge_result_file(run_dir)

        assert result.is_absolute()

    def test_path_components(self, tmp_path: Path) -> None:
        """Test individual path components."""
        run_dir = tmp_path / "T0" / "00" / "run_01"
        result = get_judge_result_file(run_dir)

        # Verify path structure: run_dir/judge/result.json
        parts = result.parts
        assert parts[-1] == "result.json"
        assert parts[-2] == "judge"


class TestAgentJudgeSymmetry:
    """Tests verifying symmetry between agent and judge path functions."""

    def test_agent_and_judge_dirs_are_siblings(self, tmp_path: Path) -> None:
        """Test that agent and judge directories are siblings under run_dir."""
        run_dir = tmp_path / "T0" / "00" / "run_01"

        agent_dir = get_agent_dir(run_dir)
        judge_dir = get_judge_dir(run_dir)

        # Both should be under same parent
        assert agent_dir.parent == judge_dir.parent
        assert agent_dir.parent == run_dir

    def test_result_files_have_same_filename(self, tmp_path: Path) -> None:
        """Test that both result files use the same filename."""
        run_dir = tmp_path / "T0" / "00" / "run_01"

        agent_result = get_agent_result_file(run_dir)
        judge_result = get_judge_result_file(run_dir)

        assert agent_result.name == judge_result.name
        assert agent_result.name == "result.json"

    def test_result_files_differ_only_in_parent_directory(self, tmp_path: Path) -> None:
        """Test that result files differ only in agent vs judge directory."""
        run_dir = tmp_path / "T0" / "00" / "run_01"

        agent_result = get_agent_result_file(run_dir)
        judge_result = get_judge_result_file(run_dir)

        # Same filename
        assert agent_result.name == judge_result.name
        # Different parent directories
        assert agent_result.parent.name == "agent"
        assert judge_result.parent.name == "judge"
        # Same grandparent
        assert agent_result.parent.parent == judge_result.parent.parent
