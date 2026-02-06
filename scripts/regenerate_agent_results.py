#!/usr/bin/env python3
"""Regenerate agent/result.json files from existing logs.

This script scans run directories for completed agents that are missing
agent/result.json and regenerates them from the existing logs (stdout.log,
stderr.log, command_log.json).

Related Scripts:
  - rerun_agents.py: Re-run failed agents (re-execution, not just rebuild)
  - See scripts/README.md for complete recovery script reference

Usage:
    pixi run python scripts/regenerate_agent_results.py /path/to/experiment/

Python Justification: File I/O, JSON parsing, and data extraction from logs.
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def regenerate_agent_result(agent_dir: Path) -> bool:
    """Regenerate agent/result.json from existing logs.

    Args:
        agent_dir: Path to agent directory

    Returns:
        True if regenerated successfully, False otherwise

    """
    result_file = agent_dir / "result.json"
    if result_file.exists():
        return False  # Already exists

    # Check if we have the required files
    stdout_file = agent_dir / "stdout.log"
    stderr_file = agent_dir / "stderr.log"
    command_log_file = agent_dir / "command_log.json"

    if not all([stdout_file.exists(), stderr_file.exists(), command_log_file.exists()]):
        logger.warning(f"Missing required files in {agent_dir}")
        return False

    try:
        # Read files
        stdout = stdout_file.read_text()
        stderr = stderr_file.read_text()

        with open(command_log_file) as f:
            cmd_log = json.load(f)

        # Parse Claude Code JSON output to extract token stats and cost
        stdout_json = json.loads(stdout.strip())

        # Extract token stats from usage field
        usage = stdout_json.get("usage", {})

        # Build token_stats structure
        token_stats = {
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "cache_creation_input_tokens": usage.get("cache_creation_input_tokens", 0),
            "cache_read_input_tokens": usage.get("cache_read_input_tokens", 0),
        }

        # Extract cost
        cost_usd = stdout_json.get("total_cost_usd", 0.0)

        # Get exit code from command log
        exit_code = cmd_log["commands"][0]["exit_code"]

        # Build result.json structure
        result_data = {
            "exit_code": exit_code,
            "stdout": stdout,
            "stderr": stderr,
            "token_stats": token_stats,
            "cost_usd": cost_usd,
            "api_calls": 1,
        }

        # Write result.json
        with open(result_file, "w") as f:
            json.dump(result_data, f, indent=2)

        logger.debug(f"✓ Regenerated {result_file}")
        return True

    except (json.JSONDecodeError, KeyError, IndexError) as e:
        logger.error(f"Failed to regenerate {agent_dir}: {e}")
        return False


def main() -> int:
    """Regenerate agent result.json files from existing logs."""
    parser = argparse.ArgumentParser(
        description="Regenerate agent/result.json files from existing logs",
    )

    parser.add_argument(
        "experiment_dir",
        type=Path,
        help="Path to experiment directory",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if not args.experiment_dir.exists():
        logger.error(f"Experiment directory not found: {args.experiment_dir}")
        return 1

    # Scan for agent directories
    logger.info(f"Scanning {args.experiment_dir}")

    regenerated = 0
    already_exists = 0
    failed = 0

    for agent_dir in args.experiment_dir.rglob("agent"):
        if not agent_dir.is_dir():
            continue

        result_file = agent_dir / "result.json"
        if result_file.exists():
            already_exists += 1
            continue

        # Check if agent completed (has output.txt)
        output_file = agent_dir / "output.txt"
        if not output_file.exists() or output_file.stat().st_size == 0:
            continue

        # Try to regenerate
        if regenerate_agent_result(agent_dir):
            regenerated += 1
        else:
            failed += 1

    # Print summary
    print()
    print("=" * 60)
    print("AGENT RESULT REGENERATION SUMMARY")
    print("=" * 60)
    print(f"Already exist:   {already_exists}")
    print(f"Regenerated:     {regenerated}")
    print(f"Failed:          {failed}")
    print("=" * 60)

    if regenerated > 0:
        logger.info(f"✓ Successfully regenerated {regenerated} agent/result.json files")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
