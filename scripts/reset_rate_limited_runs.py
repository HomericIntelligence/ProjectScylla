#!/usr/bin/env python3
"""Reset rate-limited (HTTP 429) runs in a test-001 experiment for rerun.

Scans the experiment results directory, identifies runs that failed due to
Anthropic API rate limiting (429 errors), resets their checkpoint states to
pending, and cleans up result/report artifacts so they regenerate on rerun.

Usage:
    # Dry run (default) - shows what would be changed
    python scripts/reset_rate_limited_runs.py results/2026-03-30T04-09-50-test-001

    # Actually perform the reset
    python scripts/reset_rate_limited_runs.py results/2026-03-30T04-09-50-test-001 --apply
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path


def is_rate_limited_agent(result_path: Path) -> bool:
    """Check if an agent result.json indicates a 429 rate limit failure."""
    if not result_path.exists():
        return False
    try:
        data = json.loads(result_path.read_text())
        # Check the parsed stdout JSON for api_error_status
        stdout = data.get("stdout", "")
        if stdout:
            try:
                stdout_data = json.loads(stdout)
                if stdout_data.get("api_error_status") == 429:
                    return True
            except (json.JSONDecodeError, TypeError):
                pass
        # Also check if exit_code=1 and 0 tokens (crash signature)
        if (
            data.get("exit_code") == 1
            and data.get("cost_usd") == 0.0
            and data.get("api_calls", 0) <= 1
        ):
            token_stats = data.get("token_stats", {})
            if token_stats.get("input_tokens", 0) == 0 and token_stats.get("output_tokens", 0) == 0:
                return True
    except (json.JSONDecodeError, OSError):
        pass
    return False


def is_rate_limited_judges(run_result_path: Path) -> bool:
    """Check if run_result.json shows judges failed due to rate limiting."""
    if not run_result_path.exists():
        return False
    try:
        data = json.loads(run_result_path.read_text())
        judges = data.get("judges", [])
        if not judges:
            return False
        # All judges must have failed with rate limit
        return all(
            not j.get("is_valid", True) and "usage limit" in j.get("reasoning", "").lower()
            for j in judges
        )
    except (json.JSONDecodeError, OSError):
        pass
    return False


def find_rate_limited_runs(
    experiment_dir: Path,
) -> dict[str, dict[str, list[str]]]:
    """Find all rate-limited runs. Returns {tier: {subtest: [run_nums]}}."""
    affected: dict[str, dict[str, list[str]]] = {}
    completed_dir = experiment_dir / "completed"

    if not completed_dir.exists():
        print(f"ERROR: {completed_dir} does not exist")
        sys.exit(1)

    for tier_dir in sorted(completed_dir.iterdir()):
        if not tier_dir.is_dir() or tier_dir.name.startswith("."):
            continue
        tier_id = tier_dir.name

        for subtest_dir in sorted(tier_dir.iterdir()):
            if not subtest_dir.is_dir() or subtest_dir.name.startswith("."):
                continue
            subtest_id = subtest_dir.name

            for run_dir in sorted(subtest_dir.iterdir()):
                if not run_dir.is_dir() or not run_dir.name.startswith("run_"):
                    continue
                run_num = run_dir.name.replace("run_", "").lstrip("0") or "1"

                agent_result = run_dir / "agent" / "result.json"
                run_result = run_dir / "run_result.json"

                if is_rate_limited_agent(agent_result) or is_rate_limited_judges(run_result):
                    affected.setdefault(tier_id, {}).setdefault(subtest_id, []).append(run_num)

    return affected


def clean_run_artifacts(run_dir: Path, dry_run: bool) -> list[str]:
    """Remove result/report artifacts from a rate-limited run directory."""
    removed: list[str] = []

    # Files to remove from the run directory
    files_to_remove = [
        "run_result.json",
        "report.json",
        "report.md",
    ]

    for fname in files_to_remove:
        fpath = run_dir / fname
        if fpath.exists():
            removed.append(str(fpath))
            if not dry_run:
                fpath.unlink()

    # Clean judge directory contents (keep the directory structure)
    judge_dir = run_dir / "judge"
    if judge_dir.exists():
        for item in judge_dir.iterdir():
            if item.is_dir():
                # Clean judge subdirs (judge_01, judge_02, etc.)
                for f in item.iterdir():
                    removed.append(str(f))
                    if not dry_run:
                        if f.is_dir():
                            shutil.rmtree(f)
                        else:
                            f.unlink()
            elif item.is_file():
                # Clean top-level judge files (result.json, timing.json)
                removed.append(str(item))
                if not dry_run:
                    item.unlink()

    return removed


def clean_subtest_reports(subtest_dir: Path, dry_run: bool) -> list[str]:
    """Remove subtest-level report files."""
    removed: list[str] = []
    for fname in ("report.json", "report.md"):
        fpath = subtest_dir / fname
        if fpath.exists():
            removed.append(str(fpath))
            if not dry_run:
                fpath.unlink()
    return removed


def clean_experiment_reports(experiment_dir: Path, dry_run: bool) -> list[str]:
    """Remove experiment-level report files that aggregate subtest data."""
    removed: list[str] = []
    files_to_remove = [
        "report.json",
        "report.md",
        "result.json",
        "summary.md",
        "tier_comparison.json",
    ]
    for fname in files_to_remove:
        fpath = experiment_dir / fname
        if fpath.exists():
            removed.append(str(fpath))
            if not dry_run:
                fpath.unlink()
    return removed


def update_checkpoint(
    experiment_dir: Path,
    affected: dict[str, dict[str, list[str]]],
    dry_run: bool,
) -> dict[str, list[str]]:
    """Update checkpoint.json to mark affected runs for rerun.

    Returns a dict of changes made for reporting.
    """
    checkpoint_path = experiment_dir / "checkpoint.json"
    checkpoint = json.loads(checkpoint_path.read_text())
    changes: dict[str, list[str]] = {
        "run_states": [],
        "completed_runs": [],
        "subtest_states": [],
        "tier_states": [],
        "experiment_state": [],
    }

    affected_tiers: set[str] = set()

    for tier_id, subtests in affected.items():
        affected_tiers.add(tier_id)

        for subtest_id, run_nums in subtests.items():
            # Check if ALL runs in this subtest are affected
            all_runs_in_subtest = set(
                checkpoint.get("run_states", {}).get(tier_id, {}).get(subtest_id, {}).keys()
            )
            affected_run_set = set(run_nums)
            all_runs_affected = affected_run_set >= all_runs_in_subtest

            for run_num in run_nums:
                # Reset run_states to pending
                current = (
                    checkpoint.get("run_states", {})
                    .get(tier_id, {})
                    .get(subtest_id, {})
                    .get(run_num, "unknown")
                )
                if current != "pending":
                    changes["run_states"].append(
                        f"  {tier_id}/{subtest_id}/run_{run_num}: {current} -> pending"
                    )
                    checkpoint["run_states"][tier_id][subtest_id][run_num] = "pending"

                # Remove from completed_runs
                completed = (
                    checkpoint.get("completed_runs", {}).get(tier_id, {}).get(subtest_id, {})
                )
                if completed and run_num in completed:
                    changes["completed_runs"].append(
                        f"  {tier_id}/{subtest_id}/run_{run_num}: removed ({completed[run_num]})"
                    )
                    del checkpoint["completed_runs"][tier_id][subtest_id][run_num]

            # Reset subtest state if all runs are affected
            if all_runs_affected:
                current_subtest = (
                    checkpoint.get("subtest_states", {}).get(tier_id, {}).get(subtest_id, "unknown")
                )
                if current_subtest not in ("pending",):
                    changes["subtest_states"].append(
                        f"  {tier_id}/{subtest_id}: {current_subtest} -> pending"
                    )
                    checkpoint["subtest_states"][tier_id][subtest_id] = "pending"

    # Reset tier states for affected tiers
    for tier_id in sorted(affected_tiers):
        current_tier = checkpoint.get("tier_states", {}).get(tier_id, "unknown")
        if current_tier not in ("pending",):
            changes["tier_states"].append(f"  {tier_id}: {current_tier} -> pending")
            checkpoint["tier_states"][tier_id] = "pending"

    # Also reset T5 and T6 tier states since they depend on lower tiers
    # T5 depends on T0-T4, T6 depends on T5
    for dep_tier in ("T5", "T6"):
        current = checkpoint.get("tier_states", {}).get(dep_tier, "unknown")
        if current not in ("pending",) and dep_tier not in affected_tiers:
            changes["tier_states"].append(
                f"  {dep_tier}: {current} -> pending (dependency cascade)"
            )
            checkpoint["tier_states"][dep_tier] = "pending"

    # Reset experiment state
    current_exp = checkpoint.get("experiment_state", "unknown")
    if current_exp != "tiers_running":
        changes["experiment_state"].append(f"  experiment_state: {current_exp} -> tiers_running")
        checkpoint["experiment_state"] = "tiers_running"

    # Reset status
    current_status = checkpoint.get("status", "unknown")
    if current_status != "running":
        changes["experiment_state"].append(f"  status: {current_status} -> running")
        checkpoint["status"] = "running"

    # Clear PID so the runner doesn't think another process owns it
    checkpoint["pid"] = None

    if not dry_run:
        # Backup original
        backup_path = checkpoint_path.with_suffix(".json.bak")
        if not backup_path.exists():
            shutil.copy2(checkpoint_path, backup_path)
            print(f"Backed up checkpoint to {backup_path}")

        checkpoint_path.write_text(json.dumps(checkpoint, indent=2) + "\n")

    return changes


def main() -> None:
    """Reset rate-limited runs in an experiment for rerun."""
    parser = argparse.ArgumentParser(
        description="Reset rate-limited runs in an experiment for rerun"
    )
    parser.add_argument(
        "experiment_dir",
        type=Path,
        help="Path to the experiment results directory",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually apply changes (default is dry-run)",
    )
    args = parser.parse_args()

    experiment_dir = args.experiment_dir.resolve()
    dry_run = not args.apply

    if dry_run:
        print("=== DRY RUN (use --apply to execute) ===\n")

    # Step 1: Find all rate-limited runs
    print("Scanning for rate-limited runs...")
    affected = find_rate_limited_runs(experiment_dir)

    if not affected:
        print("No rate-limited runs found.")
        return

    total_runs = sum(len(runs) for subtests in affected.values() for runs in subtests.values())
    total_subtests = sum(len(s) for s in affected.values())
    print(
        f"Found {total_runs} rate-limited runs across "
        f"{total_subtests} subtests in {len(affected)} tiers:\n"
    )
    for tier_id, subtests in sorted(affected.items()):
        for subtest_id, run_nums in sorted(subtests.items()):
            print(f"  {tier_id}/{subtest_id}: runs {', '.join(sorted(run_nums))}")

    # Step 2: Clean run-level artifacts
    print("\n--- Cleaning run artifacts ---")
    all_removed: list[str] = []
    for tier_id, subtests in sorted(affected.items()):
        for subtest_id, run_nums in sorted(subtests.items()):
            for run_num in sorted(run_nums):
                run_dir = (
                    experiment_dir / "completed" / tier_id / subtest_id / f"run_{int(run_num):02d}"
                )
                if run_dir.exists():
                    removed = clean_run_artifacts(run_dir, dry_run)
                    all_removed.extend(removed)

    # Step 3: Clean subtest-level reports
    print("\n--- Cleaning subtest reports ---")
    for tier_id, subtests in sorted(affected.items()):
        for subtest_id in sorted(subtests.keys()):
            subtest_dir = experiment_dir / "completed" / tier_id / subtest_id
            removed = clean_subtest_reports(subtest_dir, dry_run)
            all_removed.extend(removed)

    # Step 4: Clean experiment-level reports
    print("\n--- Cleaning experiment reports ---")
    removed = clean_experiment_reports(experiment_dir, dry_run)
    all_removed.extend(removed)

    if all_removed:
        print(f"{'Would remove' if dry_run else 'Removed'} {len(all_removed)} files:")
        for f in all_removed[:20]:
            print(f"  {f}")
        if len(all_removed) > 20:
            print(f"  ... and {len(all_removed) - 20} more")

    # Step 5: Update checkpoint
    print("\n--- Updating checkpoint ---")
    changes = update_checkpoint(experiment_dir, affected, dry_run)
    for category, items in changes.items():
        if items:
            print(f"\n{category}:")
            for item in items:
                print(item)

    if dry_run:
        print("\n=== DRY RUN COMPLETE - no changes made ===")
        print("Run with --apply to execute these changes.")
    else:
        print("\n=== RESET COMPLETE ===")
        print(f"Reset {total_runs} runs across {total_subtests} subtests. Ready for rerun.")


if __name__ == "__main__":
    main()
