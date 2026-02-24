"""Tests for rerun_base.py shared infrastructure."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import pytest

from scylla.e2e.rerun_base import load_rerun_context, print_dry_run_summary


class _TestStatus(Enum):
    """Test status enum for dry-run testing."""

    COMPLETE = "complete"
    FAILED = "failed"
    MISSING = "missing"


@dataclass
class _TestRunItem:
    """Test run item for dry-run testing."""

    tier_id: str
    subtest_id: str
    run_number: int
    reason: str


@dataclass
class _TestJudgeItem:
    """Test judge item for dry-run testing."""

    tier_id: str
    subtest_id: str
    run_number: int
    judge_number: int
    judge_model: str
    reason: str


def test_load_rerun_context_success(tmp_path: Path):
    """Test successful loading of rerun context."""
    # Create experiment directory structure
    experiment_dir = tmp_path / "experiment"
    config_dir = experiment_dir / "config"
    config_dir.mkdir(parents=True)

    # Create minimal config
    config_file = config_dir / "experiment.json"
    config_file.write_text(
        """{
        "experiment_id": "test-001",
        "tiers_to_run": ["T0"],
        "runs_per_subtest": 3,
        "judge_models": ["claude-sonnet-4-5"],
        "task_repo": "test-repo",
        "task_commit": "abc123",
        "task_prompt_file": "prompt.md",
        "language": "python"
    }"""
    )

    # Create tiers directory
    tiers_dir = tmp_path / "tests" / "fixtures" / "tests" / "test-001"
    tiers_dir.mkdir(parents=True)

    # Create T0 config
    t0_dir = tiers_dir / "T0"
    t0_dir.mkdir()
    (t0_dir / "config.yaml").write_text(
        """subtests:
  - id: "00"
    name: "Test subtest"
"""
    )

    # Load context
    context = load_rerun_context(experiment_dir)

    # Verify
    assert context.experiment_dir == experiment_dir
    assert context.config.experiment_id == "test-001"
    assert context.tiers_dir == tiers_dir
    assert context.tier_manager is not None


def test_load_rerun_context_missing_config(tmp_path: Path):
    """Test error when config file is missing."""
    experiment_dir = tmp_path / "experiment"
    experiment_dir.mkdir()

    with pytest.raises(FileNotFoundError, match="Experiment config not found"):
        load_rerun_context(experiment_dir)


def test_load_rerun_context_missing_tiers_dir(tmp_path: Path, monkeypatch):
    """Test error when tiers directory cannot be found."""
    # Create experiment directory with config but no tiers
    experiment_dir = tmp_path / "experiment"
    config_dir = experiment_dir / "config"
    config_dir.mkdir(parents=True)

    config_file = config_dir / "experiment.json"
    config_file.write_text(
        """{
        "experiment_id": "test-001",
        "tiers_to_run": ["T0"],
        "runs_per_subtest": 3,
        "judge_models": ["claude-sonnet-4-5"],
        "task_repo": "test-repo",
        "task_commit": "abc123",
        "task_prompt_file": "prompt.md",
        "language": "python"
    }"""
    )

    # Mock __file__ to prevent fallback from finding real tiers directory
    fake_module_path = tmp_path / "fake_module.py"
    monkeypatch.setattr("scylla.e2e.rerun_base.__file__", str(fake_module_path))

    with pytest.raises(FileNotFoundError, match="Could not auto-detect tiers directory"):
        load_rerun_context(experiment_dir)


def test_print_dry_run_summary_runs(capsys):
    """Test dry-run summary for run items."""
    # Create test items
    failed_runs = [
        _TestRunItem("T0", "00", 1, "Agent failed"),
        _TestRunItem("T0", "00", 2, "Agent failed"),
    ]
    missing_runs = [
        _TestRunItem("T0", "01", 1, "Never started"),
    ]

    items_by_status = {
        _TestStatus.FAILED: failed_runs,
        _TestStatus.MISSING: missing_runs,
        _TestStatus.COMPLETE: [],
    }

    status_names = {
        _TestStatus.FAILED: "FAILED",
        _TestStatus.MISSING: "MISSING",
        _TestStatus.COMPLETE: "COMPLETE",
    }

    print_dry_run_summary(items_by_status, status_names)

    captured = capsys.readouterr()
    assert "DRY RUN MODE - No changes will be made" in captured.out
    assert "FAILED (2 items):" in captured.out
    assert "T0/00/run_01: Agent failed" in captured.out
    assert "T0/00/run_02: Agent failed" in captured.out
    assert "MISSING (1 items):" in captured.out
    assert "T0/01/run_01: Never started" in captured.out


def test_print_dry_run_summary_judges(capsys):
    """Test dry-run summary for judge items."""
    # Create test items
    failed_slots = [
        _TestJudgeItem("T0", "00", 1, 1, "claude-sonnet-4-5", "Judge failed"),
        _TestJudgeItem("T0", "00", 1, 2, "claude-opus-4", "Judge failed"),
    ]
    missing_slots = [
        _TestJudgeItem("T0", "00", 2, 1, "claude-sonnet-4-5", "Never ran"),
    ]

    items_by_status = {
        _TestStatus.FAILED: failed_slots,
        _TestStatus.MISSING: missing_slots,
        _TestStatus.COMPLETE: [],
    }

    status_names = {
        _TestStatus.FAILED: "FAILED",
        _TestStatus.MISSING: "MISSING",
        _TestStatus.COMPLETE: "COMPLETE",
    }

    print_dry_run_summary(items_by_status, status_names)

    captured = capsys.readouterr()
    assert "DRY RUN MODE - No changes will be made" in captured.out
    assert "FAILED (2 items):" in captured.out
    assert "T0/00/run_01 judge_01 (claude-sonnet-4-5): Judge failed" in captured.out
    assert "T0/00/run_01 judge_02 (claude-opus-4): Judge failed" in captured.out
    assert "MISSING (1 items):" in captured.out
    assert "T0/00/run_02 judge_01 (claude-sonnet-4-5): Never ran" in captured.out


def test_print_dry_run_summary_truncation(capsys):
    """Test that dry-run summary truncates long lists."""
    # Create 15 failed runs
    failed_runs = [_TestRunItem("T0", f"{i:02d}", 1, "Failed") for i in range(15)]

    items_by_status = {
        _TestStatus.FAILED: failed_runs,
    }

    status_names = {
        _TestStatus.FAILED: "FAILED",
    }

    print_dry_run_summary(items_by_status, status_names, max_preview=10)

    captured = capsys.readouterr()
    assert "FAILED (15 items):" in captured.out
    assert "... and 5 more" in captured.out


def test_print_dry_run_summary_empty(capsys):
    """Test dry-run summary with no items."""
    items_by_status: dict[_TestStatus, list[_TestRunItem]] = {
        _TestStatus.FAILED: [],
        _TestStatus.MISSING: [],
        _TestStatus.COMPLETE: [],
    }

    status_names = {
        _TestStatus.FAILED: "FAILED",
        _TestStatus.MISSING: "MISSING",
        _TestStatus.COMPLETE: "COMPLETE",
    }

    print_dry_run_summary(items_by_status, status_names)

    captured = capsys.readouterr()
    assert "DRY RUN MODE - No changes will be made" in captured.out
    # Should not show any status sections since all are empty
    assert "FAILED" not in captured.out
    assert "MISSING" not in captured.out
    assert "COMPLETE" not in captured.out
