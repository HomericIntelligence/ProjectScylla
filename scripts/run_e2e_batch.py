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
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, cast

# Add scripts/ to path for common utilities
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from common import Colors, get_repo_root

from scylla.e2e.models import TestFixture
from scylla.e2e.rate_limit import check_api_rate_limit_status
from scylla.utils.terminal import restore_terminal

# Defaults (overridable via CLI args)
DEFAULT_RESULTS_DIR = Path.home() / "dryrun"
DEFAULT_NUM_THREADS = 4
DEFAULT_MODEL = "haiku"
DEFAULT_JUDGE_MODEL = "haiku"
DEFAULT_RUNS = 3
DEFAULT_MAX_SUBTESTS = 0  # 0 = no limit (all subtests)
DEFAULT_TIERS = ["T0", "T1", "T2", "T3", "T4", "T5", "T6"]


def format_duration(seconds: float) -> str:
    """Convert seconds to human-readable duration string.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted string like "5m 23s" or "2h 14m" or "N/A" for 0/None

    """
    if not seconds or seconds <= 0:
        return "N/A"

    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if hours > 0:
        return f"{hours}h {minutes}m"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    else:
        return f"{secs}s"


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Thread-safe lock for incremental saves
_save_lock = threading.Lock()


def load_existing_results(results_dir: Path) -> list[dict[str, Any]]:
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
        return cast(list[dict[Any, Any]], results)
    except Exception as e:
        logger.warning(f"Failed to load existing results from {summary_path}: {e}")
        return []


def save_incremental_result(
    results_dir: Path, result: dict[str, Any], config: dict[str, Any]
) -> None:
    """Save a single result incrementally to batch_summary.json.

    Loads existing summary, appends the new result, and writes atomically.
    Thread-safe using a lock to prevent race conditions.

    Args:
        results_dir: Results directory
        result: Single test result dict to append
        config: Configuration dict

    """
    summary_path = results_dir / "batch_summary.json"
    # Use thread-specific temp file to prevent race conditions
    tmp_path = results_dir / f"batch_summary.json.tmp.{threading.get_ident()}"

    # Use lock to prevent concurrent read-modify-write cycles
    with _save_lock:
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


def discover_tests(tests_dir: Path, test_filter: list[str] | None = None) -> list[dict[str, Any]]:
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
            logger.debug(f"Found {test_id}: {fixture.name} (timeout: {fixture.timeout_seconds}s)")
        except Exception as e:
            logger.warning(f"Failed to load test {test_id}: {e}")
            continue

    logger.info(f"Discovered {len(tests)} tests")
    return tests


def partition_tests(tests: list[dict[str, Any]], num_threads: int) -> list[list[dict[str, Any]]]:
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
    threads: list[list[dict[str, Any]]] = [[] for _ in range(num_threads)]
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
            f"Thread {i}: {len(thread_tests)} tests, ~{total_time}s ({total_time / 3600:.1f}h)"
        )

    return threads


def run_single_test(
    test: dict[str, Any],
    thread_id: int,
    log_file: Any,
    args: argparse.Namespace,
    config: dict[str, Any],
    pixi_path: str,
) -> dict[str, Any]:
    """Run one test via subprocess, capture output to log file.

    Args:
        test: Test metadata dict
        thread_id: Thread ID for logging
        log_file: Open file handle for logging
        args: Parsed CLI arguments
        config: Configuration dict for incremental saves
        pixi_path: Full path to pixi executable

    Returns:
        Result dict with status, metrics, and paths

    """
    test_id = test["id"]
    logger.info(f"[Thread {thread_id}] Starting {test_id}")

    # Build command (conditionally add --fresh)
    cmd = [
        pixi_path,
        "run",
        "python",
        "scripts/manage_experiment.py",
        "run",
        "--tiers-dir",
        str(test["path"]),
        "--tiers",
        *args.tiers,
        "--runs",
        str(args.runs),
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
    if args.max_subtests > 0:
        cmd.extend(["--max-subtests", str(args.max_subtests)])

    # Write command to log
    log_file.write(f"\n{'=' * 70}\n")
    log_file.write(f"[{datetime.now(timezone.utc).isoformat()}] Starting {test_id}\n")
    log_file.write(f"Command: {' '.join(cmd)}\n")
    log_file.write(f"{'=' * 70}\n\n")
    log_file.flush()

    # Run subprocess
    start_time = datetime.now(timezone.utc)
    try:
        proc = subprocess.run(
            cmd,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
            check=False,  # Don't raise on error
        )
        exit_code = proc.returncode
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
        score = metrics.get("best_score") or 0.0
        status = "pass" if score > 0.5 else "fail"
    elif exit_code == 0:
        status = "unknown"
    else:
        status = "error"

    logger.info(f"[Thread {thread_id}] Completed {test_id}: {status.upper()}")

    result = {
        "test_id": test_id,
        "test_name": test.get("name", ""),
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


def run_thread(
    thread_id: int,
    tests: list[dict[str, Any]],
    log_dir: Path,
    args: argparse.Namespace,
    config: dict[str, Any],
    pixi_path: str,
) -> list[dict[str, Any]]:
    """Run all assigned tests sequentially within one thread.

    Args:
        thread_id: Thread ID
        tests: List of tests assigned to this thread
        log_dir: Directory for log files
        args: Parsed CLI arguments
        config: Configuration dict for incremental saves
        pixi_path: Full path to pixi executable

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
            try:
                result = run_single_test(test, thread_id, log_file, args, config, pixi_path)
                results.append(result)
            except Exception as e:
                logger.error(f"[Thread {thread_id}] Unexpected error for {test['id']}: {e}")
                # Record error result
                error_result = {
                    "test_id": test["id"],
                    "test_name": test.get("name", ""),
                    "thread_id": thread_id,
                    "status": "error",
                    "exit_code": -1,
                    "result_dir": None,
                    "error": str(e),
                }
                results.append(error_result)
                # Log to file
                log_file.write(f"\nUNEXPECTED ERROR: {e}\n")
                log_file.flush()

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


def extract_metrics(result_dir: Path) -> dict[str, Any] | None:
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

        # Read from nested structure: report["summary"] and report["children"]
        summary = report.get("summary", {})
        best_tier = summary.get("best_tier")
        best_score = 0.0
        if best_tier:
            for child in report.get("children", []):
                if child.get("tier") == best_tier:
                    best_score = child.get("best_score", 0.0) or 0.0
                    break

        return {
            "best_tier": best_tier,
            "best_score": best_score,
            "frontier_cop": summary.get("frontier_cop"),
            "total_cost": summary.get("total_cost", 0.0),
            "total_duration": summary.get("total_duration", 0.0),
        }
    except Exception as e:
        logger.warning(f"Failed to extract metrics from {report_path}: {e}")
        return None


def write_batch_summary(
    results_dir: Path,
    all_results: list[dict[str, Any]],
    config: dict[str, Any],
    threads: list[list[dict[str, Any]]],
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


def write_analysis_prompt(results_dir: Path, config: dict[str, Any]) -> None:
    """Write ANALYZE_RESULTS.md prompt for post-run analysis.

    Args:
        results_dir: Results directory
        config: Configuration dict

    """
    prompt_path = results_dir / "ANALYZE_RESULTS.md"

    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    tiers_str = "-".join(config["tiers"])
    run_name = f"{config['model']}-{tiers_str}-{date}"

    content = f"""# E2E Batch Run Analysis

## Task
Analyze the results of running all 47 E2E tests and write comprehensive reports to
`docs/runs/{run_name}/`.

## Configuration
- Date: {date}
- Model: {config["model"]} | Judge: {config["judge_model"]} | Runs: {config["runs"]}
- Max Subtests: {config["max_subtests"]} | Thinking: {config["thinking"]}
- Tiers: {", ".join(config["tiers"])}
- Results directory: {results_dir}/
- Output directory: docs/runs/{run_name}/

## What to Do

### Step 1: Read the batch summary
Read `{results_dir}/batch_summary.json` for the structured results of all 47 tests.

### Step 2: Create output directory and write master summary
Create the output directory structure:
```bash
mkdir -p docs/runs/{run_name}/failures
```

Write `docs/runs/{run_name}/README.md` containing:

#### Configuration Section
```markdown
# E2E Batch Run: {run_name}

**Configuration:**
- Date: {date}
- Model: {config["model"]}
- Judge: {config["judge_model"]}
- Runs per test: {config["runs"]}
- Max Subtests: {config["max_subtests"]}
- Extended Thinking: {config["thinking"]}
- Tiers Tested: {", ".join(config["tiers"])}
```

#### Aggregate Statistics Section
Calculate and include:
- Overall pass rate (e.g., "42/47 passed (89.4%)")
- Total cost across all tests
- Total duration
- Mean Cost-of-Pass (CoP) for passing tests
- Median CoP
- Min/Max CoP

#### Full Results Table
Create a comprehensive table sorted by test_id with columns:
- Test ID
- Name
- Status (PASS/FAIL/ERROR)
- Best Tier
- Best Score
- CoP ($)
- Total Cost ($)
- Total Duration (s)

#### Links Section
- Link to each test's existing `report.md` in the results directory:
  `{results_dir}/{{timestamp}}-{{test_id}}/report.md`
- Link to `failures/README.md` for failure analysis
- Link to `analysis.md` for detailed findings

### Step 3: Analyze failures and write failure reports
For each failed or errored test:

1. Read the thread log: `{results_dir}/thread_logs/thread_N.log`
2. Read the test results: `{results_dir}/{{timestamp}}-{{test_id}}/report.json`
3. Determine root cause and categorize:
   - **Framework bug**: Test harness, executor, or infrastructure issue
   - **Model limitation**: Model unable to solve task despite framework working correctly
   - **Test fixture issue**: Test definition, rubric, or setup problem
   - **Zero-cost instant-fail**: Test failed immediately without agent execution (cost = $0)

4. Write `docs/runs/{run_name}/failures/{{test_id}}.md`:
```markdown
# Failure Analysis: {{test_id}} - {{name}}

**Status**: {{FAIL/ERROR}}
**Category**: {{Framework Bug/Model Limitation/Test Fixture Issue/Zero-Cost Instant-Fail}}

## Results
- Best Subtest Score: {{best_score}} (threshold: {{pass_threshold}})
- Total Token Usage: {{total_tokens}}
- Total Cost: ${{total_cost}}
- Total Duration: {{duration}}s

## Root Cause
{{Detailed analysis from thread logs and results}}

## Relevant Errors
{{Error messages from logs, if any}}

## Recommendations
{{Next steps: fix framework, adjust rubric, investigate model behavior, etc.}}
```

5. Write `docs/runs/{run_name}/failures/README.md`:
```markdown
# Failure Analysis Summary

**Total Failures**: {{num_failures}}/47

## Summary Table
| Test ID | Name | Category | Best Score | Cost ($) |
|---------|------|----------|------------|----------|
| ... | ... | ... | ... | ... |

## Failure Categories

### Framework Bugs ({{count}})
{{List of framework-related failures}}

### Model Limitations ({{count}})
{{List of model capability failures}}

### Test Fixture Issues ({{count}})
{{List of test definition problems}}

### Zero-Cost Instant-Fails ({{count}})
{{List of tests that failed without execution}}

## Common Patterns
{{Identify recurring failure modes across tests}}
```

### Step 4: Write final analysis
Write `docs/runs/{run_name}/analysis.md`:

```markdown
# Final Analysis: {run_name}

## Overall Statistics

### Pass/Fail Breakdown
- **Passed**: {{num_pass}}/47 ({{pass_rate}}%)
- **Failed**: {{num_fail}}/47 ({{fail_rate}}%)
- **Errors**: {{num_error}}/47 ({{error_rate}}%)

### Cost Analysis
- **Total Cost**: ${{total_cost}}
- **Mean CoP**: ${{mean_cop}} (passing tests only)
- **Median CoP**: ${{median_cop}}
- **Min CoP**: ${{min_cop}} ({{test_id}})
- **Max CoP**: ${{max_cop}} ({{test_id}})

### Duration Analysis
- **Total Duration**: {{total_duration}}s ({{hours}}h {{minutes}}m)
- **Mean Duration**: {{mean_duration}}s per test
- **Median Duration**: {{median_duration}}s

## Failure Analysis

### Common Failure Patterns
{{Categorized patterns from failures/README.md}}

### Zero-Cost Failures
**Count**: {{zero_cost_count}}
{{Analysis of tests that failed instantly without agent execution - likely framework bugs}}

## Model Performance Observations
{{Observations about model behavior:}}
- Tier performance comparison
- Common model errors or limitations
- Success patterns in passing tests

## Recommendations

### Framework Improvements
{{Based on framework bugs identified}}

### Test Fixture Updates
{{Based on test definition issues}}

### Future Evaluation
{{Suggestions for next batch runs: different tiers, models, configurations}}
```

### Step 5: Run the analysis pipeline
Execute the existing data analysis and visualization pipeline:

```bash
pixi run python scripts/generate_all_results.py \\
  --data-dir {results_dir} \\
  --output-dir docs/runs/{run_name} \\
  --no-render
```

This will generate:
- `docs/runs/{run_name}/data/runs.csv` - Run-level data
- `docs/runs/{run_name}/data/judges.csv` - Judge-level data
- `docs/runs/{run_name}/data/criteria.csv` - Criteria-level data
- `docs/runs/{run_name}/data/subtests.csv` - Subtest-level data
- `docs/runs/{run_name}/data/summary.json` - Aggregated statistics
- `docs/runs/{run_name}/data/statistical_results.json` - Statistical analysis
- `docs/runs/{run_name}/figures/*.vl.json` - Vega-Lite figure specifications
- `docs/runs/{run_name}/figures/*.csv` - Figure data files
- `docs/runs/{run_name}/tables/*.md` - Markdown tables
- `docs/runs/{run_name}/tables/*.tex` - LaTeX tables

## Final Output Structure

```
docs/runs/{run_name}/
├── README.md              # Master summary (epic equivalent)
├── analysis.md            # Final analysis with statistics & recommendations
├── failures/
│   ├── README.md          # Failure analysis summary
│   └── test-XXX.md        # Per-failed-test root cause analysis
├── data/                  # From generate_all_results.py
│   ├── runs.csv
│   ├── judges.csv
│   ├── criteria.csv
│   ├── subtests.csv
│   ├── summary.json
│   └── statistical_results.json
├── figures/               # From generate_all_results.py
│   └── *.vl.json, *.csv
└── tables/                # From generate_all_results.py
    └── *.md, *.tex
```

## Files to Read
- `{results_dir}/batch_summary.json` — All results in structured format
- `{results_dir}/thread_logs/thread_*.log` — Per-thread execution logs
- `{results_dir}/{{timestamp}}-test-XXX/report.json` — Per-test detailed results
- `{results_dir}/{{timestamp}}-test-XXX/report.md` — Per-test markdown reports
  (link to these, don't copy)

## Important Notes
- **No GitHub interaction** - All outputs are files, no `gh issue create` or
  `gh issue comment` commands
- **Only failures get dedicated files** - Passing tests are referenced via links
  to existing `report.md`
- **Zero-cost failures** - Pay special attention to tests that failed immediately
  (cost = $0) as these indicate framework bugs
- **Versionable output** - All reports are committed to git for historical tracking
- **Complete pipeline** - Run `generate_all_results.py` to produce CSVs, figures,
  and tables alongside narrative reports
"""

    with open(prompt_path, "w") as f:
        f.write(content)

    logger.info(f"Wrote analysis prompt to {prompt_path}")


def print_summary_table(all_results: list[dict[str, Any]]) -> None:
    """Print colored summary table to stdout.

    Args:
        all_results: List of all result dicts

    """
    print(f"\n{Colors.BOLD}{'=' * 120}{Colors.ENDC}")
    print(f"{Colors.BOLD}Batch Run Summary{Colors.ENDC}")
    print(f"{Colors.BOLD}{'=' * 120}{Colors.ENDC}\n")

    # Header
    print(
        f"{Colors.BOLD}{'Test ID':<12} {'Name':<28} {'Status':<8} {'Best Tier':<10} "
        f"{'Score':<8} {'CoP ($)':<10} {'Cost ($)':<10} {'Duration':<12}{Colors.ENDC}"
    )
    print("-" * 120)

    # Results
    for result in sorted(all_results, key=lambda r: r["test_id"]):
        test_id = result["test_id"]
        test_name = result.get("test_name", "")
        # Truncate name to 28 chars
        if len(test_name) > 28:
            test_name = test_name[:25] + "..."
        status = result["status"].upper()
        best_tier = result.get("best_tier") or "N/A"
        best_score = result.get("best_score") or 0.0
        frontier_cop = result.get("frontier_cop")
        total_cost = result.get("total_cost") or 0.0
        total_duration = result.get("total_duration") or 0.0

        # Color code status
        if status == "PASS":
            status_colored = f"{Colors.OKGREEN}{status}{Colors.ENDC}"
        elif status == "FAIL":
            status_colored = f"{Colors.WARNING}{status}{Colors.ENDC}"
        else:
            status_colored = f"{Colors.FAIL}{status}{Colors.ENDC}"

        # Format values
        score_str = f"{best_score:.2f}" if best_score > 0 else "N/A"
        cop_str = f"${frontier_cop:.4f}" if frontier_cop is not None else "N/A"
        cost_str = f"${total_cost:.4f}" if total_cost > 0 else "N/A"
        duration_str = format_duration(total_duration)

        print(
            f"{test_id:<12} {test_name:<28} {status_colored:<16} {best_tier:<10} "
            f"{score_str:<8} {cop_str:<10} {cost_str:<10} {duration_str:<12}"
        )

    print(f"\n{Colors.BOLD}{'=' * 120}{Colors.ENDC}")

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

    # Aggregate metrics
    total_cost_sum = sum(r.get("total_cost", 0) or 0 for r in all_results)
    avg_cost = total_cost_sum / total if total > 0 else 0
    total_duration_sum = sum(r.get("total_duration", 0) or 0 for r in all_results)

    print(f"\n{Colors.BOLD}Aggregate Metrics:{Colors.ENDC}")
    print(f"  Total cost:       ${total_cost_sum:.4f}")
    print(f"  Average cost:     ${avg_cost:.4f}")
    print(f"  Total duration:   {format_duration(total_duration_sum)}")
    print()


def main(argv: list[str] | None = None) -> int:  # noqa: C901  # CLI main with multiple batch modes
    """Run batch E2E experiments.

    Args:
        argv: Optional argument list (defaults to sys.argv[1:] if None)

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
        help="Max subtests per tier (default: 0 = no limit, run all)",
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

    args = parser.parse_args(argv)

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

    batch_start_time = time.time()

    try:
        # 0. Resolve pixi executable path
        pixi_path = shutil.which("pixi")
        if pixi_path is None:
            logger.error("pixi not found on PATH. Install pixi or add ~/.pixi/bin to PATH")
            print(f"\n{Colors.FAIL}ERROR: pixi not found on PATH{Colors.ENDC}\n")
            print("Please ensure pixi is installed and available:")
            print("  1. Install pixi: curl -fsSL https://pixi.sh/install.sh | bash")
            print('  2. Add to PATH: export PATH="$HOME/.pixi/bin:$PATH"')
            print()
            return 1

        logger.info(f"Using pixi from: {pixi_path}")

        # 1. Check for rate limits before starting
        is_rate_limited, rate_msg = check_rate_limit()
        if is_rate_limited:
            logger.error(f"API is currently rate-limited: {rate_msg}")
            print(f"\n{Colors.FAIL}⏸️  {rate_msg}{Colors.ENDC}\n")
            print("Please wait for the rate limit to expire and re-run this script.")
            print("The batch runner will auto-resume from where it left off.\n")
            return 2  # Distinct exit code for rate limit

        # 2. Load existing results (unless --fresh)
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

        # 3. Discover tests
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
            print(
                "  Use --fresh to restart from scratch, or --retry-errors to retry failed tests.\n"
            )
            return 0

        # Log resume info
        if completed_test_ids:
            logger.info("Resuming batch run:")
            logger.info(f"  Total tests: {len(all_tests)}")
            logger.info(f"  Already completed: {len(completed_test_ids)}")
            logger.info(f"  To run: {len(tests)}")
            print(f"\n{Colors.BOLD}Resuming batch run:{Colors.ENDC}")
            print(f"  Total tests: {len(all_tests)}")
            print(f"  {Colors.OKGREEN}Already completed: {len(completed_test_ids)}{Colors.ENDC}")
            print(f"  To run: {len(tests)}\n")

        # 4. Partition across threads
        threads = partition_tests(tests, args.threads)

        # 5. Run tests in parallel
        logger.info(f"Starting {len(tests)} tests across {args.threads} threads")
        print(f"\n{Colors.BOLD}Running {len(tests)} tests...{Colors.ENDC}\n")

        new_results = []
        completed_count = 0
        total_tests = len(tests)

        with concurrent.futures.ThreadPoolExecutor(max_workers=args.threads) as executor:
            # Submit all threads
            futures = [
                executor.submit(run_thread, i, thread_tests, log_dir, args, config, pixi_path)
                for i, thread_tests in enumerate(threads)
            ]

            # Collect results as they complete
            for future in concurrent.futures.as_completed(futures):
                try:
                    results = future.result()
                    new_results.extend(results)
                    completed_count += len(results)

                    # Print progress
                    elapsed = time.time() - batch_start_time
                    progress_pct = (
                        int(100 * completed_count / total_tests) if total_tests > 0 else 0
                    )
                    print(
                        f"  Progress: {completed_count}/{total_tests} tests "
                        f"({progress_pct}%) - Elapsed: {format_duration(elapsed)}"
                    )
                except Exception as e:
                    logger.error(f"Thread failed with exception: {e}")

        # 6. Merge existing and new results
        all_results = existing_results + new_results

        # 7. Write final outputs
        logger.info("Writing final batch summary and analysis prompt")
        write_batch_summary(args.results_dir, all_results, config, threads)
        write_analysis_prompt(args.results_dir, config)

        # 8. Print summary
        print_summary_table(all_results)

        # Final output locations
        print(f"{Colors.BOLD}Output Files:{Colors.ENDC}")
        print(f"  Batch Summary:    {args.results_dir}/batch_summary.json")
        print(f"  Analysis Prompt:  {args.results_dir}/ANALYZE_RESULTS.md")
        print(f"  Thread Logs:      {args.results_dir}/thread_logs/thread_*.log")
        print(f"  Result Dirs:      {args.results_dir}/*-test-*/")
        print()

        # What to do next
        print(f"{Colors.BOLD}What to Do Next:{Colors.ENDC}")
        print(f"  1. Review results:  less {args.results_dir}/batch_summary.json")
        print(f"  2. Analyze with AI: Follow the prompt in {args.results_dir}/ANALYZE_RESULTS.md")
        print(f"  3. Check failures:  Look at {args.results_dir}/thread_logs/ for error details")
        print("  4. Retry errors:    python scripts/run_e2e_batch.py --retry-errors")
        print()

        return 0

    except KeyboardInterrupt:
        logger.warning("Batch run interrupted by user")
        return 130

    except Exception as e:
        logger.exception(f"Batch run failed: {e}")
        return 1

    finally:
        # Always restore terminal on exit
        restore_terminal()


if __name__ == "__main__":
    sys.exit(main())
