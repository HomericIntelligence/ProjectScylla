"""Unit tests for subtest executor functions."""

from __future__ import annotations

from pathlib import Path

import pytest

from scylla.e2e.subtest_executor import _move_to_failed


class TestMoveToFailed:
    """Tests for _move_to_failed function."""

    def test_move_creates_failed_dir(self, tmp_path: Path) -> None:
        """Test that .failed/ directory is created."""
        run_dir = tmp_path / "subtest" / "run_01"
        run_dir.mkdir(parents=True)
        (run_dir / "output.txt").write_text("test output")

        new_path = _move_to_failed(run_dir)

        assert (tmp_path / "subtest" / ".failed").exists()
        assert new_path.name == "run_01_attempt_01"
        assert not run_dir.exists()
        assert (new_path / "output.txt").exists()

    def test_move_increments_attempt(self, tmp_path: Path) -> None:
        """Test that attempt number increments."""
        subtest_dir = tmp_path / "subtest"
        failed_dir = subtest_dir / ".failed"
        failed_dir.mkdir(parents=True)
        (failed_dir / "run_01_attempt_01").mkdir()

        run_dir = subtest_dir / "run_01"
        run_dir.mkdir()

        new_path = _move_to_failed(run_dir)

        assert new_path.name == "run_01_attempt_02"

    def test_move_preserves_contents(self, tmp_path: Path) -> None:
        """Test that all contents are preserved during move."""
        run_dir = tmp_path / "subtest" / "run_03"
        run_dir.mkdir(parents=True)
        (run_dir / "output.txt").write_text("agent output")
        (run_dir / "stderr.log").write_text("error log")
        (run_dir / "run_result.json").write_text('{"exit_code": -1}')

        new_path = _move_to_failed(run_dir)

        assert (new_path / "output.txt").read_text() == "agent output"
        assert (new_path / "stderr.log").read_text() == "error log"
        assert (new_path / "run_result.json").read_text() == '{"exit_code": -1}'

    def test_move_with_custom_attempt(self, tmp_path: Path) -> None:
        """Test move with custom attempt number."""
        run_dir = tmp_path / "subtest" / "run_01"
        run_dir.mkdir(parents=True)

        new_path = _move_to_failed(run_dir, attempt=5)

        assert new_path.name == "run_01_attempt_05"

    def test_move_multiple_increments(self, tmp_path: Path) -> None:
        """Test that multiple attempts increment correctly."""
        subtest_dir = tmp_path / "subtest"
        failed_dir = subtest_dir / ".failed"
        failed_dir.mkdir(parents=True)

        # Create attempts 01-03
        (failed_dir / "run_01_attempt_01").mkdir()
        (failed_dir / "run_01_attempt_02").mkdir()
        (failed_dir / "run_01_attempt_03").mkdir()

        run_dir = subtest_dir / "run_01"
        run_dir.mkdir()

        new_path = _move_to_failed(run_dir)

        assert new_path.name == "run_01_attempt_04"
