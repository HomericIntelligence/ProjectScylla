#!/usr/bin/env python3
"""Merge ready pull requests using GitHub CLI.

Automatically merges PRs that have:
- All CI checks passing
- No merge conflicts
- Review approval (if required)

Uses the gh CLI tool instead of PyGithub for better reliability.

Usage:
    python scripts/merge_prs.py [--dry-run] [--push-all]

Options:
    --dry-run: Show what would be merged without actually merging
    --push-all: Merge all PRs regardless of CI status
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

# Enable importing from repository root and scripts directory
_SCRIPT_DIR = Path(__file__).parent
_REPO_ROOT = _SCRIPT_DIR.parent
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_SCRIPT_DIR))

from common import get_repo_root  # noqa: E402


def get_repo_name() -> str:
    """Get current repository name from gh CLI.

    Returns:
        Repository name in owner/repo format

    """
    result = subprocess.run(
        ["gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"],
        capture_output=True,
        text=True,
        cwd=get_repo_root(),
    )
    if result.returncode != 0:
        print(f"Error: Failed to get repo name: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    return result.stdout.strip()


def get_open_prs() -> list[dict]:
    """Get list of open pull requests using gh CLI.

    Returns:
        List of PR dictionaries with number, title, headRefName, etc.

    """
    result = subprocess.run(
        [
            "gh",
            "pr",
            "list",
            "--state",
            "open",
            "--json",
            "number,title,headRefName,baseRefName,headRefOid,statusCheckRollup",
        ],
        capture_output=True,
        text=True,
        cwd=get_repo_root(),
    )

    if result.returncode != 0:
        print(f"Error: Failed to list PRs: {result.stderr}", file=sys.stderr)
        sys.exit(1)

    return json.loads(result.stdout)


def check_pr_status(pr_number: int) -> dict[str, bool]:
    """Check if PR is ready to merge.

    Args:
        pr_number: Pull request number

    Returns:
        Dictionary with status checks: ci_passing, mergeable, approved

    """
    result = subprocess.run(
        [
            "gh",
            "pr",
            "view",
            str(pr_number),
            "--json",
            "statusCheckRollup,mergeable,reviewDecision",
        ],
        capture_output=True,
        text=True,
        cwd=get_repo_root(),
    )

    if result.returncode != 0:
        return {"ci_passing": False, "mergeable": False, "approved": False}

    data = json.loads(result.stdout)

    # Check CI status
    ci_passing = True
    if data.get("statusCheckRollup"):
        for check in data["statusCheckRollup"]:
            if check.get("conclusion") not in ["SUCCESS", "SKIPPED", "NEUTRAL"]:
                ci_passing = False
                break

    # Check if mergeable
    mergeable = data.get("mergeable") == "MERGEABLE"

    # Check review decision (may be None if not required)
    review_decision = data.get("reviewDecision")
    approved = review_decision in ["APPROVED", None]

    return {
        "ci_passing": ci_passing,
        "mergeable": mergeable,
        "approved": approved,
    }


def merge_pr(pr_number: int, dry_run: bool = False) -> bool:
    """Merge a pull request using rebase strategy.

    Args:
        pr_number: Pull request number
        dry_run: If True, only print what would be done

    Returns:
        True if merge succeeded (or would succeed in dry-run)

    """
    if dry_run:
        print(f"[DRY RUN] Would merge PR #{pr_number} with --rebase")
        return True

    result = subprocess.run(
        ["gh", "pr", "merge", str(pr_number), "--rebase"],
        capture_output=True,
        text=True,
        cwd=get_repo_root(),
    )

    if result.returncode == 0:
        print(f"✓ Merged PR #{pr_number}")
        return True
    else:
        print(f"✗ Failed to merge PR #{pr_number}: {result.stderr}", file=sys.stderr)
        return False


def main() -> int:
    """Run the merge PRs script."""
    parser = argparse.ArgumentParser(
        description="Merge ready pull requests automatically",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Dry run - show what would be merged
    python scripts/merge_prs.py --dry-run

    # Merge all PRs with passing CI
    python scripts/merge_prs.py

    # Merge all PRs regardless of CI status
    python scripts/merge_prs.py --push-all
        """,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be merged without actually merging",
    )
    parser.add_argument(
        "--push-all",
        action="store_true",
        help="Merge all PRs regardless of CI status",
    )

    args = parser.parse_args()

    # Get repository name
    repo = get_repo_name()
    print(f"Repository: {repo}\n")

    # Get open PRs
    prs = get_open_prs()

    if not prs:
        print("No open pull requests found")
        return 0

    print(f"Found {len(prs)} open pull request(s)\n")

    merged_count = 0
    skipped_count = 0

    for pr in prs:
        pr_number = pr["number"]
        title = pr["title"]
        head_ref = pr["headRefName"]

        print(f"PR #{pr_number}: {title} ({head_ref})")

        # Check PR status
        status = check_pr_status(pr_number)

        print(f"  CI: {'✓' if status['ci_passing'] else '✗'}")
        print(f"  Mergeable: {'✓' if status['mergeable'] else '✗'}")
        print(f"  Approved: {'✓' if status['approved'] else '✗'}")

        # Decide whether to merge
        should_merge = False
        if args.push_all:
            should_merge = status["mergeable"] and status["approved"]
            if not should_merge:
                print("  → Skipping (not mergeable or not approved)")
        else:
            should_merge = all(status.values())
            if not should_merge:
                print("  → Skipping (not ready)")

        if should_merge:
            if merge_pr(pr_number, dry_run=args.dry_run):
                merged_count += 1
        else:
            skipped_count += 1

        print()

    # Summary
    print("=" * 60)
    if args.dry_run:
        print(f"[DRY RUN] Would merge: {merged_count}, Skip: {skipped_count}")
    else:
        print(f"Merged: {merged_count}, Skipped: {skipped_count}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
