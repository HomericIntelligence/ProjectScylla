"""Checkpoint management for E2E experiment pause/resume.

This module provides checkpoint state tracking for E2E experiments,
enabling pause/resume functionality for overnight runs with rate limit handling.

Python Justification: Required for JSON serialization and file I/O.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from scylla.e2e.models import ExperimentConfig


class CheckpointError(Exception):
    """Base exception for checkpoint-related errors."""

    pass


class ConfigMismatchError(CheckpointError):
    """Raised when checkpoint config doesn't match current config."""

    pass


@dataclass
class E2ECheckpoint:
    """Checkpoint state for E2E experiment resume capability.

    Stored at: results/{experiment}/checkpoint.json

    Enables run-level resume: after each run completes, checkpoint is updated.
    On resume, completed runs are skipped.

    Attributes:
        version: Checkpoint format version
        experiment_id: Unique experiment identifier
        experiment_dir: Absolute path to experiment directory
        config_hash: SHA256 hash of config for strict validation
        completed_runs: tier_id -> subtest_id -> {run_number: status}
                       status can be: "passed", "failed", "agent_complete"
        started_at: ISO timestamp of experiment start
        last_updated_at: ISO timestamp of last checkpoint update
        status: Current status (running, paused_rate_limit, completed, failed)
        rate_limit_source: Source of rate limit (agent or judge)
        rate_limit_until: ISO timestamp when rate limit expires
        pause_count: Number of times paused for rate limits
        pid: Process ID of running experiment

    """

    version: str = "2.0"  # Bumped for schema change
    experiment_id: str = ""
    experiment_dir: str = ""
    config_hash: str = ""

    # Progress tracking: tier_id -> subtest_id -> {run_number: status}
    # status: "passed", "failed", "agent_complete"
    completed_runs: dict[str, dict[str, dict[int, str]]] = field(default_factory=dict)

    # Timing
    started_at: str = ""
    last_updated_at: str = ""

    # Rate limit state
    status: str = "running"  # running, paused_rate_limit, completed, failed
    rate_limit_source: str | None = None  # agent or judge
    rate_limit_until: str | None = None  # ISO timestamp
    pause_count: int = 0

    # Process info for monitoring
    pid: int | None = None

    def mark_run_completed(
        self, tier_id: str, subtest_id: str, run_number: int, status: str = "passed"
    ) -> None:
        """Mark a run as completed in the checkpoint with status.

        Args:
            tier_id: Tier identifier (e.g., "T0", "T1")
            subtest_id: Subtest identifier (e.g., "00-empty")
            run_number: Run number (1-based)
            status: Run status - "passed", "failed", or "agent_complete"

        """
        if status not in ("passed", "failed", "agent_complete"):
            raise ValueError(
                f"Invalid status: {status}. Must be 'passed', 'failed', or 'agent_complete'."
            )

        if tier_id not in self.completed_runs:
            self.completed_runs[tier_id] = {}
        if subtest_id not in self.completed_runs[tier_id]:
            self.completed_runs[tier_id][subtest_id] = {}

        self.completed_runs[tier_id][subtest_id][run_number] = status
        self.last_updated_at = datetime.now(timezone.utc).isoformat()

    def unmark_run_completed(self, tier_id: str, subtest_id: str, run_number: int) -> None:
        """Remove a run from completed runs (for re-running invalid runs).

        Args:
            tier_id: Tier identifier (e.g., "T0", "T1")
            subtest_id: Subtest identifier (e.g., "00-empty")
            run_number: Run number (1-based)

        """
        if tier_id in self.completed_runs:
            if subtest_id in self.completed_runs[tier_id]:
                if run_number in self.completed_runs[tier_id][subtest_id]:
                    del self.completed_runs[tier_id][subtest_id][run_number]
                    self.last_updated_at = datetime.now(timezone.utc).isoformat()

    def get_run_status(self, tier_id: str, subtest_id: str, run_number: int) -> str | None:
        """Get the status of a run.

        Args:
            tier_id: Tier identifier
            subtest_id: Subtest identifier
            run_number: Run number (1-based)

        Returns:
            Run status ("passed", "failed", "agent_complete") or None if not found

        """
        if tier_id in self.completed_runs:
            if subtest_id in self.completed_runs[tier_id]:
                return self.completed_runs[tier_id][subtest_id].get(run_number)
        return None

    def is_run_completed(self, tier_id: str, subtest_id: str, run_number: int) -> bool:
        """Check if a run has been fully completed (passed or failed).

        Args:
            tier_id: Tier identifier
            subtest_id: Subtest identifier
            run_number: Run number (1-based)

        Returns:
            True if run status is "passed" or "failed", False otherwise

        """
        status = self.get_run_status(tier_id, subtest_id, run_number)
        return status in ("passed", "failed")

    def get_completed_run_count(self) -> int:
        """Get total number of completed runs across all tiers/subtests.

        Returns:
            Total count of completed runs

        """
        total = 0
        for tier_runs in self.completed_runs.values():
            for subtest_runs in tier_runs.values():
                total += len(subtest_runs)
        return total

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dictionary representation of checkpoint

        """
        return {
            "version": self.version,
            "experiment_id": self.experiment_id,
            "experiment_dir": self.experiment_dir,
            "config_hash": self.config_hash,
            "completed_runs": self.completed_runs,
            "started_at": self.started_at,
            "last_updated_at": self.last_updated_at,
            "status": self.status,
            "rate_limit_source": self.rate_limit_source,
            "rate_limit_until": self.rate_limit_until,
            "pause_count": self.pause_count,
            "pid": self.pid,
        }

    @classmethod
    def _convert_completed_runs_keys(
        cls, raw: dict[str, dict[str, dict[str, str]]]
    ) -> dict[str, dict[str, dict[int, str]]]:
        """Convert completed_runs run_number keys from JSON strings to int.

        JSON serialization converts Python int dict keys to strings.
        When loading from disk, we must convert them back to int for
        correct lookups via get_run_status() and is_run_completed().

        Args:
            raw: completed_runs dict with string keys (from JSON)

        Returns:
            completed_runs dict with int keys (Python native)

        """
        result: dict[str, dict[str, dict[int, str]]] = {}
        for tier_id, subtests in raw.items():
            result[tier_id] = {}
            for subtest_id, runs in subtests.items():
                result[tier_id][subtest_id] = {int(k): v for k, v in runs.items()}
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> E2ECheckpoint:
        """Create from dictionary.

        Args:
            data: Dictionary representation

        Returns:
            E2ECheckpoint instance

        Raises:
            CheckpointError: If checkpoint version is incompatible

        """
        version = data.get("version", "1.0")

        # Version 2.0+ uses dict[int, str] for completed_runs, v1.0 used list[int]
        # No backward compatibility - old checkpoints must be discarded
        if version != "2.0":
            raise CheckpointError(
                f"Incompatible checkpoint version {version}. "
                "This version requires checkpoint format 2.0. "
                "Please delete the old checkpoint and re-run the experiment."
            )

        return cls(
            version=version,
            experiment_id=data.get("experiment_id", ""),
            experiment_dir=data.get("experiment_dir", ""),
            config_hash=data.get("config_hash", ""),
            completed_runs=cls._convert_completed_runs_keys(data.get("completed_runs", {})),
            started_at=data.get("started_at", ""),
            last_updated_at=data.get("last_updated_at", ""),
            status=data.get("status", "running"),
            rate_limit_source=data.get("rate_limit_source"),
            rate_limit_until=data.get("rate_limit_until"),
            pause_count=data.get("pause_count", 0),
            pid=data.get("pid"),
        )


def save_checkpoint(checkpoint: E2ECheckpoint, path: Path) -> None:
    """Save checkpoint to file with atomic write.

    Uses temporary file + rename for atomic write to prevent
    corruption from interrupted writes.

    Args:
        checkpoint: Checkpoint to save
        path: Path to checkpoint file

    Raises:
        CheckpointError: If save fails

    """
    try:
        # Update timestamp
        checkpoint.last_updated_at = datetime.now(timezone.utc).isoformat()

        # Atomic write: write to temp file, then rename
        # Use process ID to avoid race conditions in parallel execution
        temp_path = path.parent / f"{path.stem}.tmp.{os.getpid()}{path.suffix}"
        with open(temp_path, "w") as f:
            json.dump(checkpoint.to_dict(), f, indent=2)

        # Atomic rename
        temp_path.replace(path)

    except OSError as e:
        raise CheckpointError(f"Failed to save checkpoint to {path}: {e}")


def load_checkpoint(path: Path) -> E2ECheckpoint:
    """Load checkpoint from file.

    Args:
        path: Path to checkpoint file

    Returns:
        Loaded E2ECheckpoint

    Raises:
        CheckpointError: If load fails or file doesn't exist

    """
    if not path.exists():
        raise CheckpointError(f"Checkpoint file not found: {path}")

    try:
        with open(path) as f:
            data = json.load(f)
        return E2ECheckpoint.from_dict(data)
    except (OSError, json.JSONDecodeError) as e:
        raise CheckpointError(f"Failed to load checkpoint from {path}: {e}")


def compute_config_hash(config: ExperimentConfig) -> str:
    """Compute hash of experiment config for validation.

    Includes all fields that affect experiment execution.
    Excludes fields that don't affect results (parallel_subtests, max_subtests).

    Args:
        config: Experiment configuration

    Returns:
        16-character hex hash (first 16 chars of SHA256)

    """
    config_dict = config.to_dict()

    # Remove fields that don't affect results
    config_dict.pop("parallel_subtests", None)  # Just parallelization setting
    config_dict.pop("max_subtests", None)  # Development/testing only

    # Stable JSON serialization (sorted keys)
    config_json = json.dumps(config_dict, sort_keys=True)
    return hashlib.sha256(config_json.encode()).hexdigest()[:16]


def validate_checkpoint_config(checkpoint: E2ECheckpoint, config: ExperimentConfig) -> bool:
    """Validate that checkpoint config matches current config.

    Requirement: Strict match - config must be identical to resume.

    Args:
        checkpoint: Loaded checkpoint
        config: Current experiment configuration

    Returns:
        True if configs match, False otherwise

    """
    current_hash = compute_config_hash(config)
    return checkpoint.config_hash == current_hash


def get_experiment_status(experiment_dir: Path) -> dict[str, Any]:
    """Get current experiment status for monitoring.

    Checks checkpoint file and PID file to determine if experiment
    is running, paused, or completed.

    Args:
        experiment_dir: Path to experiment directory

    Returns:
        Dict with status information:
        - running: bool - whether process is active
        - status: str - status from checkpoint
        - completed_runs: int - number of completed runs
        - rate_limit_until: str | None - when rate limit expires
        - pid: int | None - process ID if running

    """
    checkpoint_path = experiment_dir / "checkpoint.json"
    pid_path = experiment_dir / "experiment.pid"

    result: dict[str, Any] = {"running": False, "status": "unknown"}

    # Load checkpoint if exists
    if checkpoint_path.exists():
        try:
            checkpoint = load_checkpoint(checkpoint_path)
            result["status"] = checkpoint.status
            result["completed_runs"] = checkpoint.get_completed_run_count()
            if checkpoint.rate_limit_until:
                result["rate_limit_until"] = checkpoint.rate_limit_until
        except CheckpointError:
            pass

    # Check if process is running
    if pid_path.exists():
        try:
            pid = int(pid_path.read_text().strip())
            # Check if process exists
            os.kill(pid, 0)  # Signal 0 doesn't kill, just checks existence
            result["running"] = True
            result["pid"] = pid
        except (OSError, ValueError):
            # Process doesn't exist or PID file is invalid
            result["running"] = False
            result["pid"] = None

    return result
