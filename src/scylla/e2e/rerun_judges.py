"""Re-run judges for failed, never-run, or incomplete judge evaluations.

This module scans an experiment directory and identifies individual judge slots
(judge_01, judge_02, judge_03) that need re-execution. It handles per-slot granularity:
1. Complete - judgment.json exists and is valid
2. Missing - judge_NN/ dir doesn't exist
3. Failed - judge_NN/ exists but judgment.json is invalid/missing
4. Agent failed - Agent failed, cannot judge (skip)

After re-running missing judge slots, regenerates judge/result.json consensus.

Python Justification: Required for subprocess execution, filesystem traversal,
and integration with existing Python-based evaluation infrastructure.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

from scylla.e2e.models import ExperimentConfig
from scylla.e2e.tier_manager import TierManager
from scylla.metrics.grading import assign_letter_grade

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class JudgeSlotStatus(Enum):
    """Status of a single judge slot (judge_01, judge_02, etc.)."""

    COMPLETE = "complete"  # judgment.json exists and is valid
    MISSING = "missing"  # judge_NN/ dir doesn't exist
    FAILED = "failed"  # judge_NN/ exists but judgment.json is invalid/missing
    AGENT_FAILED = "agent_failed"  # Agent failed, cannot judge


@dataclass
class RerunJudgeStats:
    """Statistics from judge rerun process."""

    total_expected_slots: int = 0  # Total judge slots expected (runs x judges)
    per_slot_stats: dict[int, dict[str, int]] = None  # Stats per judge slot number

    # Overall stats
    complete: int = 0
    missing: int = 0
    failed: int = 0
    agent_failed: int = 0
    slots_rerun_success: int = 0
    slots_rerun_failed: int = 0
    consensus_regenerated: int = 0  # Number of run_dirs where consensus was regenerated
    runs_skipped_by_filter: int = 0

    def __post_init__(self):
        """Initialize per_slot_stats if not provided."""
        if self.per_slot_stats is None:
            self.per_slot_stats = {}

    def print_summary(self, judge_models: list[str]) -> None:
        """Print a summary of rerun statistics."""
        print("\n" + "=" * 70)
        print("JUDGE SLOT CLASSIFICATION")
        print("=" * 70)
        print(f"Total expected judge slots: {self.total_expected_slots}")
        print()
        print("  Per-slot breakdown:")

        for judge_num in sorted(self.per_slot_stats.keys()):
            stats = self.per_slot_stats[judge_num]
            model = judge_models[judge_num - 1] if judge_num <= len(judge_models) else "unknown"
            print(f"    judge_{judge_num:02d} ({model}):")
            print(
                f"      ✓ complete: {stats.get('complete', 0):4d}    "
                f"○ missing: {stats.get('missing', 0):4d}     "
                f"✗ failed: {stats.get('failed', 0):4d}"
            )

        print()
        print("RERUN RESULTS")
        print("=" * 70)
        print(f"Judge slots rerun successfully:  {self.slots_rerun_success}")
        print(f"Judge slots failed to rerun:     {self.slots_rerun_failed}")
        print(f"Consensus regenerated (runs):    {self.consensus_regenerated}")
        print("=" * 70)


@dataclass
class JudgeSlotToRerun:
    """A single judge slot that needs re-running."""

    tier_id: str  # e.g., "T0"
    subtest_id: str  # e.g., "00"
    run_number: int  # 1-based
    run_dir: Path  # Full path to run_NN/ directory
    judge_number: int  # 1, 2, or 3
    judge_model: str  # Model to use for this slot
    status: JudgeSlotStatus  # Current status
    reason: str  # Human-readable description


def _has_valid_agent_result(run_dir: Path) -> bool:
    """Check if run has a valid agent result.

    Args:
        run_dir: Path to run directory

    Returns:
        True if agent result exists and is valid

    """
    agent_dir = run_dir / "agent"
    agent_output = agent_dir / "output.txt"
    agent_result = agent_dir / "result.json"

    return agent_output.exists() and agent_output.stat().st_size > 0 and agent_result.exists()


def _is_valid_judgment(judgment_file: Path) -> bool:
    """Check if judgment.json is valid.

    Args:
        judgment_file: Path to judgment.json

    Returns:
        True if judgment file exists and is valid JSON with required fields

    """
    if not judgment_file.exists():
        return False

    try:
        with open(judgment_file) as f:
            data = json.load(f)
            # Must have at least score field
            return "score" in data
    except (json.JSONDecodeError, OSError):
        return False


def _classify_judge_slots(
    run_dir: Path,
    judge_models: list[str],
) -> list[tuple[int, str, JudgeSlotStatus]]:
    """Classify each judge slot (judge_01, judge_02, etc.) individually.

    Args:
        run_dir: Path to run directory
        judge_models: List of judge models (used to map judge_num -> model)

    Returns:
        List of (judge_number, judge_model, status) tuples

    """
    # First check agent validity
    if not _has_valid_agent_result(run_dir):
        return [(i + 1, m, JudgeSlotStatus.AGENT_FAILED) for i, m in enumerate(judge_models)]

    results = []
    for judge_num, model in enumerate(judge_models, start=1):
        judge_slot_dir = run_dir / "judge" / f"judge_{judge_num:02d}"
        judgment_file = judge_slot_dir / "judgment.json"

        if not judge_slot_dir.exists():
            results.append((judge_num, model, JudgeSlotStatus.MISSING))
        elif not judgment_file.exists():
            results.append((judge_num, model, JudgeSlotStatus.FAILED))
        elif _is_valid_judgment(judgment_file):
            results.append((judge_num, model, JudgeSlotStatus.COMPLETE))
        else:
            results.append((judge_num, model, JudgeSlotStatus.FAILED))

    return results


def scan_judges_needing_rerun(
    experiment_dir: Path,
    config: ExperimentConfig,
    tier_manager: TierManager,
    tier_filter: list[str] | None = None,
    subtest_filter: list[str] | None = None,
    run_filter: list[int] | None = None,
    judge_slot_filter: list[int] | None = None,
    status_filter: list[JudgeSlotStatus] | None = None,
    stats: RerunJudgeStats | None = None,
) -> dict[JudgeSlotStatus, list[JudgeSlotToRerun]]:
    """Scan experiment directory and classify judge slots by status.

    Args:
        experiment_dir: Path to experiment directory
        config: Experiment configuration
        tier_manager: TierManager instance
        tier_filter: Only process these tiers (e.g., ["T0", "T1"])
        subtest_filter: Only process these subtests (e.g., ["00", "01"])
        run_filter: Only process these run numbers (e.g., [1, 3, 5])
        judge_slot_filter: Only process these judge slots (e.g., [1, 3])
        status_filter: Only include judge slots with these statuses
        stats: RerunJudgeStats instance to update (optional)

    Returns:
        Dictionary mapping JudgeSlotStatus to list of JudgeSlotToRerun instances

    """
    if stats is None:
        stats = RerunJudgeStats()

    slots_by_status: dict[JudgeSlotStatus, list[JudgeSlotToRerun]] = {
        status: [] for status in JudgeSlotStatus
    }

    # Iterate over all tiers to run
    for tier_id in config.tiers_to_run:
        tier_str = tier_id.value

        # Apply tier filter
        if tier_filter and tier_str not in tier_filter:
            continue

        # Load tier config to get subtests
        tier_config = tier_manager.load_tier_config(tier_id)

        # Limit subtests if max_subtests is set
        subtests = tier_config.subtests
        if config.max_subtests is not None:
            subtests = subtests[: config.max_subtests]

        # Iterate over all subtests
        for subtest in subtests:
            subtest_id = subtest.id

            # Apply subtest filter
            if subtest_filter and subtest_id not in subtest_filter:
                continue

            subtest_dir = experiment_dir / tier_str / subtest_id

            # Iterate over all expected runs
            for run_number in range(1, config.runs_per_subtest + 1):
                # Apply run filter
                if run_filter and run_number not in run_filter:
                    stats.runs_skipped_by_filter += 1
                    continue

                run_dir = subtest_dir / f"run_{run_number:02d}"

                # Classify each judge slot
                slot_statuses = _classify_judge_slots(run_dir, config.judge_models)

                for judge_num, judge_model, status in slot_statuses:
                    # Apply judge slot filter
                    if judge_slot_filter and judge_num not in judge_slot_filter:
                        continue

                    # Update stats
                    stats.total_expected_slots += 1

                    # Update per-slot stats
                    if judge_num not in stats.per_slot_stats:
                        stats.per_slot_stats[judge_num] = {
                            "complete": 0,
                            "missing": 0,
                            "failed": 0,
                            "agent_failed": 0,
                        }

                    if status == JudgeSlotStatus.COMPLETE:
                        stats.complete += 1
                        stats.per_slot_stats[judge_num]["complete"] += 1
                    elif status == JudgeSlotStatus.MISSING:
                        stats.missing += 1
                        stats.per_slot_stats[judge_num]["missing"] += 1
                    elif status == JudgeSlotStatus.FAILED:
                        stats.failed += 1
                        stats.per_slot_stats[judge_num]["failed"] += 1
                    elif status == JudgeSlotStatus.AGENT_FAILED:
                        stats.agent_failed += 1
                        stats.per_slot_stats[judge_num]["agent_failed"] += 1

                    # Apply status filter
                    if status_filter and status not in status_filter:
                        continue

                    # Create human-readable reason
                    reason_map = {
                        JudgeSlotStatus.COMPLETE: (
                            f"Judge {judge_num} complete (no action needed)"
                        ),
                        JudgeSlotStatus.MISSING: (
                            f"Judge {judge_num} never ran " f"(judge_{judge_num:02d}/ missing)"
                        ),
                        JudgeSlotStatus.FAILED: (
                            f"Judge {judge_num} ran but failed " "(no valid judgment.json)"
                        ),
                        JudgeSlotStatus.AGENT_FAILED: "Agent failed, cannot judge",
                    }

                    slots_by_status[status].append(
                        JudgeSlotToRerun(
                            tier_id=tier_str,
                            subtest_id=subtest_id,
                            run_number=run_number,
                            run_dir=run_dir,
                            judge_number=judge_num,
                            judge_model=judge_model,
                            status=status,
                            reason=reason_map[status],
                        )
                    )

    return slots_by_status


def _rerun_single_judge_slot(
    slot: JudgeSlotToRerun, experiment_dir: Path, config: ExperimentConfig
) -> bool:
    """Re-run a single judge slot.

    Args:
        slot: JudgeSlotToRerun instance
        experiment_dir: Path to experiment directory
        config: Experiment configuration

    Returns:
        True if judge slot was successfully re-run

    """
    from scylla.e2e.llm_judge import run_llm_judge

    run_dir = slot.run_dir
    judge_dir = run_dir / "judge"
    judge_dir.mkdir(exist_ok=True)

    # Load agent output
    agent_output_file = run_dir / "agent" / "output.txt"
    if not agent_output_file.exists():
        logger.error(f"Agent output not found: {agent_output_file}")
        return False

    agent_output = agent_output_file.read_text()

    # Load task prompt
    task_prompt_file = experiment_dir / "prompt.md"
    if not task_prompt_file.exists():
        logger.error(f"Task prompt not found: {task_prompt_file}")
        return False

    task_prompt = task_prompt_file.read_text()

    # Find rubric
    rubric_path = experiment_dir / "rubric.yaml"
    if not rubric_path.exists():
        rubric_path = None

    workspace = run_dir / "workspace"

    logger.info(
        f"Re-running judge slot {slot.judge_number} for "
        f"{slot.tier_id}/{slot.subtest_id}/run_{slot.run_number:02d} "
        f"with model {slot.judge_model}"
    )

    # Run judge for this specific slot
    try:
        judge_result = run_llm_judge(
            workspace=workspace,
            task_prompt=task_prompt,
            agent_output=agent_output,
            model=slot.judge_model,
            judge_dir=judge_dir,
            judge_run_number=slot.judge_number,
            language=config.language,
            rubric_path=rubric_path,
        )

        return judge_result.is_valid

    except Exception as e:
        logger.error(
            f"Failed to re-run judge slot {slot.judge_number} for "
            f"{slot.tier_id}/{slot.subtest_id}/run_{slot.run_number:02d}: {e}"
        )
        return False


def _regenerate_consensus(run_dir: Path, judge_models: list[str]) -> bool:
    """Regenerate judge/result.json consensus from per-judge judgment files.

    Also updates run_result.json with the new consensus scores.

    Args:
        run_dir: Path to run directory
        judge_models: List of judge models (for metadata)

    Returns:
        True if consensus was successfully regenerated

    """
    # Load all judgment.json files
    judges = []
    for judge_num, model in enumerate(judge_models, start=1):
        judgment_file = run_dir / "judge" / f"judge_{judge_num:02d}" / "judgment.json"
        if judgment_file.exists() and _is_valid_judgment(judgment_file):
            try:
                data = json.loads(judgment_file.read_text())
                judges.append(
                    {
                        "model": model,
                        "score": data.get("score"),
                        "passed": data.get("passed"),
                        "grade": data.get("grade"),
                        "reasoning": data.get("reasoning", ""),
                        "judge_number": judge_num,
                    }
                )
            except Exception as e:
                logger.warning(f"Failed to load judgment from {judgment_file}: {e}")

    if not judges:
        logger.warning(f"No valid judge results found for {run_dir}, skipping consensus")
        return False

    # Compute consensus (same logic as subtest_executor._compute_judge_consensus)
    valid = [j for j in judges if j["score"] is not None]
    if not valid:
        logger.warning(f"No valid scores for {run_dir}, skipping consensus")
        return False

    consensus_score = sum(j["score"] for j in valid) / len(valid)
    passed_votes = sum(1 for j in valid if j.get("passed", False))
    passed = passed_votes > len(valid) / 2
    grade = assign_letter_grade(consensus_score)

    # Save judge/result.json
    result_data = {
        "score": consensus_score,
        "passed": passed,
        "grade": grade,
        "reasoning": valid[0]["reasoning"] if valid else "",
    }

    judge_result_file = run_dir / "judge" / "result.json"
    try:
        with open(judge_result_file, "w") as f:
            json.dump(result_data, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to write judge/result.json for {run_dir}: {e}")
        return False

    # Update run_result.json judge fields
    run_result_file = run_dir / "run_result.json"
    if run_result_file.exists():
        try:
            run_data = json.loads(run_result_file.read_text())
            run_data["judge_score"] = consensus_score
            run_data["judge_passed"] = passed
            run_data["judge_grade"] = grade
            run_data["judge_reasoning"] = valid[0]["reasoning"] if valid else ""
            with open(run_result_file, "w") as f:
                json.dump(run_data, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to update run_result.json for {run_dir}: {e}")

    logger.info(
        f"Regenerated consensus for {run_dir.name}: "
        f"score={consensus_score:.2f}, passed={passed}, grade={grade}"
    )
    return True


def rerun_judges_experiment(
    experiment_dir: Path,
    dry_run: bool = False,
    verbose: bool = False,
    tier_filter: list[str] | None = None,
    subtest_filter: list[str] | None = None,
    run_filter: list[int] | None = None,
    judge_slot_filter: list[int] | None = None,
    status_filter: list[JudgeSlotStatus] | None = None,
    judge_model: str | None = None,
    regenerate_only: bool = False,
) -> RerunJudgeStats:
    """Re-run judges for failed/missing judge evaluations in an experiment.

    Args:
        experiment_dir: Path to experiment directory
        dry_run: Show what would be done without executing
        verbose: Enable verbose logging
        tier_filter: Only process these tiers (e.g., ["T0", "T1"])
        subtest_filter: Only process these subtests (e.g., ["00", "01"])
        run_filter: Only process these run numbers (e.g., [1, 3, 5])
        judge_slot_filter: Only process these judge slots (e.g., [1, 3])
        status_filter: Only rerun judge slots with these statuses
        judge_model: Judge model to use (default: from config) - IGNORED, uses config.judge_models
        regenerate_only: Only regenerate consensus, don't re-run judges

    Returns:
        RerunJudgeStats with summary of what was done

    """
    # Configure logging
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    logger.info(f"Scanning experiment directory: {experiment_dir}")

    # Load experiment config
    config_file = experiment_dir / "config" / "experiment.json"
    if not config_file.exists():
        raise FileNotFoundError(f"Experiment config not found: {config_file}")

    config = ExperimentConfig.load(config_file)
    logger.info(f"Loaded config: {config.experiment_id}")
    logger.info(f"Judge models: {config.judge_models}")

    # Auto-detect tiers_dir
    current = experiment_dir
    tiers_dir = None
    for _ in range(5):
        candidate = current / "tests" / "fixtures" / "tests"
        if candidate.exists() and candidate.is_dir():
            test_dirs = [
                d for d in candidate.iterdir() if d.is_dir() and d.name.startswith("test-")
            ]
            if test_dirs:
                tiers_dir = sorted(test_dirs)[0]
                break
        current = current.parent
        if current == current.parent:
            break

    if not tiers_dir:
        project_root = Path(__file__).parent.parent.parent.parent
        candidate = project_root / "tests" / "fixtures" / "tests"
        if candidate.exists():
            test_dirs = [
                d for d in candidate.iterdir() if d.is_dir() and d.name.startswith("test-")
            ]
            if test_dirs:
                tiers_dir = sorted(test_dirs)[0]

    if not tiers_dir:
        raise FileNotFoundError(
            "Could not auto-detect tiers directory. Please ensure the experiment was created "
            "with a valid test fixture directory."
        )

    logger.info(f"Using tiers directory: {tiers_dir}")

    # Create tier manager
    tier_manager = TierManager(tiers_dir)

    # Scan for judge slots by status
    stats = RerunJudgeStats()
    slots_by_status = scan_judges_needing_rerun(
        experiment_dir=experiment_dir,
        config=config,
        tier_manager=tier_manager,
        tier_filter=tier_filter,
        subtest_filter=subtest_filter,
        run_filter=run_filter,
        judge_slot_filter=judge_slot_filter,
        status_filter=status_filter,
        stats=stats,
    )

    # Print classification summary
    logger.info("Classification complete:")
    logger.info(f"  total slots:   {stats.total_expected_slots}")
    logger.info(f"  complete:      {stats.complete}")
    logger.info(f"  missing:       {stats.missing}")
    logger.info(f"  failed:        {stats.failed}")
    logger.info(f"  agent_failed:  {stats.agent_failed}")

    # Regenerate-only mode: just rebuild consensus files
    if regenerate_only:
        logger.info("Regenerate-only mode: rebuilding consensus files")

        # Find all runs where all judge slots are complete but result.json is missing
        runs_to_regenerate = set()
        for slot in slots_by_status[JudgeSlotStatus.COMPLETE]:
            result_file = slot.run_dir / "judge" / "result.json"
            if not result_file.exists():
                runs_to_regenerate.add(slot.run_dir)

        logger.info(f"Found {len(runs_to_regenerate)} runs needing consensus regeneration")

        if dry_run:
            print("\n" + "=" * 70)
            print("DRY RUN MODE - No changes will be made")
            print("=" * 70)
            print(f"\nWould regenerate consensus for {len(runs_to_regenerate)} runs")
            print("(All runs have complete judge slots but missing judge/result.json)")
            stats.print_summary(config.judge_models)
            return stats

        for run_dir in sorted(runs_to_regenerate):
            if _regenerate_consensus(run_dir, config.judge_models):
                stats.consensus_regenerated += 1

        stats.print_summary(config.judge_models)
        return stats

    # Standard dry-run mode (not regenerate-only)
    if dry_run:
        print("\n" + "=" * 70)
        print("DRY RUN MODE - No changes will be made")
        print("=" * 70)

        for status, slots in slots_by_status.items():
            if slots:
                print(f"\n{status.value.upper().replace('_', ' ')} ({len(slots)} slots):")
                for slot in slots[:10]:
                    print(
                        f"  - {slot.tier_id}/{slot.subtest_id}/run_{slot.run_number:02d} "
                        f"judge_{slot.judge_number:02d} ({slot.judge_model}): {slot.reason}"
                    )
                if len(slots) > 10:
                    print(f"  ... and {len(slots) - 10} more")

        stats.print_summary(config.judge_models)
        return stats

    # Determine which judge slots to rerun (exclude complete and agent_failed)
    needs_judge_rerun = []
    for status in [JudgeSlotStatus.MISSING, JudgeSlotStatus.FAILED]:
        needs_judge_rerun.extend(slots_by_status[status])

    logger.info(f"Judge slots needing re-execution: {len(needs_judge_rerun)}")

    # Re-run judges slot by slot
    if needs_judge_rerun:
        logger.info("Re-running judge slots...")

        # Track which run_dirs had judges re-run (for consensus regeneration)
        runs_with_reruns = set()

        for slot in needs_judge_rerun:
            if _rerun_single_judge_slot(slot, experiment_dir, config):
                stats.slots_rerun_success += 1
                runs_with_reruns.add(slot.run_dir)
            else:
                stats.slots_rerun_failed += 1

        logger.info(f"✓ Re-ran {stats.slots_rerun_success} judge slots")
        logger.info(f"✗ Failed to re-run {stats.slots_rerun_failed} judge slots")

        # Regenerate consensus for runs that had any judge re-run
        logger.info(f"Regenerating consensus for {len(runs_with_reruns)} runs")
        for run_dir in sorted(runs_with_reruns):
            if _regenerate_consensus(run_dir, config.judge_models):
                stats.consensus_regenerated += 1

    stats.print_summary(config.judge_models)
    return stats
