#!/usr/bin/env python3
"""Get GitHub contribution statistics using GitHub CLI.

Fetches and displays statistics for issues, PRs, and commits within a date range.

Uses the gh CLI tool instead of PyGithub for better reliability.

Usage:
    python scripts/get_stats.py START_DATE END_DATE [--author USERNAME] [--repo OWNER/REPO]

Examples:
    # Stats for current repo in January 2026
    python scripts/get_stats.py 2026-01-01 2026-01-31

    # Stats for specific author
    python scripts/get_stats.py 2026-01-01 2026-01-31 --author mvillmow

    # Stats for different repo
    python scripts/get_stats.py 2026-01-01 2026-01-31 --repo owner/repo

"""

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

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


def get_issues_stats(
    start_date: str, end_date: str, author: str | None, repo: str
) -> dict[str, Any]:
    """Get issue statistics using gh CLI.

    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        author: Optional author username filter
        repo: Repository in owner/repo format

    Returns:
        Dictionary with issue counts

    """
    # Build search query
    query_parts = [
        f"repo:{repo}",
        "type:issue",
        f"created:{start_date}..{end_date}",
    ]
    if author:
        query_parts.append(f"author:{author}")

    query = " ".join(query_parts)

    result = subprocess.run(
        ["gh", "api", "search/issues", "-f", f"q={query}", "--jq", ".total_count"],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return {"total": 0, "open": 0, "closed": 0}

    total = int(result.stdout.strip())

    # Get open issues
    query_open = query + " state:open"
    result_open = subprocess.run(
        ["gh", "api", "search/issues", "-f", f"q={query_open}", "--jq", ".total_count"],
        capture_output=True,
        text=True,
    )
    open_count = int(result_open.stdout.strip()) if result_open.returncode == 0 else 0

    return {
        "total": total,
        "open": open_count,
        "closed": total - open_count,
    }


def get_prs_stats(start_date: str, end_date: str, author: str | None, repo: str) -> dict[str, Any]:
    """Get pull request statistics using gh CLI.

    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        author: Optional author username filter
        repo: Repository in owner/repo format

    Returns:
        Dictionary with PR counts

    """
    # Build search query
    query_parts = [
        f"repo:{repo}",
        "type:pr",
        f"created:{start_date}..{end_date}",
    ]
    if author:
        query_parts.append(f"author:{author}")

    query = " ".join(query_parts)

    result = subprocess.run(
        ["gh", "api", "search/issues", "-f", f"q={query}", "--jq", ".total_count"],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return {"total": 0, "merged": 0, "open": 0, "closed": 0}

    total = int(result.stdout.strip())

    # Get merged PRs
    query_merged = query + " is:merged"
    result_merged = subprocess.run(
        ["gh", "api", "search/issues", "-f", f"q={query_merged}", "--jq", ".total_count"],
        capture_output=True,
        text=True,
    )
    merged = int(result_merged.stdout.strip()) if result_merged.returncode == 0 else 0

    # Get open PRs
    query_open = query + " state:open"
    result_open = subprocess.run(
        ["gh", "api", "search/issues", "-f", f"q={query_open}", "--jq", ".total_count"],
        capture_output=True,
        text=True,
    )
    open_count = int(result_open.stdout.strip()) if result_open.returncode == 0 else 0

    return {
        "total": total,
        "merged": merged,
        "open": open_count,
        "closed": total - merged - open_count,
    }


def get_commits_stats(
    start_date: str, end_date: str, author: str | None, repo: str
) -> dict[str, Any]:
    """Get commit statistics using gh CLI.

    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        author: Optional author username filter
        repo: Repository in owner/repo format

    Returns:
        Dictionary with commit counts

    """
    # Build gh api query for commits
    owner, repo_name = repo.split("/")

    params = [
        "gh",
        "api",
        f"repos/{owner}/{repo_name}/commits",
        "--paginate",
        "-f",
        f"since={start_date}T00:00:00Z",
        "-f",
        f"until={end_date}T23:59:59Z",
    ]

    if author:
        params.extend(["-f", f"author={author}"])

    params.append("--jq")
    params.append("length")

    result = subprocess.run(
        params,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return {"total": 0}

    # Sum up all pages
    total = sum(int(line.strip()) for line in result.stdout.strip().split("\n") if line.strip())

    return {"total": total}


def format_table(stats: dict[str, Any]) -> None:
    """Format and print statistics table.

    Args:
        stats: Dictionary containing issues, prs, and commits statistics

    """
    print("\n" + "=" * 60)
    print("GitHub Contribution Statistics")
    print("=" * 60)
    print()

    # Issues
    print("ISSUES")
    print("-" * 60)
    print(f"  Total:  {stats['issues']['total']:>6}")
    print(f"  Open:   {stats['issues']['open']:>6}")
    print(f"  Closed: {stats['issues']['closed']:>6}")
    print()

    # Pull Requests
    print("PULL REQUESTS")
    print("-" * 60)
    print(f"  Total:  {stats['prs']['total']:>6}")
    print(f"  Merged: {stats['prs']['merged']:>6}")
    print(f"  Open:   {stats['prs']['open']:>6}")
    print(f"  Closed: {stats['prs']['closed']:>6}")
    print()

    # Commits
    print("COMMITS")
    print("-" * 60)
    print(f"  Total:  {stats['commits']['total']:>6}")
    print()

    # Summary
    print("=" * 60)


def validate_date(date_string: str) -> bool:
    """Validate date string format.

    Args:
        date_string: Date in YYYY-MM-DD format

    Returns:
        True if valid

    """
    try:
        datetime.strptime(date_string, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def main() -> int:
    """Run the GitHub stats script."""
    parser = argparse.ArgumentParser(
        description="Get GitHub contribution statistics",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Stats for January 2026
    python scripts/get_stats.py 2026-01-01 2026-01-31

    # Stats for specific author
    python scripts/get_stats.py 2026-01-01 2026-01-31 --author mvillmow

    # Stats for different repo
    python scripts/get_stats.py 2026-01-01 2026-01-31 --repo owner/repo
        """,
    )
    parser.add_argument("start_date", help="Start date (YYYY-MM-DD)")
    parser.add_argument("end_date", help="End date (YYYY-MM-DD)")
    parser.add_argument("--author", help="Filter by author username")
    parser.add_argument("--repo", help="Repository (owner/repo), defaults to current repo")

    args = parser.parse_args()

    # Validate dates
    if not validate_date(args.start_date):
        print(f"Error: Invalid start date format: {args.start_date}", file=sys.stderr)
        print("Expected format: YYYY-MM-DD", file=sys.stderr)
        return 1

    if not validate_date(args.end_date):
        print(f"Error: Invalid end date format: {args.end_date}", file=sys.stderr)
        print("Expected format: YYYY-MM-DD", file=sys.stderr)
        return 1

    # Get repository
    repo = args.repo if args.repo else get_repo_name()

    # Display query parameters
    print(f"Repository: {repo}")
    print(f"Date range: {args.start_date} to {args.end_date}")
    if args.author:
        print(f"Author: {args.author}")
    print()

    # Fetch statistics
    print("Fetching statistics...")

    stats = {
        "issues": get_issues_stats(args.start_date, args.end_date, args.author, repo),
        "prs": get_prs_stats(args.start_date, args.end_date, args.author, repo),
        "commits": get_commits_stats(args.start_date, args.end_date, args.author, repo),
    }

    # Display results
    format_table(stats)

    return 0


if __name__ == "__main__":
    sys.exit(main())
