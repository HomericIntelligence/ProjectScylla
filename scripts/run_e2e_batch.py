#!/usr/bin/env python3
"""Batch runner for E2E experiments across all 47 tests using 4 parallel threads.

This script runs all E2E tests in parallel across multiple threads, with optimal
load balancing based on expected runtime (timeout_seconds). Results are logged
per-thread and aggregated into a batch summary.

Python Justification: Required for thread orchestration and subprocess management.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import logging
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add scripts/ to path for common utilities
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from common import Colors, get_repo_root
from scylla.e2e.models import TestFixture
from scylla.e2e.rate_limit import check_api_rate_limit_status

# Defaults (overridable via CLI args)
DEFAULT_RESULTS_DIR = Path.home() / "dryrun"
DEFAULT_NUM_THREADS = 4
DEFAULT_MODEL = "haiku"
DEFAULT_JUDGE_MODEL = "haiku"
DEFAULT_RUNS = 1
DEFAULT_MAX_SUBTESTS = 2
DEFAULT_TIERS = ["T0", "T1", "T2", "T3", "T4", "T5", "T6"]

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def load_existing_results(results_dir: Path) -> list[dict]:
    """Load existing results from batch_summary.json if it exists.

    Args:
        results_dir: Results directory containing batch_summary.json

    Returns:
        List of previously completed test results, or [] if no summary exists

    """
    summary_path = results_dir / "batch_summary.json"
    if not summary_path.exists():
        return []

    try:
        with open(summary_path) as f:
            data = json.load(f)
        results = data.get("results", [])
        logger.info(f"Loaded {len(results)} existing results from {summary_path}")
        return results
    except Exception as e:
        logger.warning(f"Failed to load existing results from {summary_path}: {e}")
        return []


def save_incremental_result(results_dir: Path, result: dict, config: dict) -> None:
    """Save a single result incrementally to batch_summary.json.

    Loads existing summary, appends the new result, and writes atomically.

    Args:
        results_dir: Results directory
        result: Single test result dict to append
        config: Configuration dict

    """
    summary_path = results_dir / "batch_summary.json"
    tmp_path = results_dir / "batch_summary.json.tmp"

    # Load existing summary or create fresh structure
    if summary_path.exists():
        try:
            with open(summary_path) as f:
                summary = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load existing summary, creating fresh: {e}")
            summary = {
                "started_at": config.get("started_at", datetime.now(timezone.utc).isoformat()),
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "config": config,
                "threads": [],
                "results": [],
            }
    else:
        summary = {
            "started_at": config.get("started_at", datetime.now(timezone.utc).isoformat()),
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "config": config,
            "threads": [],
            "results": [],
        }

    # Append new result
    summary["results"].append(result)
    summary["completed_at"] = datetime.now(timezone.utc).isoformat()

    # Write atomically (tmp + rename)
    with open(tmp_path, "w") as f:
        json.dump(summary, f, indent=2)
    tmp_path.rename(summary_path)

    logger.debug(f"Saved incremental result for {result['test_id']} to {summary_path}")


def check_rate_limit() -> tuple[bool, str]:
    """Check if API is currently rate-limited.

    Returns:
        Tuple of (is_rate_limited, message)

    """
    rate_info = check_api_rate_limit_status()
    if rate_info:
        reset_time = rate_info.detected_at
        if rate_info.retry_after_seconds:
            reset_time = (
                datetime.now(timezone.utc) + timedelta(seconds=rate_info.retry_after_seconds)
            ).isoformat()
        message = f"Rate limited until {reset_time}: {rate_info.error_message}"
        return True, message
    return False, ""


def discover_tests(tests_dir: Path, test_filter: list[str] | None = None) -> list[dict]:
    """Find all test-XXX dirs using TestFixture.from_directory() for metadata.

    Args:
        tests_dir: Path to tests/fixtures/tests directory
        test_filter: Optional list of specific test IDs to run (e.g., ["test-001", "test-005"])

    Returns:
        List of test metadata dicts: {id, name, timeout_seconds, path}

    """
    logger.info(f"Discovering tests in {tests_dir}")

    tests = []
    for test_dir in sorted(tests_dir.glob("test-*")):
        if not test_dir.is_dir():
            continue

        test_id = test_dir.name

        # Skip test-config-loader (it's not a real test)
        if test_id == "test-config-loader":
            continue

        # Apply filter if specified
        if test_filter and test_id not in test_filter:
            continue

        try:
            fixture = TestFixture.from_directory(test_dir)
            tests.append(
                {
                    "id": fixture.id,
                    "name": fixture.name,
                    "timeout_seconds": fixture.timeout_seconds,
                    "path": test_dir,
                }
            )
            logger.debug(
                f"Found {test_id}: {fixture.name} (timeout: {fixture.timeout_seconds}s)"
            )
        except Exception as e:
            logger.warning(f"Failed to load test {test_id}: {e}")
            continue

    logger.info(f"Discovered {len(tests)} tests")
    return tests


def partition_tests(tests: list[dict], num_threads: int) -> list[list[dict]]:
    """LPT scheduling: sort by timeout desc, assign to thread with lowest load.

    Uses Longest Processing Time First (LPT) algorithm to balance workload
    across threads.

    Args:
        tests: List of test metadata dicts
        num_threads: Number of threads to partition across

    Returns:
        List of thread assignments, where each element is a list of tests for that thread

    """
    # Sort tests by timeout descending (longest first)
    sorted_tests = sorted(tests, key=lambda t: t["timeout_seconds"], reverse=True)

    # Initialize thread assignments and load tracking
    threads: list[list[dict]] = [[] for _ in range(num_threads)]
    thread_loads: list[int] = [0] * num_threads

    # Assign each test to the thread with the lowest current load
    for test in sorted_tests:
        # Find thread with minimum load
        min_load_idx = min(range(num_threads), key=lambda i: thread_loads[i])

        # Assign test to that thread
        threads[min_load_idx].append(test)
        thread_loads[min_load_idx] += test["timeout_seconds"]

    # Log partition results
    for i, thread_tests in enumerate(threads):
        total_time = sum(t["timeout_seconds"] for t in thread_tests)
        logger.info(
            f"Thread {i}: {len(thread_tests)} tests, "
            f"~{total_time}s ({total_time / 3600:.1f}h)"
        )

    return threads


def run_single_test(test: dict, thread_id: int, log_file, args, config: dict) -> dict:
    """Run one test via subprocess, capture output to log file.

    Args:
        test: Test metadata dict
        thread_id: Thread ID for logging
        log_file: Open file handle for logging
        args: Parsed CLI arguments
        config: Configuration dict for incremental saves

    Returns:
        Result dict with status, metrics, and paths

    """
    test_id = test["id"]
    logger.info(f"[Thread {thread_id}] Starting {test_id}")

    # Build command (conditionally add --fresh)
    cmd = [
        "pixi",
        "run",
        "python",
        "scripts/run_e2e_experiment.py",
        "--tiers-dir",
        str(test["path"]),
        "--tiers",
        *args.tiers,
        "--runs",
        str(args.runs),
        "--max-subtests",
        str(args.max_subtests),
        "--model",
        args.model,
        "--judge-model",
        args.judge_model,
        "--thinking",
        args.thinking,
        "--results-dir",
        str(args.results_dir),
    ]
    if args.fresh:
        cmd.append("--fresh")

    # Write command to log
    log_file.write(f"\n{'=' * 70}\n")
    log_file.write(f"[{datetime.now(timezone.utc).isoformat()}] Starting {test_id}\n")
    log_file.write(f"Command: {' '.join(cmd)}\n")
    log_file.write(f"{'=' * 70}\n\n")
    log_file.flush()

    # Run subprocess
    start_time = datetime.now(timezone.utc)
    try:
        result = subprocess.run(
            cmd,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,  # Don't raise on error
        )
        exit_code = result.returncode
        error = None if exit_code == 0 else f"Exit code: {exit_code}"
    except Exception as e:
        exit_code = -1
        error = str(e)
        log_file.write(f"\nERROR: {e}\n")
        log_file.flush()

    end_time = datetime.now(timezone.utc)
    duration = (end_time - start_time).total_seconds()

    # Write completion to log
    log_file.write(f"\n{'=' * 70}\n")
    log_file.write(
        f"[{end_time.isoformat()}] Completed {test_id} in {duration:.1f}s "
        f"(exit code: {exit_code})\n"
    )
    log_file.write(f"{'=' * 70}\n\n")
    log_file.flush()

    # Find result directory and extract metrics
    result_dir = find_result_dir(args.results_dir, test_id)
    metrics = extract_metrics(result_dir) if result_dir else None

    # Determine status
    if exit_code == 0 and metrics:
        status = "pass" if metrics.get("best_score", 0) > 0.5 else "fail"
    elif exit_code == 0:
        status = "unknown"
    else:
        status = "error"

    logger.info(f"[Thread {thread_id}] Completed {test_id}: {status.upper()}")

    result = {
        "test_id": test_id,
        "thread_id": thread_id,
        "status": status,
        "exit_code": exit_code,
        "result_dir": str(result_dir) if result_dir else None,
        "error": error,
        **(metrics or {}),
    }

    # Save incremental result
    save_incremental_result(args.results_dir, result, config)

    return result


def run_thread(thread_id: int, tests: list[dict], log_dir: Path, args, config: dict) -> list[dict]:
    """Run all assigned tests sequentially within one thread.

    Args:
        thread_id: Thread ID
        tests: List of tests assigned to this thread
        log_dir: Directory for log files
        args: Parsed CLI arguments
        config: Configuration dict for incremental saves

    Returns:
        List of result dicts

    """
    log_file_path = log_dir / f"thread_{thread_id}.log"
    logger.info(f"[Thread {thread_id}] Starting with {len(tests)} tests")
    logger.info(f"[Thread {thread_id}] Logging to {log_file_path}")

    results = []
    # Use append mode to preserve logs on restart
    with open(log_file_path, "a") as log_file:
        for test in tests:
            result = run_single_test(test, thread_id, log_file, args, config)
            results.append(result)

    logger.info(f"[Thread {thread_id}] Completed all tests")
    return results


def find_result_dir(results_dir: Path, test_id: str) -> Path | None:
    """Find the timestamped result directory for a test.

    Args:
        results_dir: Base results directory
        test_id: Test ID to search for

    Returns:
        Path to result directory, or None if not found

    """
    # Look for directories matching pattern: *-{test_id}/
    pattern = f"*-{test_id}"
    matches = list(results_dir.glob(pattern))

    if not matches:
        return None

    # Return most recent (sorted by name, which includes timestamp)
    return sorted(matches)[-1]


def extract_metrics(result_dir: Path) -> dict | None:
    """Read report.json and extract summary metrics.

    Args:
        result_dir: Path to result directory

    Returns:
        Dict with metrics, or None if report not found

    """
    report_path = result_dir / "report.json"
    if not report_path.exists():
        return None

    try:
        with open(report_path) as f:
            report = json.load(f)

        return {
            "best_tier": report.get("best_overall_tier"),
            "best_score": report.get("tier_results", {})
            .get(report.get("best_overall_tier", ""), {})
            .get("best_subtest_score", 0.0),
            "frontier_cop": report.get("frontier_cop", float("inf")),
            "total_cost": report.get("total_cost", 0.0),
            "total_duration": report.get("total_duration_seconds", 0.0),
        }
    except Exception as e:
        logger.warning(f"Failed to extract metrics from {report_path}: {e}")
        return None


def write_batch_summary(
    results_dir: Path, all_results: list[dict], config: dict, threads: list[list[dict]]
) -> None:
    """Write batch_summary.json with all results.

    Args:
        results_dir: Results directory
        all_results: List of all result dicts
        config: Configuration dict
        threads: Thread partition information

    """
    summary_path = results_dir / "batch_summary.json"

    # Build thread summaries
    thread_summaries = []
    for i, thread_tests in enumerate(threads):
        thread_results = [r for r in all_results if r["thread_id"] == i]
        thread_summaries.append(
            {
                "thread_id": i,
                "tests": [t["id"] for t in thread_tests],
                "completed": len(thread_results),
                "failed": len([r for r in thread_results if r["status"] in ["fail", "error"]]),
            }
        )

    summary = {
        "started_at": config["started_at"],
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "config": {
            "model": config["model"],
            "judge_model": config["judge_model"],
            "runs": config["runs"],
            "max_subtests": config["max_subtests"],
            "thinking": config["thinking"],
            "tiers": config["tiers"],
        },
        "threads": thread_summaries,
        "results": all_results,
    }

    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    logger.info(f"Wrote batch summary to {summary_path}")


def write_analysis_prompt(results_dir: Path, config: dict) -> None:
    """Write ANALYZE_RESULTS.md prompt for post-run analysis.

    Args:
        results_dir: Results directory
        config: Configuration dict

    """
    prompt_path = results_dir / "ANALYZE_RESULTS.md"

    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    content = f"""# E2E Dry Run Analysis

## Task
Analyze the results of running all 47 E2E tests and file summaries to GitHub.

## Configuration
- Date: {date}
- Model: {config['model']} | Judge: {config['judge_model']} | Runs: {config['runs']} | Max Subtests: {config['max_subtests']} | Thinking: {config['thinking']}
- Tiers: {', '.join(config['tiers'])}
- Results directory: {results_dir}/

## What to Do

### 1. Read the batch summary
Read `{results_dir}/batch_summary.json` for the structured results of all 47 tests.

### 2. Create a GitHub tracking epic
Create an issue titled "E2E Dry Run: All 47 Tests (Haiku, {date})" with label "evaluation".
Include a summary table of all test results in the body.

Example table format:
```markdown
| Test ID | Status | Best Tier | Score | CoP ($) | Cost ($) | Duration (s) |
|---------|--------|-----------|-------|---------|----------|--------------|
| test-001 | PASS | T0 | 1.00 | 0.0165 | 0.48 | 273 |
| test-002 | FAIL | T1 | 0.45 | 2.22 | 1.24 | 450 |
| ... | ... | ... | ... | ... | ... | ... |
```

### 3. For each test, create a linked GitHub issue
For each test in the batch summary, create an issue:
- Title: `[E2E] {{test_id}}: {{name}} - {{PASS/FAIL/ERROR}}`
- Label: `evaluation`
- Body should include:
  - Status and overall result
  - Configuration (model, runs, tiers tested)
  - Best tier and frontier CoP
  - Total cost and duration
  - Link to results directory: `{results_dir}/{{timestamp}}-{{test_id}}/`
  - Any errors encountered
  - Next steps (if failed)

Use the gh CLI to create issues:
```bash
gh issue create \\
  --title "[E2E] test-001: Example Test - PASS" \\
  --body "..." \\
  --label "evaluation"
```

### 4. Link per-test issues to the epic
Reference each per-test issue in the epic body using "Closes #N" or "Related: #N" syntax.

### 5. Identify and analyze failures
For any test that failed or errored:
- Read the thread log: `{results_dir}/thread_logs/thread_N.log`
- Check the result directory for partial results
- Determine if it's a framework bug, model issue, or test fixture problem
- Document findings in the per-test issue
- Consider creating separate bug reports for framework issues

### 6. Post final analysis
Post a final comment on the epic with:
- Overall pass/fail statistics (e.g., "42/47 passed (89%)")
- Common failure patterns (e.g., "5 tests timed out", "3 tests failed rubric criteria")
- Framework bugs identified (link to bug issues)
- Model performance observations
- Recommendations for next steps

## Files to Read
- `{results_dir}/batch_summary.json` — All results in structured format
- `{results_dir}/thread_logs/thread_*.log` — Per-thread execution logs with full output
- `{results_dir}/{{timestamp}}-test-XXX/report.json` — Per-test detailed results
- `{results_dir}/{{timestamp}}-test-XXX/report.md` — Per-test markdown reports

## Example Issue Body Template

```markdown
# Test: {{name}}

**Status**: {{PASS/FAIL/ERROR}}

## Configuration
- Model: {config['model']}
- Judge: {config['judge_model']}
- Runs: {config['runs']}
- Max Subtests: {config['max_subtests']}
- Thinking: {config['thinking']}
- Tiers: {', '.join(config['tiers'])}

## Results
- Best Tier: {{best_tier}}
- Best Score: {{best_score}}
- Frontier CoP: ${{frontier_cop}}
- Total Cost: ${{total_cost}}
- Total Duration: {{total_duration}}s

## Details
Results directory: `{results_dir}/{{timestamp}}-{{test_id}}/`

{{Additional details from report.json or logs}}

## Next Steps
{{For failures: investigation needed, fix required, etc.}}
{{For passes: verification, production deployment, etc.}}
```

## Workflow Example

```bash
# 1. Read batch summary
cat {results_dir}/batch_summary.json

# 2. Create epic
gh issue create \\
  --title "E2E Dry Run: All 47 Tests (Haiku, {date})" \\
  --label "evaluation" \\
  --body "Full dry run results..."

# 3. Create per-test issues (repeat for each test)
gh issue create \\
  --title "[E2E] test-001: ... - PASS" \\
  --label "evaluation" \\
  --body "..."

# 4. Update epic with links
gh issue comment <epic-number> --body "Per-test issues: #N1, #N2, ..."

# 5. Analyze failures
for thread_log in {results_dir}/thread_logs/*.log; do
  # Review logs for errors
  grep -i error "$thread_log"
done

# 6. Post final analysis
gh issue comment <epic-number> --body "Final analysis: ..."
```
"""

    with open(prompt_path, "w") as f:
        f.write(content)

    logger.info(f"Wrote analysis prompt to {prompt_path}")


def print_summary_table(all_results: list[dict]) -> None:
    """Print colored summary table to stdout.

    Args:
        all_results: List of all result dicts

    """
    print(f"\n{Colors.BOLD}{'=' * 100}{Colors.ENDC}")
    print(f"{Colors.BOLD}Batch Run Summary{Colors.ENDC}")
    print(f"{Colors.BOLD}{'=' * 100}{Colors.ENDC}\n")

    # Header
    print(
        f"{Colors.BOLD}{'Test ID':<12} {'Status':<8} {'Best Tier':<10} "
        f"{'Score':<8} {'CoP ($)':<10} {'Cost ($)':<10} {'Duration (s)':<12}{Colors.ENDC}"
    )
    print("-" * 100)

    # Results
    for result in sorted(all_results, key=lambda r: r["test_id"]):
        test_id = result["test_id"]
        status = result["status"].upper()
        best_tier = result.get("best_tier", "N/A")
        best_score = result.get("best_score", 0.0)
        frontier_cop = result.get("frontier_cop", float("inf"))
        total_cost = result.get("total_cost", 0.0)
        total_duration = result.get("total_duration", 0.0)

        # Color code status
        if status == "PASS":
            status_colored = f"{Colors.OKGREEN}{status}{Colors.ENDC}"
        elif status == "FAIL":
            status_colored = f"{Colors.WARNING}{status}{Colors.ENDC}"
        else:
            status_colored = f"{Colors.FAIL}{status}{Colors.ENDC}"

        # Format values
        score_str = f"{best_score:.2f}" if best_score > 0 else "N/A"
        cop_str = f"{frontier_cop:.4f}" if frontier_cop != float("inf") else "N/A"
        cost_str = f"{total_cost:.4f}" if total_cost > 0 else "N/A"
        duration_str = f"{total_duration:.0f}" if total_duration > 0 else "N/A"

        print(
            f"{test_id:<12} {status_colored:<16} {best_tier:<10} "
            f"{score_str:<8} {cop_str:<10} {cost_str:<10} {duration_str:<12}"
        )

    print(f"\n{Colors.BOLD}{'=' * 100}{Colors.ENDC}")

    # Statistics
    total = len(all_results)
    passed = len([r for r in all_results if r["status"] == "pass"])
    failed = len([r for r in all_results if r["status"] == "fail"])
    errored = len([r for r in all_results if r["status"] == "error"])

    print(f"\n{Colors.BOLD}Statistics:{Colors.ENDC}")
    print(f"  Total:   {total}")
    print(f"  {Colors.OKGREEN}Passed:  {passed} ({100 * passed / total:.1f}%){Colors.ENDC}")
    print(f"  {Colors.WARNING}Failed:  {failed} ({100 * failed / total:.1f}%){Colors.ENDC}")
    print(f"  {Colors.FAIL}Errored: {errored} ({100 * errored / total:.1f}%){Colors.ENDC}")
    print()


def main() -> int:
    """Run batch E2E experiments.

    Returns:
        Exit code (0 for success, 1 for error)

    """
    parser = argparse.ArgumentParser(
        description="Run all E2E tests in parallel across multiple threads",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run all tests with defaults (4 threads, haiku, T0-T6, 1 run, 2 subtests)
    python scripts/run_e2e_batch.py

    # Run specific tests
    python scripts/run_e2e_batch.py --tests test-001 test-005 test-010

    # Run with 8 threads
    python scripts/run_e2e_batch.py --threads 8

    # Run with sonnet instead of haiku
    python scripts/run_e2e_batch.py --model sonnet --judge-model sonnet

    # Run only T0 and T1 tiers
    python scripts/run_e2e_batch.py --tiers T0 T1
        """,
    )

    parser.add_argument(
        "--results-dir",
        type=Path,
        default=DEFAULT_RESULTS_DIR,
        help=f"Results directory (default: {DEFAULT_RESULTS_DIR})",
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=DEFAULT_NUM_THREADS,
        help=f"Number of parallel threads (default: {DEFAULT_NUM_THREADS})",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Model for task execution (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--judge-model",
        default=DEFAULT_JUDGE_MODEL,
        help=f"Model for judging (default: {DEFAULT_JUDGE_MODEL})",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=DEFAULT_RUNS,
        help=f"Runs per subtest (default: {DEFAULT_RUNS})",
    )
    parser.add_argument(
        "--max-subtests",
        type=int,
        default=DEFAULT_MAX_SUBTESTS,
        help=f"Max subtests per tier (default: {DEFAULT_MAX_SUBTESTS})",
    )
    parser.add_argument(
        "--tiers",
        nargs="+",
        default=DEFAULT_TIERS,
        help=f"Tiers to run (default: {' '.join(DEFAULT_TIERS)})",
    )
    parser.add_argument(
        "--thinking",
        choices=["None", "Low", "High", "UltraThink"],
        default="None",
        help="Thinking mode for agent execution (default: None)",
    )
    parser.add_argument(
        "--tests",
        nargs="*",
        help="Specific test IDs to run (default: all tests)",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Start fresh, clear batch_summary.json and restart all tests (default: auto-resume)",
    )
    parser.add_argument(
        "--retry-errors",
        action="store_true",
        help="Re-run tests that previously ended with status='error' (default: skip errors)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    # Configure logging
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Create results directory and subdirectories
    args.results_dir.mkdir(parents=True, exist_ok=True)
    log_dir = args.results_dir / "thread_logs"
    log_dir.mkdir(exist_ok=True)

    # Record configuration
    config = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "model": args.model,
        "judge_model": args.judge_model,
        "runs": args.runs,
        "max_subtests": args.max_subtests,
        "thinking": args.thinking,
        "tiers": args.tiers,
        "threads": args.threads,
    }

    try:
        # 0. Check for rate limits before starting
        is_rate_limited, rate_msg = check_rate_limit()
        if is_rate_limited:
            logger.error(f"API is currently rate-limited: {rate_msg}")
            print(f"\n{Colors.FAIL}⏸️  {rate_msg}{Colors.ENDC}\n")
            print("Please wait for the rate limit to expire and re-run this script.")
            print("The batch runner will auto-resume from where it left off.\n")
            return 2  # Distinct exit code for rate limit

        # 1. Load existing results (unless --fresh)
        existing_results = []
        if args.fresh:
            # Clear existing batch_summary.json
            summary_path = args.results_dir / "batch_summary.json"
            if summary_path.exists():
                summary_path.unlink()
                logger.info("Cleared existing batch_summary.json (--fresh mode)")
        else:
            existing_results = load_existing_results(args.results_dir)

        # Build set of completed test IDs to skip
        completed_test_ids = set()
        for result in existing_results:
            # Skip if status is not "error", OR if status is "error" but --retry-errors is not set
            if result["status"] != "error" or not args.retry_errors:
                completed_test_ids.add(result["test_id"])

        # If --retry-errors, remove error entries from existing_results
        if args.retry_errors:
            existing_results = [r for r in existing_results if r["status"] != "error"]

        # 2. Discover tests
        repo_root = get_repo_root()
        tests_dir = repo_root / "tests" / "fixtures" / "tests"
        all_tests = discover_tests(tests_dir, args.tests)

        if not all_tests:
            logger.error("No tests found to run")
            return 1

        # Filter out completed tests
        tests = [t for t in all_tests if t["id"] not in completed_test_ids]

        if not tests:
            logger.info(f"All {len(all_tests)} tests already completed. Nothing to run.")
            print(f"\n{Colors.OKGREEN}✓ All tests already completed!{Colors.ENDC}")
            print(f"  Skipped: {len(completed_test_ids)} tests")
            print(f"  Use --fresh to restart from scratch, or --retry-errors to retry failed tests.\n")
            return 0

        # Log resume info
        if completed_test_ids:
            logger.info(f"Resuming batch run:")
            logger.info(f"  Total tests: {len(all_tests)}")
            logger.info(f"  Already completed: {len(completed_test_ids)}")
            logger.info(f"  To run: {len(tests)}")
            print(f"\n{Colors.BOLD}Resuming batch run:{Colors.ENDC}")
            print(f"  Total tests: {len(all_tests)}")
            print(f"  {Colors.OKGREEN}Already completed: {len(completed_test_ids)}{Colors.ENDC}")
            print(f"  To run: {len(tests)}\n")

        # 3. Partition across threads
        threads = partition_tests(tests, args.threads)

        # 4. Run tests in parallel
        logger.info(f"Starting {len(tests)} tests across {args.threads} threads")
        print(f"\n{Colors.BOLD}Running {len(tests)} tests...{Colors.ENDC}\n")

        new_results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.threads) as executor:
            # Submit all threads
            futures = [
                executor.submit(run_thread, i, thread_tests, log_dir, args, config)
                for i, thread_tests in enumerate(threads)
            ]

            # Collect results as they complete
            for future in concurrent.futures.as_completed(futures):
                try:
                    results = future.result()
                    new_results.extend(results)
                except Exception as e:
                    logger.error(f"Thread failed with exception: {e}")

        # 5. Merge existing and new results
        all_results = existing_results + new_results

        # 6. Write final outputs
        logger.info("Writing final batch summary and analysis prompt")
        write_batch_summary(args.results_dir, all_results, config, threads)
        write_analysis_prompt(args.results_dir, config)

        # 5. Print summary
        print_summary_table(all_results)

        # Final output locations
        print(f"{Colors.BOLD}Output Files:{Colors.ENDC}")
        print(f"  Batch Summary:    {args.results_dir}/batch_summary.json")
        print(f"  Analysis Prompt:  {args.results_dir}/ANALYZE_RESULTS.md")
        print(f"  Thread Logs:      {args.results_dir}/thread_logs/thread_*.log")
        print(f"  Result Dirs:      {args.results_dir}/*-test-*/")
        print()

        return 0

    except KeyboardInterrupt:
        logger.warning("Batch run interrupted by user")
        return 130

    except Exception as e:
        logger.exception(f"Batch run failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
