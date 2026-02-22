"""Data loader for experiment results.

Loads experiment data from the fullruns/ directory hierarchy and converts
to structured dataclasses for analysis.
data structures. Uses existing e2e.models data structures to avoid duplication.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jsonschema
import numpy as np
import yaml

from scylla.e2e.models import TokenStats

logger = logging.getLogger(__name__)

# Load JSON Schema for run_result.json validation
_SCHEMA_PATH = Path(__file__).parent / "schemas" / "run_result.schema.json"
with _SCHEMA_PATH.open() as _schema_file:
    _RUN_RESULT_SCHEMA = json.load(_schema_file)


def validate_numeric(value: Any, field_name: str, default: float = np.nan) -> float:
    """Validate and coerce numeric field from JSON.

    Args:
        value: Value from JSON (could be int, float, str, None, etc.)
        field_name: Field name for error messages
        default: Default value if validation fails

    Returns:
        Validated float value or default

    """
    # Handle None or missing
    if value is None:
        return default

    # Try to convert to float
    try:
        result = float(value)

        # Check for invalid values
        if np.isnan(result) or np.isinf(result):
            return default

        return result
    except (ValueError, TypeError):
        logger.warning(
            "Invalid type for %s: %s (value=%r), using default=%s",
            field_name,
            type(value).__name__,
            value,
            default,
        )
        return default


def validate_bool(value: Any, field_name: str, default: bool = False) -> bool:
    """Validate and coerce boolean field from JSON.

    Args:
        value: Value from JSON (could be bool, int, str, None, etc.)
        field_name: Field name for error messages
        default: Default value if validation fails

    Returns:
        Validated bool value or default

    """
    # Handle None or missing
    if value is None:
        return default

    # If already bool, return directly
    if isinstance(value, bool):
        return value

    # Try common string representations
    if isinstance(value, str):
        value_lower = value.lower()
        if value_lower in ("true", "yes", "1"):
            return True
        if value_lower in ("false", "no", "0"):
            return False

    # Try numeric conversion (0 = False, non-zero = True)
    try:
        return bool(int(value))
    except (ValueError, TypeError):
        logger.warning(
            "Invalid type for %s: %s (value=%r), using default=%s",
            field_name,
            type(value).__name__,
            value,
            default,
        )
        return default


def validate_int(value: Any, field_name: str, default: int = -1) -> int:
    """Validate and coerce integer field from JSON.

    Args:
        value: Value from JSON (could be int, float, str, None, etc.)
        field_name: Field name for error messages
        default: Default value if validation fails

    Returns:
        Validated int value or default

    """
    # Handle None or missing
    if value is None:
        return default

    # Try to convert to int
    try:
        return int(value)
    except (ValueError, TypeError):
        logger.warning(
            "Invalid type for %s: %s (value=%r), using default=%s",
            field_name,
            type(value).__name__,
            value,
            default,
        )
        return default


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
class ModelUsage:
    """Per-model token usage from agent execution.

    Tracks individual model usage when multiple models are involved
    (relevant for T3-T5 delegation tiers).

    Attributes:
        model: Model identifier
        input_tokens: Input tokens consumed
        output_tokens: Output tokens generated
        cache_creation_tokens: Cache creation tokens
        cache_read_tokens: Cache read tokens
        cost_usd: Cost for this model's usage

    """

    model: str
    input_tokens: int
    output_tokens: int
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    cost_usd: float = 0.0


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
        api_calls: Number of API calls (optional, for delegation tiers)
        num_turns: Number of agentic turns (optional, for delegation tiers)
        model_usage: Per-model token usage (optional, for delegation tiers)

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
    # Optional agent result fields (from agent/result.json)
    api_calls: int | None = None
    num_turns: int | None = None
    model_usage: list[ModelUsage] | None = None


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
            # Use match.group(0) to avoid including trailing date suffix
            return re.sub(pattern, replacement, match.group(0))

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
            logger.warning("Failed to read %s: %s", config_path, e)

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
                        logger.warning("Failed to parse %s: %s", model_md, e)

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


def load_agent_result(run_dir: Path) -> dict[str, Any]:
    """Load agent execution result from agent/result.json.

    Args:
        run_dir: Path to the run directory

    Returns:
        Dictionary with agent result data, or empty dict if not available

    """
    agent_result_path = run_dir / "agent" / "result.json"
    if not agent_result_path.exists():
        return {}

    try:
        with agent_result_path.open() as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to load agent result %s: %s", agent_result_path, e)
        return {}


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
            achieved=criterion_data.get("achieved", np.nan),
            max_points=criterion_data.get("max", np.nan),
            score=criterion_data.get("score", np.nan),
            items=items,
        )

    # Check is_valid flag
    is_valid_raw = data.get("is_valid", True) is not False

    return JudgeEvaluation(
        judge_model=judge_model,
        judge_number=judge_number,
        score=data.get("score", np.nan),
        passed=data.get("passed", False),
        grade=data.get("grade", "F"),
        is_valid=is_valid_raw,
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

    # Validate against JSON Schema (graceful degradation - log warning only)
    try:
        jsonschema.validate(result, _RUN_RESULT_SCHEMA)
    except jsonschema.ValidationError as e:
        logger.warning(
            "Schema validation failed for %s: %s (path: %s)",
            run_result_path,
            e.message,
            " -> ".join(str(p) for p in e.path) if e.path else "root",
        )

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
        # Dynamically discover all judge directories
        for judge_path in sorted(judge_dir.glob("judge_*/judgment.json")):
            # Extract judge number from directory name (e.g., "judge_01" -> 1)
            judge_num = int(judge_path.parent.name.replace("judge_", ""))
            judges.append(load_judgment(judge_path, judge_num))

    # Load optional agent result data
    agent_data = load_agent_result(run_dir)
    api_calls_val = None
    num_turns_val = None
    model_usage_val = None

    if agent_data:
        # Extract API calls and turns if present
        if "api_calls" in agent_data:
            api_calls_val = validate_int(agent_data["api_calls"], "api_calls", 0) or None
        if "num_turns" in agent_data:
            num_turns_val = validate_int(agent_data["num_turns"], "num_turns", 0) or None

        # Parse model_usage if present (for delegation tiers)
        raw_usage = agent_data.get("model_usage") or agent_data.get("modelUsage")
        if raw_usage and isinstance(raw_usage, list):
            model_usage_val = []
            for usage in raw_usage:
                if isinstance(usage, dict):
                    model_usage_val.append(
                        ModelUsage(
                            model=usage.get("model", "unknown"),
                            input_tokens=validate_int(
                                usage.get("input_tokens") or usage.get("inputTokens"),
                                "input_tokens",
                                0,
                            ),
                            output_tokens=validate_int(
                                usage.get("output_tokens") or usage.get("outputTokens"),
                                "output_tokens",
                                0,
                            ),
                            cache_creation_tokens=validate_int(
                                usage.get("cache_creation_tokens"), "cache_creation_tokens", 0
                            ),
                            cache_read_tokens=validate_int(
                                usage.get("cache_read_tokens"), "cache_read_tokens", 0
                            ),
                            cost_usd=validate_numeric(usage.get("cost_usd"), "cost_usd", 0.0),
                        )
                    )

    # Validate and coerce all numeric/boolean fields with type checking
    return RunData(
        experiment=experiment,
        agent_model=agent_model,
        tier=tier,
        subtest=subtest,
        run_number=run_number,
        score=validate_numeric(result.get("judge_score"), "judge_score", np.nan),
        passed=validate_bool(result.get("judge_passed"), "judge_passed", False),
        grade=result.get("judge_grade", "F"),  # String, no validation needed
        cost_usd=validate_numeric(result.get("cost_usd"), "cost_usd", np.nan),
        duration_seconds=validate_numeric(
            result.get("duration_seconds"), "duration_seconds", np.nan
        ),
        agent_duration_seconds=validate_numeric(
            result.get("agent_duration_seconds"), "agent_duration_seconds", np.nan
        ),
        judge_duration_seconds=validate_numeric(
            result.get("judge_duration_seconds"), "judge_duration_seconds", np.nan
        ),
        token_stats=token_stats,
        exit_code=validate_int(result.get("exit_code"), "exit_code", -1),
        judges=judges,
        api_calls=api_calls_val,
        num_turns=num_turns_val,
        model_usage=model_usage_val,
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
                    logger.warning("Failed to load %s: %s", run_dir, e)
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
            logger.info("Skipping excluded experiment: %s", exp_name)
            continue

        logger.info("Loading experiment: %s", exp_name)

        # Resolve agent model from experiment configuration
        try:
            agent_model = resolve_agent_model(actual_exp_dir)
        except ValueError as e:
            logger.warning("%s, skipping experiment", e)
            continue

        runs = load_experiment(actual_exp_dir, agent_model)
        experiments[exp_name] = runs
        logger.info("  Loaded %d runs (agent model: %s)", len(runs), agent_model)

    return experiments


def load_rubric_weights(
    data_dir: Path, exclude: list[str] | None = None
) -> dict[str, float] | None:
    """Load category weights from the first experiment's rubric.yaml.

    Scans experiment directories for rubric.yaml and parses categories.*.weight.
    Returns None if no rubric found.

    Args:
        data_dir: Root fullruns directory
        exclude: List of experiment names to exclude

    Returns:
        Dictionary mapping category names to weights, or None if no rubric found

    """
    exclude = exclude or []

    for exp_dir in sorted(data_dir.iterdir()):
        if not exp_dir.is_dir() or exp_dir.name in exclude:
            continue

        # Find the timestamp directory
        for ts_dir in sorted(exp_dir.iterdir()):
            if not ts_dir.is_dir():
                continue

            rubric_path = ts_dir / "rubric.yaml"
            if rubric_path.exists():
                with rubric_path.open() as f:
                    data = yaml.safe_load(f)

                categories = data.get("categories", {})
                return {name: cat.get("weight", 0.0) for name, cat in categories.items()}

    return None
