#!/usr/bin/env python3
"""Analyze dryrun3 experiment results and produce Go/NoGo assessment.

Usage:
    pixi run python scripts/analyze_dryrun3.py --results-dir ~/dryrun3
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

# Tier subtest counts from tests/claude-code/shared/subtests/
TIER_SUBTEST_COUNTS: dict[str, int] = {
    "T0": 24,
    "T1": 10,
    "T2": 15,
    "T3": 41,
    "T4": 14,
    "T5": 15,
    "T6": 1,
}
TOTAL_SUBTESTS_FULL = sum(TIER_SUBTEST_COUNTS.values())  # 120
TOTAL_SUBTESTS_STANDARD = sum(min(3, v) for v in TIER_SUBTEST_COUNTS.values())  # 19

FULL_ABLATION_TESTS = {"test-001", "test-002", "test-003"}
TERMINAL_ERROR_STATES = {"failed", "rate_limited"}

# Run classification labels
COMPLETE = "COMPLETE"
INFRA_ERROR = "INFRA_ERROR"
ORPHAN = "ORPHAN"
INTERMEDIATE = "INTERMEDIATE"


def get_max_subtests(test_name: str) -> int | None:
    """Return effective max subtests per tier. None means all (full ablation)."""
    if test_name in FULL_ABLATION_TESTS:
        return None
    return 3


def discover_experiments(results_dir: Path) -> dict[str, tuple[str, Path]]:
    """Scan results_dir for experiment dirs, return latest per test name.

    Returns:
        dict mapping test_name -> (experiment_dir_name, experiment_dir_path)

    """
    pattern = re.compile(r"^(\d{4}-\d{2}-\d{2}T[\d-]+)-(test-\d{3})$")
    experiments: dict[str, list[tuple[str, Path]]] = defaultdict(list)

    for d in results_dir.iterdir():
        if not d.is_dir():
            continue
        m = pattern.match(d.name)
        if m:
            test_name = m.group(2)
            experiments[test_name].append((d.name, d))

    # Pick latest (lexicographic sort on timestamp prefix)
    result: dict[str, tuple[str, Path]] = {}
    for test_name, dirs in experiments.items():
        dirs.sort(key=lambda x: x[0], reverse=True)
        result[test_name] = dirs[0]

    return result


def classify_runs(
    run_states: dict[str, dict[str, dict[str, str]]], max_subtests: int | None
) -> dict[str, list[tuple[str, str, str, str]]]:
    """Classify each run into COMPLETE/INFRA_ERROR/ORPHAN/INTERMEDIATE.

    Returns:
        dict mapping classification -> list of (tier_id, subtest_id, run_id, state)

    """
    classified: dict[str, list[tuple[str, str, str, str]]] = defaultdict(list)

    for tier_id, subtests in run_states.items():
        tier_total = TIER_SUBTEST_COUNTS.get(tier_id, 0)
        effective_max = min(max_subtests, tier_total) if max_subtests is not None else tier_total

        for sub_id, runs in subtests.items():
            sub_index = int(sub_id)
            is_orphan = sub_index >= effective_max

            for run_id, state in runs.items():
                entry = (tier_id, sub_id, run_id, state)
                if is_orphan:
                    classified[ORPHAN].append(entry)
                elif state == "worktree_cleaned":
                    classified[COMPLETE].append(entry)
                elif state in TERMINAL_ERROR_STATES:
                    classified[INFRA_ERROR].append(entry)
                else:
                    classified[INTERMEDIATE].append(entry)

    return dict(classified)


def check_subtest_coverage(
    run_states: dict[str, dict[str, dict[str, str]]], test_name: str
) -> dict[str, tuple[int, int]]:
    """Check subtest coverage per tier.

    Returns:
        dict mapping tier_id -> (actual_active_subtests, expected_subtests)
        Only includes tiers with missing subtests.

    """
    max_subtests = get_max_subtests(test_name)
    missing: dict[str, tuple[int, int]] = {}

    for tier_id, expected_count in TIER_SUBTEST_COUNTS.items():
        effective_max = (
            min(max_subtests, expected_count) if max_subtests is not None else expected_count
        )
        subtests = run_states.get(tier_id, {})

        # Count active (non-orphan) subtests
        active = sum(1 for sub_id in subtests if int(sub_id) < effective_max)

        if active < effective_max:
            missing[tier_id] = (active, effective_max)

    return missing


def load_grades(
    experiment_dir: Path,
    complete_runs: list[tuple[str, str, str, str]],
) -> tuple[int, int, int]:
    """Load grades from run_result.json for completed runs.

    Returns:
        (passed, failed, missing_json) counts

    """
    passed = 0
    failed = 0
    missing_json = 0

    for tier_id, sub_id, run_id, _state in complete_runs:
        run_result_path = (
            experiment_dir / tier_id / sub_id / f"run_{int(run_id):02d}" / "run_result.json"
        )
        if not run_result_path.exists():
            missing_json += 1
            continue
        try:
            with open(run_result_path) as f:
                data = json.load(f)
            if data.get("judge_passed", False):
                passed += 1
            else:
                failed += 1
        except Exception:
            missing_json += 1

    return passed, failed, missing_json


def load_per_tier_grades(
    experiment_dir: Path,
    complete_runs: list[tuple[str, str, str, str]],
) -> dict[str, tuple[int, int]]:
    """Load pass/fail counts per tier for completed runs."""
    tier_grades: dict[str, list[bool]] = defaultdict(list)

    for tier_id, sub_id, run_id, _state in complete_runs:
        run_result_path = (
            experiment_dir / tier_id / sub_id / f"run_{int(run_id):02d}" / "run_result.json"
        )
        if not run_result_path.exists():
            continue
        try:
            with open(run_result_path) as f:
                data = json.load(f)
            tier_grades[tier_id].append(data.get("judge_passed", False))
        except Exception:
            pass

    return {tier: (sum(grades), len(grades)) for tier, grades in tier_grades.items()}


def analyze_test(
    test_name: str,
    exp_dir_name: str,
    experiment_dir: Path,
) -> dict[str, Any]:
    """Analyze a single test experiment. Returns analysis dict."""
    cp_path = experiment_dir / "checkpoint.json"
    if not cp_path.exists():
        return {
            "test_name": test_name,
            "exp_dir": exp_dir_name,
            "error": "no checkpoint.json",
        }

    with open(cp_path) as f:
        cp = json.load(f)

    run_states: dict[str, dict[str, dict[str, str]]] = cp.get("run_states", {})
    max_subtests = get_max_subtests(test_name)
    classified = classify_runs(run_states, max_subtests)

    complete_runs = classified.get(COMPLETE, [])
    infra_error_runs = classified.get(INFRA_ERROR, [])
    orphan_runs = classified.get(ORPHAN, [])
    intermediate_runs = classified.get(INTERMEDIATE, [])

    total_in_cp = sum(len(runs) for subtests in run_states.values() for runs in subtests.values())
    active_in_cp = total_in_cp - len(orphan_runs)

    missing_subtests = check_subtest_coverage(run_states, test_name)
    passed, failed, missing_json = load_grades(experiment_dir, complete_runs)
    per_tier_grades = load_per_tier_grades(experiment_dir, complete_runs)

    # Expected total active runs (1 run per subtest)
    if max_subtests is None:
        expected_runs = TOTAL_SUBTESTS_FULL
    else:
        expected_runs = TOTAL_SUBTESTS_STANDARD

    return {
        "test_name": test_name,
        "exp_dir": exp_dir_name,
        "experiment_dir": experiment_dir,
        "max_subtests": max_subtests,
        "total_in_cp": total_in_cp,
        "active_in_cp": active_in_cp,
        "expected_runs": expected_runs,
        "complete": len(complete_runs),
        "infra_error": len(infra_error_runs),
        "orphan": len(orphan_runs),
        "intermediate": len(intermediate_runs),
        "missing_subtests": missing_subtests,
        "infra_error_runs": infra_error_runs,
        "intermediate_runs": intermediate_runs,
        "passed": passed,
        "failed": failed,
        "missing_json": missing_json,
        "per_tier_grades": per_tier_grades,
        "experiment_state": cp.get("experiment_state", "unknown"),
    }


def go_nogo(all_results: list[dict[str, Any]]) -> tuple[str, list[str]]:
    """Compute Go/NoGo verdict from all test results.

    Returns:
        (verdict, list_of_reasons)

    """
    reasons: list[str] = []
    warnings: list[str] = []

    # 1. Coverage: all 47 tests have checkpoints
    errored = [r for r in all_results if "error" in r]
    if errored:
        reasons.append(
            f"{len(errored)} tests missing checkpoint: {[r['test_name'] for r in errored]}"
        )

    # 2. Active completion: all non-orphan runs at worktree_cleaned
    total_incomplete = sum(r.get("infra_error", 0) + r.get("intermediate", 0) for r in all_results)
    if total_incomplete > 0:
        reasons.append(
            f"{total_incomplete} active runs not yet complete (infra errors or intermediate)"
        )

    # 3. Subtest expansion: tests have expected subtest count per tier
    tests_with_missing = [
        r for r in all_results if r.get("missing_subtests") and not r.get("error")
    ]
    if tests_with_missing:
        reasons.append(
            f"{len(tests_with_missing)} tests have missing subtests (not yet created in checkpoint)"
        )

    # 4. Data quality: >=95% complete runs have valid run_result.json
    total_complete = sum(r.get("complete", 0) for r in all_results)
    total_missing_json = sum(r.get("missing_json", 0) for r in all_results)
    if total_complete > 0:
        quality_pct = 1.0 - (total_missing_json / total_complete)
        if quality_pct < 0.95:
            reasons.append(
                f"Data quality {quality_pct:.1%} below 95% threshold "
                f"({total_missing_json} runs missing run_result.json)"
            )
        elif total_missing_json > 0:
            warnings.append(f"{total_missing_json} complete runs missing run_result.json")

    if not reasons:
        if warnings:
            return "CONDITIONAL_GO", warnings
        return "GO", []
    return "NOGO", reasons


def generate_report(all_results: list[dict[str, Any]]) -> tuple[str, list[str]]:
    """Print the analysis report to stdout. Returns (verdict, reasons)."""
    today = date.today().isoformat()
    print(f"=== DRYRUN3 COMPLETION ANALYSIS ({today}) ===")
    print()

    # Sort by test name
    all_results.sort(key=lambda r: r["test_name"])

    tests_needing_work = [
        r
        for r in all_results
        if r.get("error")
        or r.get("infra_error", 0) > 0
        or r.get("intermediate", 0) > 0
        or r.get("missing_subtests")
    ]
    tests_complete = [
        r
        for r in all_results
        if not r.get("error")
        and r.get("infra_error", 0) == 0
        and r.get("intermediate", 0) == 0
        and not r.get("missing_subtests")
    ]

    total_active = sum(r.get("active_in_cp", 0) for r in all_results)
    total_complete_runs = sum(r.get("complete", 0) for r in all_results)
    total_infra_error = sum(r.get("infra_error", 0) for r in all_results)
    total_intermediate = sum(r.get("intermediate", 0) for r in all_results)
    total_orphan = sum(r.get("orphan", 0) for r in all_results)

    # Count missing runs (subtests not yet in checkpoint)
    total_missing_runs = 0
    for r in all_results:
        if r.get("missing_subtests"):
            for tier_id, (actual, expected) in r["missing_subtests"].items():
                total_missing_runs += expected - actual

    print("--- SUMMARY ---")
    print(f"Tests: {len(all_results)} | Complete: {len(tests_complete)}")
    print(
        f"Active runs: {total_active} | "
        f"Complete: {total_complete_runs} | "
        f"Incomplete: {total_infra_error + total_intermediate} | "
        f"Missing: {total_missing_runs}"
    )
    print(f"Orphan runs: {total_orphan} (ignored)")
    print()

    if tests_needing_work:
        print("--- TESTS NEEDING WORK ---")
        for r in tests_needing_work:
            test_name = r["test_name"]
            max_sub = r.get("max_subtests")
            subtest_type = (
                "full ablation, all subtests"
                if max_sub is None
                else f"standard, max_subtests={max_sub}"
            )
            print(f"\n{test_name} ({subtest_type}):")

            if r.get("error"):
                print(f"  ERROR: {r['error']}")
                continue

            print(
                f"  In checkpoint: {r['active_in_cp']} | "
                f"Expected: {r.get('expected_runs', '?')} | "
                f"Complete: {r['complete']} | "
                f"Incomplete: {r['infra_error'] + r['intermediate']}"
            )

            if r.get("missing_subtests"):
                missing_parts = []
                for tier_id, (actual, expected) in sorted(r["missing_subtests"].items()):
                    missing_parts.append(f"{tier_id}({actual}/{expected})")
                print(f"  MISSING SUBTESTS: {', '.join(missing_parts)}")
                total_ms = sum(exp - act for act, exp in r["missing_subtests"].values())
                print(f"  ({total_ms} subtests / runs not yet in checkpoint)")

            if r.get("infra_error", 0) > 0:
                items = [
                    f"{t}/{s}/run_{int(rn):02d}({st})"
                    for t, s, rn, st in r["infra_error_runs"][:10]
                ]
                suffix = f" ... (+{r['infra_error'] - 10} more)" if r["infra_error"] > 10 else ""
                print(f"  INFRA_ERROR: {', '.join(items)}{suffix}")

            if r.get("intermediate", 0) > 0:
                items = [
                    f"{t}/{s}/run_{int(rn):02d}({st})"
                    for t, s, rn, st in r["intermediate_runs"][:10]
                ]
                suffix = f" ... (+{r['intermediate'] - 10} more)" if r["intermediate"] > 10 else ""
                print(f"  INTERMEDIATE: {', '.join(items)}{suffix}")

        print()

    # Grade distribution
    total_passed = sum(r.get("passed", 0) for r in all_results)
    total_failed = sum(r.get("failed", 0) for r in all_results)
    total_missing_json = sum(r.get("missing_json", 0) for r in all_results)
    total_judged = total_passed + total_failed

    print("--- GRADE DISTRIBUTION ---")
    if total_judged > 0:
        print(
            f"Overall: {total_passed} passed, {total_failed} failed / "
            f"{total_complete_runs} complete runs ({total_passed / total_judged:.1%} pass rate)"
        )
        if total_missing_json:
            print(f"  ({total_missing_json} complete runs missing run_result.json)")

        # Per-tier aggregation across all tests
        tier_totals: dict[str, tuple[int, int]] = defaultdict(lambda: (0, 0))
        for r in all_results:
            for tier_id, (p, total) in r.get("per_tier_grades", {}).items():
                prev_p, prev_total = tier_totals[tier_id]
                tier_totals[tier_id] = (prev_p + p, prev_total + total)

        tier_rows = []
        for tier_id in sorted(TIER_SUBTEST_COUNTS.keys()):
            if tier_id in tier_totals:
                p, total = tier_totals[tier_id]
                pct = p / total if total > 0 else 0.0
                tier_rows.append(f"{tier_id}: {pct:.0%}({p}/{total})")
        if tier_rows:
            print(f"Per-tier: {', '.join(tier_rows)}")
    else:
        print("  No complete runs with grade data found.")

    print()

    verdict, reasons = go_nogo(all_results)
    print(f"--- GO/NOGO: {verdict} ---")
    if reasons:
        for reason in reasons:
            print(f"  - {reason}")
    else:
        print("  All criteria met.")
    print()

    return verdict, reasons


def main() -> None:
    """Analyze dryrun3 experiment results from checkpoint files."""
    parser = argparse.ArgumentParser(description="Analyze dryrun3 experiment results")
    parser.add_argument(
        "--results-dir",
        required=True,
        type=Path,
        help="Path to dryrun3 results directory (e.g. ~/dryrun3)",
    )
    args = parser.parse_args()

    results_dir = args.results_dir.expanduser().resolve()
    if not results_dir.exists():
        print(f"ERROR: results-dir does not exist: {results_dir}", file=sys.stderr)
        sys.exit(1)

    experiments = discover_experiments(results_dir)

    # Check for missing tests
    all_test_names = {f"test-{i:03d}" for i in range(1, 48)}
    missing_tests = all_test_names - experiments.keys()
    if missing_tests:
        print(f"WARNING: No experiment dirs found for: {sorted(missing_tests)}", file=sys.stderr)

    all_results: list[dict[str, Any]] = []

    # Add missing tests as errors
    for test_name in sorted(missing_tests):
        all_results.append(
            {"test_name": test_name, "exp_dir": "", "error": "no experiment dir found"}
        )

    # Analyze found experiments
    for test_name in sorted(experiments.keys()):
        exp_dir_name, experiment_dir = experiments[test_name]
        result = analyze_test(test_name, exp_dir_name, experiment_dir)
        all_results.append(result)

    verdict, reasons = generate_report(all_results)

    if verdict == "NOGO":
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
