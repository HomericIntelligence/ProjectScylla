"""GitHub API utilities using gh CLI.

Provides:
- Issue data fetching with caching
- Rate-limited API calls
- Batch operations with GraphQL
- Secure file writing
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from .git_utils import get_repo_info, run
from .models import IssueInfo, IssueState
from .rate_limit import detect_claude_usage_limit, detect_rate_limit, wait_until

logger = logging.getLogger(__name__)


def _gh_call(
    args: list[str],
    check: bool = True,
    retry_on_rate_limit: bool = True,
    max_retries: int = 3,
) -> subprocess.CompletedProcess:
    """Call gh CLI with rate limit handling.

    Args:
        args: Arguments to pass to gh
        check: Whether to raise on non-zero exit
        retry_on_rate_limit: Whether to retry on rate limit
        max_retries: Maximum retry attempts

    Returns:
        CompletedProcess instance

    Raises:
        subprocess.CalledProcessError: If command fails and check=True
        RuntimeError: If Claude usage limit detected

    """
    for attempt in range(max_retries):
        try:
            result = run(
                ["gh"] + args,
                check=check,
                capture_output=True,
            )
            return result
        except subprocess.CalledProcessError as e:
            stderr = e.stderr if e.stderr else ""

            # Check for Claude usage limit
            if detect_claude_usage_limit(stderr):
                raise RuntimeError(
                    "Claude API usage limit reached. Please check your billing."
                ) from e

            # Check for rate limit (regardless of retry_on_rate_limit flag)
            is_rate_limited, reset_epoch = detect_rate_limit(stderr)
            if is_rate_limited:
                if retry_on_rate_limit:
                    if reset_epoch > 0:
                        wait_until(reset_epoch, "GitHub API rate limit")
                    else:
                        # No reset time, use exponential backoff
                        wait_seconds = min(60 * (2**attempt), 300)  # Max 5 minutes
                        logger.warning(f"Rate limited but no reset time, waiting {wait_seconds}s")
                        time.sleep(wait_seconds)
                    continue
                else:
                    # Don't retry, but provide clear error message
                    raise RuntimeError(
                        f"GitHub API rate limit reached. Reset at epoch {reset_epoch}"
                    ) from e

            # Check if this is a non-transient error that shouldn't be retried
            # Permission errors, not found, bad requests should fail fast
            non_transient_patterns = [
                r"403|forbidden|permission denied",
                r"404|not found",
                r"400|bad request",
                r"401|unauthorized",
                r"invalid argument",
            ]
            if any(re.search(pattern, stderr, re.IGNORECASE) for pattern in non_transient_patterns):
                logger.error(f"Non-transient error detected: {stderr[:200]}")
                raise

            # Last retry attempt, re-raise
            if attempt == max_retries - 1:
                raise

            # Transient error (network, timeout, 5xx), retry with backoff
            wait_seconds = 2**attempt
            logger.warning(f"gh call failed (attempt {attempt + 1}), retrying in {wait_seconds}s")
            time.sleep(wait_seconds)

    # Should not reach here, but satisfy type checker
    raise RuntimeError("gh call failed after all retries")


def gh_issue_json(issue_number: int) -> dict[str, Any]:
    """Fetch issue data as JSON.

    Args:
        issue_number: GitHub issue number

    Returns:
        Issue data dictionary

    Raises:
        RuntimeError: If issue fetch fails

    """
    try:
        result = _gh_call(
            ["issue", "view", str(issue_number), "--json", "number,title,state,labels,body"],
        )
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to fetch issue #{issue_number}: {e}") from e


def gh_issue_comment(issue_number: int, body: str) -> None:
    """Post a comment to an issue.

    Args:
        issue_number: GitHub issue number
        body: Comment body text

    Raises:
        RuntimeError: If comment post fails

    """
    try:
        _gh_call(["issue", "comment", str(issue_number), "--body", body])
        logger.info(f"Posted comment to issue #{issue_number}")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to post comment to issue #{issue_number}: {e}") from e


def gh_issue_create(title: str, body: str, labels: list[str] | None = None) -> int:
    """Create a new GitHub issue.

    Args:
        title: Issue title
        body: Issue body/description
        labels: Optional list of label names to apply

    Returns:
        Created issue number

    Raises:
        RuntimeError: If issue creation fails

    """
    try:
        # Build command
        cmd = ["issue", "create", "--title", title, "--body", body]

        # Add labels if provided
        if labels:
            for label in labels:
                cmd.extend(["--label", label])

        result = _gh_call(cmd)

        # Extract issue number from URL in output
        output = result.stdout.strip()
        try:
            # Try to extract number from URL (e.g., https://github.com/owner/repo/issues/123)
            match = re.search(r"/issues/(\d+)", output)
            if match:
                issue_number = int(match.group(1))
            else:
                # Fallback to parsing last path component
                issue_number = int(output.split("/")[-1])
        except (ValueError, IndexError) as e:
            raise RuntimeError(f"Failed to parse issue number from output: {output}") from e

        logger.info(f"Created issue #{issue_number}")
        return issue_number

    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to create issue: {e}") from e


def gh_pr_create(
    branch: str,
    title: str,
    body: str,
    auto_merge: bool = True,
) -> int:
    """Create a pull request.

    Args:
        branch: Branch name
        title: PR title
        body: PR description
        auto_merge: Whether to enable auto-merge

    Returns:
        PR number

    Raises:
        RuntimeError: If PR creation fails

    """
    try:
        # Create PR
        result = _gh_call(
            [
                "pr",
                "create",
                "--head",
                branch,
                "--title",
                title,
                "--body",
                body,
            ]
        )

        # Extract PR number from URL in output
        output = result.stdout.strip()
        try:
            # Try to extract number from URL (e.g., https://github.com/owner/repo/pull/123)
            match = re.search(r"/pull/(\d+)", output)
            if match:
                pr_number = int(match.group(1))
            else:
                # Fallback to parsing last path component
                pr_number = int(output.split("/")[-1])
        except (ValueError, IndexError) as e:
            raise RuntimeError(f"Failed to parse PR number from output: {output}") from e

        logger.info(f"Created PR #{pr_number}")

        # Enable auto-merge if requested
        if auto_merge:
            try:
                _gh_call(["pr", "merge", str(pr_number), "--auto", "--rebase"])
                logger.info(f"Enabled auto-merge for PR #{pr_number}")
            except subprocess.CalledProcessError as e:
                logger.warning(f"Failed to enable auto-merge for PR #{pr_number}: {e}")

        return pr_number

    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to create PR: {e}") from e


def prefetch_issue_states(issue_numbers: list[int]) -> dict[int, IssueState]:
    """Batch fetch issue states using GraphQL.

    Args:
        issue_numbers: List of issue numbers

    Returns:
        Dictionary mapping issue number to state

    """
    if not issue_numbers:
        return {}

    try:
        owner, repo = get_repo_info()
    except RuntimeError as e:
        logger.warning(f"Failed to get repo info: {e}")
        return {}

    # Sanitize owner and repo to prevent GraphQL injection
    # Owner and repo should be alphanumeric with hyphens/underscores
    if not re.match(r"^[a-zA-Z0-9_-]+$", owner) or not re.match(r"^[a-zA-Z0-9_-]+$", repo):
        logger.error(f"Invalid owner/repo format: {owner}/{repo}")
        return {}

    # Build GraphQL query for batch fetch
    # Query up to 100 issues at once (GitHub limit)
    batch_size = 100
    all_states: dict[int, IssueState] = {}

    for i in range(0, len(issue_numbers), batch_size):
        batch = issue_numbers[i : i + batch_size]

        # Build query fragments
        fragments = []
        for idx, num in enumerate(batch):
            fragments.append(f"issue{idx}: issue(number: {num}) {{ number state }}")

        query = f"""
        query {{
            repository(owner: "{owner}", name: "{repo}") {{
                {" ".join(fragments)}
            }}
        }}
        """

        try:
            result = _gh_call(["api", "graphql", "-f", f"query={query}"])
            data = json.loads(result.stdout)

            # Extract states
            repo_data = data.get("data", {}).get("repository", {})
            for key, issue_data in repo_data.items():
                if key.startswith("issue") and issue_data:
                    number = issue_data["number"]
                    state_str = issue_data["state"]
                    all_states[number] = IssueState(state_str)

            logger.debug(f"Fetched states for {len(batch)} issues")

        except (subprocess.CalledProcessError, json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to batch fetch issue states: {e}")
            # Fall back to individual fetches for this batch
            for num in batch:
                try:
                    issue_data = gh_issue_json(num)
                    all_states[num] = IssueState(issue_data["state"])
                except Exception as e2:
                    logger.warning(f"Failed to fetch state for issue #{num}: {e2}")

    return all_states


def is_issue_closed(issue_number: int, cached_states: dict[int, IssueState] | None = None) -> bool:
    """Check if an issue is closed.

    Args:
        issue_number: GitHub issue number
        cached_states: Optional pre-fetched states cache

    Returns:
        True if issue is closed

    """
    if cached_states and issue_number in cached_states:
        return cached_states[issue_number] == IssueState.CLOSED

    try:
        issue_data = gh_issue_json(issue_number)
        return issue_data["state"] == "CLOSED"
    except Exception as e:
        logger.warning(f"Failed to check if issue #{issue_number} is closed: {e}")
        return False


def parse_issue_dependencies(issue_body: str) -> list[int]:
    """Parse issue dependencies from issue body.

    Looks for patterns like:
    - Depends on #123
    - Depends: #123, #456
    - Blocked by #789

    Args:
        issue_body: Issue body text

    Returns:
        List of dependency issue numbers

    """
    dependencies = []

    # Pattern 1: Find all #numbers after dependency keywords
    dep_keywords = r"(?:depends on|blocked by|requires|dependencies?:?)"
    # Find all #123 patterns in lines containing dependency keywords
    for line in issue_body.split("\n"):
        if re.search(dep_keywords, line, re.IGNORECASE):
            # Find all #number patterns in this line
            for match in re.finditer(r"#(\d+)", line):
                dependencies.append(int(match.group(1)))

    # Pattern 2: Find issue references in lists under Dependencies heading
    # Look for a "Dependencies" section and extract list items from it
    dep_section_match = re.search(
        r"##\s*Dependencies.*?\n(.*?)(?=##|\Z)", issue_body, re.IGNORECASE | re.DOTALL
    )
    if dep_section_match:
        dep_section = dep_section_match.group(1)
        list_pattern = r"^\s*[-*]\s*#(\d+)"
        for match in re.finditer(list_pattern, dep_section, re.MULTILINE):
            dependencies.append(int(match.group(1)))

    return list(set(dependencies))  # Remove duplicates


def fetch_issue_info(issue_number: int) -> IssueInfo:
    """Fetch complete issue information.

    Args:
        issue_number: GitHub issue number

    Returns:
        IssueInfo instance

    Raises:
        RuntimeError: If fetch fails

    """
    issue_data = gh_issue_json(issue_number)

    return IssueInfo(
        number=issue_data["number"],
        title=issue_data["title"],
        state=IssueState(issue_data["state"]),
        labels=[label["name"] for label in issue_data.get("labels", [])],
        dependencies=parse_issue_dependencies(issue_data.get("body", "")),
    )


def write_secure(path: Path, content: str) -> None:
    """Write content to file securely using atomic write.

    Args:
        path: Destination file path
        content: Content to write

    """
    path.parent.mkdir(parents=True, exist_ok=True)

    # Write to temp file first, then atomic rename
    fd, temp_path = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )

    try:
        with os.fdopen(fd, "w") as f:
            f.write(content)
        os.replace(temp_path, path)
        logger.debug(f"Wrote {len(content)} bytes to {path}")
    except Exception:
        # Clean up temp file on error
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise
