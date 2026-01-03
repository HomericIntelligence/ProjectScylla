"""Data models for E2E testing framework.

This module defines the core data structures used throughout the E2E
testing pipeline, including configurations, results, and aggregations.

Python Justification: Required for dataclass support and JSON serialization.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any


class TierID(Enum):
    """Tier identifiers for the evaluation framework.

    Tiers represent increasing levels of agent capability:
    - T0: Prompts - System prompt ablation (empty → full CLAUDE.md)
    - T1: Skills - Domain expertise via installed skills
    - T2: Tooling - External tools and MCP servers
    - T3: Delegation - Flat multi-agent with specialist agents
    - T4: Hierarchy - Nested orchestration with orchestrators
    - T5: Hybrid - Best combinations and permutations
    - T6: Super - Everything enabled at maximum capability
    """

    T0 = "T0"
    T1 = "T1"
    T2 = "T2"
    T3 = "T3"
    T4 = "T4"
    T5 = "T5"
    T6 = "T6"

    @classmethod
    def from_string(cls, value: str) -> TierID:
        """Create TierID from string value."""
        return cls(value.upper())

    def __lt__(self, other: TierID) -> bool:
        """Enable sorting of tiers."""
        order = list(TierID)
        return order.index(self) < order.index(other)


@dataclass
class SubTestConfig:
    """Configuration for a single sub-test within a tier.

    Each sub-test represents a variation of the tier configuration,
    such as different levels of CLAUDE.md complexity.

    Attributes:
        id: Numeric identifier (e.g., "01", "02")
        name: Human-readable name
        description: Description of what this sub-test tests
        claude_md_path: Path to CLAUDE.md for this sub-test (legacy mode)
        claude_dir_path: Path to .claude/ directory for this sub-test (legacy mode)
        extends_previous: Whether to inherit from best previous tier
        resources: Resource specification for symlink-based fixtures.
            When specified, symlinks are created to shared/ at runtime
            instead of copying files. Format:
            {
                "skills": {"categories": ["agent", "github"], "names": ["skill-name"]},
                "agents": {"levels": [0, 1, 3], "names": ["chief-architect.md"]},
                "claude_md": {"blocks": ["B02", "B05"]}
            }
    """

    id: str
    name: str
    description: str
    claude_md_path: Path | None = None
    claude_dir_path: Path | None = None
    extends_previous: bool = True
    resources: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "claude_md_path": str(self.claude_md_path) if self.claude_md_path else None,
            "claude_dir_path": str(self.claude_dir_path) if self.claude_dir_path else None,
            "extends_previous": self.extends_previous,
            "resources": self.resources,
        }


@dataclass
class TierConfig:
    """Configuration for a tier including all sub-tests.

    Attributes:
        tier_id: The tier identifier
        subtests: List of sub-test configurations
        system_prompt_mode: How to handle system prompt ("none", "default", "custom")
        custom_system_prompt: Custom system prompt if mode is "custom"
    """

    tier_id: TierID
    subtests: list[SubTestConfig]
    system_prompt_mode: str = "default"  # "none", "default", "custom"
    custom_system_prompt: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "tier_id": self.tier_id.value,
            "subtests": [s.to_dict() for s in self.subtests],
            "system_prompt_mode": self.system_prompt_mode,
            "custom_system_prompt": self.custom_system_prompt,
        }


@dataclass
class RunResult:
    """Result from a single run of a sub-test.

    Captures all execution details, metrics, and judge evaluation
    for one run of an agent against the canonical task.

    This is the E2E testing result with detailed paths and judge fields.
    For other RunResult types, see:
    - executor/runner.py:RunResult (execution tracking with status)
    - reporting/result.py:RunResult (persistence with nested info)
    - metrics/aggregator.py:RunResult (statistical aggregation)
    - core/results.py:BaseRunResult (base type)

    Attributes:
        run_number: The run number (1-indexed)
        exit_code: Process exit code
        tokens_input: Number of input tokens
        tokens_output: Number of output tokens
        cost_usd: Total cost in USD
        duration_seconds: Execution duration
        judge_score: LLM judge's score (0.0 - 1.0)
        judge_passed: Whether the run passed
        judge_grade: Letter grade (S-F)
        judge_reasoning: Judge's reasoning text
        workspace_path: Path to preserved workspace
        logs_path: Path to execution logs
        command_log_path: Path to command log JSON
    """

    run_number: int
    exit_code: int
    tokens_input: int
    tokens_output: int
    cost_usd: float
    duration_seconds: float
    judge_score: float
    judge_passed: bool
    judge_grade: str
    judge_reasoning: str
    workspace_path: Path
    logs_path: Path
    command_log_path: Path | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "run_number": self.run_number,
            "exit_code": self.exit_code,
            "tokens_input": self.tokens_input,
            "tokens_output": self.tokens_output,
            "cost_usd": self.cost_usd,
            "duration_seconds": self.duration_seconds,
            "judge_score": self.judge_score,
            "judge_passed": self.judge_passed,
            "judge_grade": self.judge_grade,
            "judge_reasoning": self.judge_reasoning,
            "workspace_path": str(self.workspace_path),
            "logs_path": str(self.logs_path),
            "command_log_path": str(self.command_log_path) if self.command_log_path else None,
        }


@dataclass
class SubTestResult:
    """Aggregated results for a sub-test across all runs.

    Contains statistics computed from all runs of a single sub-test.

    Attributes:
        subtest_id: The sub-test identifier
        tier_id: The tier identifier
        runs: List of individual run results
        pass_rate: Fraction of runs that passed
        mean_score: Mean judge score across runs
        median_score: Median judge score
        std_dev_score: Standard deviation of scores
        mean_cost: Mean cost per run
        total_cost: Total cost across all runs
        consistency: Score consistency (1 - coefficient of variation)
        selected_as_best: Whether this sub-test was selected as best
        selection_reason: Reason for selection (if selected)
    """

    subtest_id: str
    tier_id: TierID
    runs: list[RunResult]
    pass_rate: float = 0.0
    mean_score: float = 0.0
    median_score: float = 0.0
    std_dev_score: float = 0.0
    mean_cost: float = 0.0
    total_cost: float = 0.0
    consistency: float = 0.0
    selected_as_best: bool = False
    selection_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "subtest_id": self.subtest_id,
            "tier_id": self.tier_id.value,
            "runs": [r.to_dict() for r in self.runs],
            "pass_rate": self.pass_rate,
            "mean_score": self.mean_score,
            "median_score": self.median_score,
            "std_dev_score": self.std_dev_score,
            "mean_cost": self.mean_cost,
            "total_cost": self.total_cost,
            "consistency": self.consistency,
            "selected_as_best": self.selected_as_best,
            "selection_reason": self.selection_reason,
        }


@dataclass
class TierBaseline:
    """Reference to a tier's best configuration for inheritance.

    Used to track which sub-test configuration should be inherited
    by the next tier.

    Attributes:
        tier_id: The tier this baseline is from
        subtest_id: The winning sub-test ID
        claude_md_path: Path to the CLAUDE.md to inherit (legacy mode)
        claude_dir_path: Path to the .claude/ directory to inherit (legacy mode)
        resources: Resource specification for symlink recreation.
            When specified, symlinks are recreated from this spec rather
            than copying files from paths.
    """

    tier_id: TierID
    subtest_id: str
    claude_md_path: Path | None
    claude_dir_path: Path | None
    resources: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "tier_id": self.tier_id.value,
            "subtest_id": self.subtest_id,
            "claude_md_path": str(self.claude_md_path) if self.claude_md_path else None,
            "claude_dir_path": str(self.claude_dir_path) if self.claude_dir_path else None,
            "resources": self.resources,
        }


@dataclass
class ResourceManifest:
    """Records which resources were used for a subtest run.

    Enables reproducibility without copying files. Instead of duplicating
    CLAUDE.md and .claude/ to results directories, this manifest records
    exactly what was used so runs can be reproduced by re-reading the
    fixture config.

    Attributes:
        tier_id: The tier identifier
        subtest_id: The subtest identifier
        fixture_config_path: Path to original config.yaml in fixtures/
        resources: The resolved resource specification
        composed_at: ISO timestamp when config was composed
        claude_md_hash: SHA256 of composed CLAUDE.md for verification
        inherited_from: Previous tier's resources (for inheritance chain)
    """

    tier_id: str
    subtest_id: str
    fixture_config_path: str
    resources: dict[str, Any]
    composed_at: str
    claude_md_hash: str | None = None
    inherited_from: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "tier_id": self.tier_id,
            "subtest_id": self.subtest_id,
            "fixture_config_path": self.fixture_config_path,
            "resources": self.resources,
            "composed_at": self.composed_at,
            "claude_md_hash": self.claude_md_hash,
            "inherited_from": self.inherited_from,
        }

    def save(self, path: Path) -> None:
        """Save manifest to JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: Path) -> ResourceManifest:
        """Load manifest from JSON file."""
        with open(path) as f:
            data = json.load(f)
        return cls(
            tier_id=data["tier_id"],
            subtest_id=data["subtest_id"],
            fixture_config_path=data["fixture_config_path"],
            resources=data["resources"],
            composed_at=data["composed_at"],
            claude_md_hash=data.get("claude_md_hash"),
            inherited_from=data.get("inherited_from"),
        )


@dataclass
class TierResult:
    """Complete results for a tier including all sub-tests.

    Attributes:
        tier_id: The tier identifier
        subtest_results: Mapping of sub-test ID to results
        best_subtest: ID of the winning sub-test
        best_subtest_score: Score of the winning sub-test
        inherited_from: Baseline this tier inherited from
        tiebreaker_used: Whether a tie-breaker was needed
        tiebreaker_model: Model used for tie-breaking (if applicable)
        total_cost: Total cost for this tier
        total_duration: Total duration for this tier
    """

    tier_id: TierID
    subtest_results: dict[str, SubTestResult]
    best_subtest: str | None = None
    best_subtest_score: float = 0.0
    inherited_from: TierBaseline | None = None
    tiebreaker_used: bool = False
    tiebreaker_model: str | None = None
    total_cost: float = 0.0
    total_duration: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "tier_id": self.tier_id.value,
            "subtest_results": {k: v.to_dict() for k, v in self.subtest_results.items()},
            "best_subtest": self.best_subtest,
            "best_subtest_score": self.best_subtest_score,
            "inherited_from": self.inherited_from.to_dict() if self.inherited_from else None,
            "tiebreaker_used": self.tiebreaker_used,
            "tiebreaker_model": self.tiebreaker_model,
            "total_cost": self.total_cost,
            "total_duration": self.total_duration,
        }


@dataclass
class ExperimentConfig:
    """Complete experiment configuration.

    Defines all parameters for running an E2E experiment.

    Attributes:
        experiment_id: Unique identifier for this experiment
        task_repo: Git repository URL for the task
        task_commit: Git commit hash to checkout
        task_prompt_file: Path to the task prompt file
        models: List of model identifiers to test
        runs_per_subtest: Number of runs per sub-test (default: 10)
        tiers_to_run: List of tiers to evaluate
        judge_model: Model to use for judging
        tiebreaker_model: Model to use for tie-breaking
        parallel_subtests: Max parallel sub-tests (default: 4)
        timeout_seconds: Timeout per run in seconds
        max_turns: Maximum conversation turns for agent (None = unlimited)
        max_subtests: Maximum sub-tests per tier for testing (None = all)
    """

    experiment_id: str
    task_repo: str
    task_commit: str
    task_prompt_file: Path
    models: list[str] = field(default_factory=lambda: ["claude-sonnet-4-20250514"])
    runs_per_subtest: int = 10
    tiers_to_run: list[TierID] = field(default_factory=lambda: list(TierID))
    judge_model: str = "claude-opus-4-5-20251101"
    tiebreaker_model: str = "claude-opus-4-5-20251101"
    parallel_subtests: int = 4
    timeout_seconds: int = 3600
    max_turns: int | None = None  # Max conversation turns for agent (None = unlimited)
    max_subtests: int | None = None  # Max sub-tests per tier (None = all)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "experiment_id": self.experiment_id,
            "task_repo": self.task_repo,
            "task_commit": self.task_commit,
            "task_prompt_file": str(self.task_prompt_file),
            "models": self.models,
            "runs_per_subtest": self.runs_per_subtest,
            "tiers_to_run": [t.value for t in self.tiers_to_run],
            "judge_model": self.judge_model,
            "tiebreaker_model": self.tiebreaker_model,
            "parallel_subtests": self.parallel_subtests,
            "timeout_seconds": self.timeout_seconds,
            "max_turns": self.max_turns,
            "max_subtests": self.max_subtests,
        }

    def save(self, path: Path) -> None:
        """Save configuration to JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: Path) -> ExperimentConfig:
        """Load configuration from JSON file."""
        with open(path) as f:
            data = json.load(f)
        return cls(
            experiment_id=data["experiment_id"],
            task_repo=data["task_repo"],
            task_commit=data["task_commit"],
            task_prompt_file=Path(data["task_prompt_file"]),
            models=data.get("models", ["claude-sonnet-4-20250514"]),
            runs_per_subtest=data.get("runs_per_subtest", 10),
            tiers_to_run=[TierID.from_string(t) for t in data.get("tiers_to_run", [])],
            judge_model=data.get("judge_model", "claude-opus-4-5-20251101"),
            tiebreaker_model=data.get("tiebreaker_model", "claude-opus-4-5-20251101"),
            parallel_subtests=data.get("parallel_subtests", 4),
            timeout_seconds=data.get("timeout_seconds", 3600),
            max_turns=data.get("max_turns"),
        )


@dataclass
class ExperimentResult:
    """Complete experiment results.

    Contains all results and analysis from running the full experiment.

    Attributes:
        config: The experiment configuration
        tier_results: Mapping of tier ID to results
        best_overall_tier: Tier with best cost-of-pass
        best_overall_subtest: Sub-test with best performance
        frontier_cop: Best cost-of-pass across all tiers
        frontier_cop_tier: Tier achieving frontier cost-of-pass
        total_cost: Total experiment cost
        total_duration_seconds: Total experiment duration
        started_at: Experiment start timestamp
        completed_at: Experiment completion timestamp
    """

    config: ExperimentConfig
    tier_results: dict[TierID, TierResult]
    best_overall_tier: TierID | None = None
    best_overall_subtest: str | None = None
    frontier_cop: float = float("inf")
    frontier_cop_tier: TierID | None = None
    total_cost: float = 0.0
    total_duration_seconds: float = 0.0
    started_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    completed_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "config": self.config.to_dict(),
            "tier_results": {k.value: v.to_dict() for k, v in self.tier_results.items()},
            "best_overall_tier": self.best_overall_tier.value if self.best_overall_tier else None,
            "best_overall_subtest": self.best_overall_subtest,
            "frontier_cop": self.frontier_cop,
            "frontier_cop_tier": self.frontier_cop_tier.value if self.frontier_cop_tier else None,
            "total_cost": self.total_cost,
            "total_duration_seconds": self.total_duration_seconds,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }

    def save(self, path: Path) -> None:
        """Save results to JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
