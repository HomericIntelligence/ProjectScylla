#!/usr/bin/env python3
r"""Repair checkpoint by rebuilding completed_runs from run_result.json files.

This script fixes checkpoints where completed_runs is empty despite having
completed run_result.json files. This can happen when the main process
overwrites worker progress during interrupt handling.

Usage:
    python scripts/repair_checkpoint.py <checkpoint_path>

Example:
    python scripts/repair_checkpoint.py \
        ~/fullruns/test001-nothinking/2026-01-20T06-50-26-test-001/checkpoint.json

"""

import json
import sys
from pathlib import Path


def repair_checkpoint(checkpoint_path: Path) -> None:
    """Repair checkpoint by rebuilding completed_runs from run_result.json files.

    Args:
        checkpoint_path: Path to checkpoint.json file

    """
    if not checkpoint_path.exists():
        print(f"❌ Checkpoint not found: {checkpoint_path}")
        sys.exit(1)

    experiment_dir = checkpoint_path.parent

    # Load existing checkpoint
    print(f"📂 Loading checkpoint: {checkpoint_path}")
    with open(checkpoint_path) as f:
        checkpoint = json.load(f)

    original_count = sum(
        len(runs)
        for tier in checkpoint.get("completed_runs", {}).values()
        for runs in tier.values()
    )
    print(f"📊 Current completed_runs count: {original_count}")

    # Rebuild completed_runs from run_result.json files
    print(f"🔍 Scanning for run_result.json files in: {experiment_dir}")
    completed_runs = {}
    run_files_found = 0

    for run_result_file in experiment_dir.rglob("run_result.json"):
        run_files_found += 1
        parts = run_result_file.relative_to(experiment_dir).parts

        # Expected structure: T0/00/run_01/run_result.json
        if len(parts) >= 4:
            tier_id = parts[0]
            subtest_id = parts[1]
            run_dir = parts[2]  # "run_01", "run_02", etc.

            try:
                run_num = int(run_dir.split("_")[1])
            except (IndexError, ValueError):
                print(f"⚠️  Skipping malformed run dir: {run_result_file}")
                continue

            # Load run result to check status
            try:
                with open(run_result_file) as f:
                    run_data = json.load(f)
            except json.JSONDecodeError:
                print(f"⚠️  Skipping invalid JSON: {run_result_file}")
                continue

            status = "passed" if run_data.get("judge_passed", False) else "failed"

            # Build nested structure
            if tier_id not in completed_runs:
                completed_runs[tier_id] = {}
            if subtest_id not in completed_runs[tier_id]:
                completed_runs[tier_id][subtest_id] = {}
            completed_runs[tier_id][subtest_id][run_num] = status

    print(f"📁 Found {run_files_found} run_result.json files")

    # Count total completed runs in rebuilt structure
    rebuilt_count = sum(len(runs) for tier in completed_runs.values() for runs in tier.values())

    if rebuilt_count == 0:
        print("⚠️  No completed runs found. Nothing to repair.")
        return

    # Update checkpoint
    checkpoint["completed_runs"] = completed_runs

    # Reset status if it was interrupted
    if checkpoint.get("status") == "interrupted":
        checkpoint["status"] = "running"
        print("🔄 Resetting status from 'interrupted' to 'running'")

    # Save repaired checkpoint (backup original first)
    backup_path = checkpoint_path.with_suffix(".json.backup")
    print(f"💾 Backing up original checkpoint to: {backup_path}")
    with open(backup_path, "w") as f:
        json.dump(checkpoint, f, indent=2)

    print(f"💾 Saving repaired checkpoint to: {checkpoint_path}")
    with open(checkpoint_path, "w") as f:
        json.dump(checkpoint, f, indent=2)

    print("\n✅ Checkpoint repaired successfully!")
    print(f"   Original completed_runs: {original_count}")
    print(f"   Rebuilt completed_runs:  {rebuilt_count}")
    print(f"   Difference:              {rebuilt_count - original_count:+d}")

    # Print breakdown by tier
    print("\n📊 Breakdown by tier:")
    for tier_id in sorted(completed_runs.keys()):
        tier_runs = sum(len(runs) for runs in completed_runs[tier_id].values())
        print(f"   {tier_id}: {tier_runs} runs")


def main() -> None:
    """Execute checkpoint repair from command line."""
    if len(sys.argv) != 2:
        print("Usage: python scripts/repair_checkpoint.py <checkpoint_path>")
        print("\nExample:")
        print("  python scripts/repair_checkpoint.py \\")
        print("      ~/fullruns/test001-nothinking/2026-01-20T06-50-26-test-001/checkpoint.json")
        sys.exit(1)

    checkpoint_path = Path(sys.argv[1]).expanduser().resolve()
    repair_checkpoint(checkpoint_path)


if __name__ == "__main__":
    main()
