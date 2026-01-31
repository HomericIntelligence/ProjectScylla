"""Data loader for experiment results.

Loads experiment data from the fullruns/ directory hierarchy and converts
to structured dataclasses for analysis.

Python Justification: Required for file I/O and JSON parsing with complex
data structures. Uses existing e2e.models data structures to avoid duplication.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from scylla.e2e.models import TokenStats


def model_id_to_display(model_id: str) -> str:
    """Convert model ID to display name.

    Args:
        model_id: Model identifier (e.g., "claude-sonnet-4-5-20250929")

    Returns:
        Display name (e.g., "Sonnet 4.5") or original ID if unknown

    """
    # Extract family name from model ID
    if "opus" in model_id.lower():
        return "Opus 4.5"
    elif "sonnet" in model_id.lower():
        return "Sonnet 4.5"
    elif "haiku" in model_id.lower():
        return "Haiku 4.5"
    else:
        # Unknown model - return as-is
        return model_id


@dataclass
class CriterionScore:
    """Detailed score for a single rubric criterion.

    Attributes:
        name: Criterion name (functional, code_quality, etc.)
        achieved: Points achieved
        max_points: Maximum possible points
        score: Normalized score (0.0-1.0)
        items: Individual check items within this criterion

    """

    name: str
    achieved: float
    max_points: float
    score: float
    items: dict[str, ItemScore]


@dataclass
class ItemScore:
    """Score for an individual rubric check item.

    Attributes:
        item_id: Item identifier (e.g., "F1", "Q2")
        achieved: Points achieved (or "N/A")
        max_points: Maximum possible points (or "N/A")
        reason: Judge's reasoning for the score

    """

    item_id: str
    achieved: float | str
    max_points: float | str
    reason: str


@dataclass
class JudgeEvaluation:
    """A single judge's evaluation of a run.

    Attributes:
        judge_model: Model ID of the judge (e.g., "claude-opus-4-5-20251101")
        judge_number: Judge number (1, 2, or 3)
        score: Overall score (0.0-1.0)
        passed: Whether the run passed
        grade: Letter grade (S/A/B/C/D/F)
        is_valid: Whether the judgment was valid
        reasoning: Judge's overall reasoning
        criteria: Detailed scores by criterion

    """

    judge_model: str
    judge_number: int
    score: float
    passed: bool
    grade: str
    is_valid: bool
    reasoning: str
    criteria: dict[str, CriterionScore]


@dataclass
class RunData:
    """Complete data for a single run.

    Attributes:
        experiment: Experiment identifier
        agent_model: Model used for agent (Sonnet 4.5, Haiku 4.5)
        tier: Tier ID (T0-T6)
        subtest: Subtest ID
        run_number: Run number (1-10)
        score: Consensus judge score (median of 3 judges)
        passed: Consensus pass decision (majority vote)
        grade: Consensus grade
        cost_usd: Total cost in USD
        duration_seconds: Total duration
        agent_duration_seconds: Agent execution time
        judge_duration_seconds: Judge evaluation time
        token_stats: Detailed token usage
        exit_code: Agent exit code
        judges: Per-judge evaluations

    """

    experiment: str
    agent_model: str
    tier: str
    subtest: str
    run_number: int
    score: float
    passed: bool
    grade: str
    cost_usd: float
    duration_seconds: float
    agent_duration_seconds: float
    judge_duration_seconds: float
    token_stats: TokenStats
    exit_code: int
    judges: list[JudgeEvaluation]


def model_id_to_display(model_id: str) -> str:
    """Convert model ID to display name.

    Args:
        model_id: Full model ID (e.g., "claude-sonnet-4-5-20250929")

    Returns:
        Display name (e.g., "Sonnet 4.5") or original ID if unknown

    Examples:
        >>> model_id_to_display("claude-sonnet-4-5-20250929")
        'Sonnet 4.5'
        >>> model_id_to_display("claude-haiku-4-5")
        'Haiku 4.5'
        >>> model_id_to_display("unknown-model")
        'unknown-model'

    """
    # Extract model family and version from ID
    # Pattern: claude-{family}-{major}-{minor}-{date} or claude-{family}-{major}-{minor}
    patterns = [
        (r"claude-opus-(\d+)-(\d+)", r"Opus \1.\2"),
        (r"claude-sonnet-(\d+)-(\d+)", r"Sonnet \1.\2"),
        (r"claude-haiku-(\d+)-(\d+)", r"Haiku \1.\2"),
    ]

    for pattern, replacement in patterns:
        match = re.search(pattern, model_id)
        if match:
            return re.sub(pattern, replacement, model_id)

    # Unknown model - return as-is
    return model_id


def resolve_agent_model(experiment_dir: Path) -> str:
    """Resolve agent model from experiment configuration.

    Tries (in order):
    1. config/experiment.json -> models[0]
    2. First agent/MODEL.md file found

    Args:
        experiment_dir: Path to experiment directory (timestamped)

    Returns:
        Model ID string

    Raises:
        ValueError: If model cannot be determined

    """
    # Try experiment.json first
    config_path = experiment_dir / "config" / "experiment.json"
    if config_path.exists():
        try:
            with config_path.open() as f:
                config = json.load(f)
                models = config.get("models", [])
                if models:
                    return model_id_to_display(models[0])
        except Exception as e:
            print(f"Warning: Failed to read {config_path}: {e}")

    # Fallback: find first agent/MODEL.md
    for tier_dir in sorted(experiment_dir.iterdir()):
        if not tier_dir.is_dir() or not tier_dir.name.startswith("T"):
            continue

        for subtest_dir in sorted(tier_dir.iterdir()):
            if not subtest_dir.is_dir() or not subtest_dir.name.isdigit():
                continue

            for run_dir in sorted(subtest_dir.iterdir()):
                if not run_dir.is_dir() or not run_dir.name.startswith("run_"):
                    continue

                model_md = run_dir / "agent" / "MODEL.md"
                if model_md.exists():
                    try:
                        return model_id_to_display(parse_judge_model(model_md))
                    except Exception as e:
                        print(f"Warning: Failed to parse {model_md}: {e}")

    raise ValueError(f"Could not determine agent model for {experiment_dir}")


def parse_judge_model(model_md_path: Path) -> str:
    """Parse judge model from MODEL.md file.

    Args:
        model_md_path: Path to MODEL.md file

    Returns:
        Judge model ID

    Raises:
        ValueError: If model pattern not found

    """
    content = model_md_path.read_text()
    match = re.search(r"\*\*Model\*\*:\s*(.+)", content)
    if not match:
        raise ValueError(f"Could not find model in {model_md_path}")
    return match.group(1).strip()


def load_judgment(judgment_path: Path, judge_number: int) -> JudgeEvaluation:
    """Load a single judge's evaluation.

    Args:
        judgment_path: Path to judgment.json file
        judge_number: Judge number (1, 2, or 3)

    Returns:
        Judge evaluation data

    """
    with judgment_path.open() as f:
        data = json.load(f)

    # Parse judge model from MODEL.md in same directory
    model_md_path = judgment_path.parent / "MODEL.md"
    judge_model = parse_judge_model(model_md_path)

    # Parse criteria scores (handle None case)
    criteria_scores_data = data.get("criteria_scores")
    if criteria_scores_data is None:
        criteria_scores_data = {}

    criteria = {}
    for criterion_name, criterion_data in criteria_scores_data.items():
        if criterion_data is None:
            continue

        items_data = criterion_data.get("items", {})
        if items_data is None:
            items_data = {}

        items = {}
        for item_id, item_data in items_data.items():
            if item_data is None:
                continue

            items[item_id] = ItemScore(
                item_id=item_id,
                achieved=item_data.get("achieved", "N/A"),
                max_points=item_data.get("max", "N/A"),
                reason=item_data.get("reason", ""),
            )

        criteria[criterion_name] = CriterionScore(
            name=criterion_name,
            achieved=criterion_data.get("achieved", 0.0),
            max_points=criterion_data.get("max", 0.0),
            score=criterion_data.get("score", 0.0),
            items=items,
        )

    return JudgeEvaluation(
        judge_model=judge_model,
        judge_number=judge_number,
        score=data.get("score", 0.0),
        passed=data.get("passed", False),
        grade=data.get("grade", "F"),
        is_valid=data.get("is_valid", True),
        reasoning=data.get("reasoning", ""),
        criteria=criteria,
    )


def load_run(run_dir: Path, experiment: str, tier: str, subtest: str, agent_model: str) -> RunData:
    """Load data for a single run.

    Args:
        run_dir: Path to run directory
        experiment: Experiment name
        tier: Tier ID (T0-T6)
        subtest: Subtest ID
        agent_model: Agent model display name

    Returns:
        Complete run data

    """
    # Load run_result.json for consensus data
    run_result_path = run_dir / "run_result.json"
    with run_result_path.open() as f:
        result = json.load(f)

    # Parse run number from directory name (e.g., "run_01" -> 1)
    try:
        run_number = int(run_dir.name.split("_")[1])
    except (IndexError, ValueError):
        # Fallback: try to extract any number from the directory name
        import re

        match = re.search(r"\d+", run_dir.name)
        run_number = int(match.group()) if match else 0

    # Load token stats
    token_stats = TokenStats.from_dict(result.get("token_stats", {}))

    # Load per-judge evaluations
    judges = []
    judge_dir = run_dir / "judge"
    if judge_dir.exists():
        for judge_num in [1, 2, 3]:
            judge_path = judge_dir / f"judge_0{judge_num}" / "judgment.json"
            if judge_path.exists():
                judges.append(load_judgment(judge_path, judge_num))

    return RunData(
        experiment=experiment,
        agent_model=agent_model,
        tier=tier,
        subtest=subtest,
        run_number=run_number,
        score=result.get("judge_score", 0.0),
        passed=result.get("judge_passed", False),
        grade=result.get("judge_grade", "F"),
        cost_usd=result.get("cost_usd", 0.0),
        duration_seconds=result.get("duration_seconds", 0.0),
        agent_duration_seconds=result.get("agent_duration_seconds", 0.0),
        judge_duration_seconds=result.get("judge_duration_seconds", 0.0),
        token_stats=token_stats,
        exit_code=result.get("exit_code", -1),
        judges=judges,
    )


def load_experiment(experiment_dir: Path, agent_model: str) -> list[RunData]:
    """Load all runs from an experiment.

    Args:
        experiment_dir: Path to experiment directory (contains tier dirs)
        agent_model: Agent model display name

    Returns:
        List of all run data

    Note:
        Automatically skips non-tier directories (config, judges.txt, etc.)

    """
    runs = []
    experiment_name = experiment_dir.name

    # Iterate through tier directories (T0-T6)
    for tier_dir in sorted(experiment_dir.iterdir()):
        if not tier_dir.is_dir() or not tier_dir.name.startswith("T"):
            continue

        tier_id = tier_dir.name

        # Iterate through subtest directories
        for subtest_dir in sorted(tier_dir.iterdir()):
            if not subtest_dir.is_dir() or not subtest_dir.name.isdigit():
                continue

            subtest_id = subtest_dir.name

            # Iterate through run directories
            for run_dir in sorted(subtest_dir.iterdir()):
                if not run_dir.is_dir() or not run_dir.name.startswith("run_"):
                    continue

                try:
                    run = load_run(run_dir, experiment_name, tier_id, subtest_id, agent_model)
                    runs.append(run)
                except Exception as e:
                    print(f"Warning: Failed to load {run_dir}: {e}")
                    continue

    return runs


def load_all_experiments(
    data_dir: Path, exclude: list[str] | None = None
) -> dict[str, list[RunData]]:
    """Load all experiments from a data directory.

    Args:
        data_dir: Path to fullruns directory
        exclude: List of experiment names to exclude (default: [])

    Returns:
        Dictionary mapping experiment name to list of runs

    """
    if exclude is None:
        exclude = []

    experiments = {}

    for exp_dir in sorted(data_dir.iterdir()):
        if not exp_dir.is_dir():
            continue

        # Find the timestamped subdirectory (use latest if multiple)
        timestamped_dirs = sorted([d for d in exp_dir.iterdir() if d.is_dir()])
        if not timestamped_dirs:
            continue

        # Use the latest timestamped directory (sorted alphabetically = chronologically)
        actual_exp_dir = timestamped_dirs[-1]
        exp_name = exp_dir.name

        if exp_name in exclude:
            print(f"Skipping excluded experiment: {exp_name}")
            continue

        print(f"Loading experiment: {exp_name}")

        # Resolve agent model from experiment configuration
        try:
            agent_model = resolve_agent_model(actual_exp_dir)
        except ValueError as e:
            print(f"Warning: {e}, skipping experiment")
            continue

        runs = load_experiment(actual_exp_dir, agent_model)
        experiments[exp_name] = runs
        print(f"  Loaded {len(runs)} runs (agent model: {agent_model})")

    return experiments
