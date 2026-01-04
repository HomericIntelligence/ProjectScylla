"""Path constants and helpers for E2E experiment directory structure.

This module centralizes all path logic for agent/judge result storage
to ensure consistency across the codebase.
"""

from pathlib import Path

# Directory name constants
AGENT_DIR = "agent"
JUDGE_DIR = "judge"
RESULT_FILE = "result.json"


def get_agent_dir(run_dir: Path) -> Path:
    """Get the agent artifacts directory for a run.

    Args:
        run_dir: Path to the run directory (e.g., T0/00/run_01)

    Returns:
        Path to agent directory (e.g., T0/00/run_01/agent)

    """
    return run_dir / AGENT_DIR


def get_judge_dir(run_dir: Path) -> Path:
    """Get the judge artifacts directory for a run.

    Args:
        run_dir: Path to the run directory (e.g., T0/00/run_01)

    Returns:
        Path to judge directory (e.g., T0/00/run_01/judge)

    """
    return run_dir / JUDGE_DIR


def get_agent_result_file(run_dir: Path) -> Path:
    """Get the agent result.json file path.

    Args:
        run_dir: Path to the run directory

    Returns:
        Path to agent/result.json

    """
    return get_agent_dir(run_dir) / RESULT_FILE


def get_judge_result_file(run_dir: Path) -> Path:
    """Get the judge result.json file path.

    Args:
        run_dir: Path to the run directory

    Returns:
        Path to judge/result.json

    """
    return get_judge_dir(run_dir) / RESULT_FILE
