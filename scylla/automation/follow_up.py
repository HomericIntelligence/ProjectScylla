"""Follow-up issue creation functions for issue implementation.

Provides:
- Parsing follow-up items from Claude JSON responses
- Creating follow-up GitHub issues after implementation
"""

from __future__ import annotations

import contextlib
import json
import logging
import re
import time
from pathlib import Path
from typing import Any

from .git_utils import run
from .github_api import gh_issue_comment, gh_issue_create
from .prompts import get_follow_up_prompt

logger = logging.getLogger(__name__)


def parse_follow_up_items(text: str) -> list[dict[str, Any]]:
    """Parse follow-up items from Claude's JSON response.

    Args:
        text: Claude's response text (may contain JSON in code blocks)

    Returns:
        List of follow-up item dictionaries with title, body, labels

    """
    # Try to extract JSON from code blocks or bare JSON
    json_match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    else:
        # Try to find bare JSON array
        json_match = re.search(r"(\[.*\])", text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            logger.warning("No JSON array found in follow-up response")
            return []

    try:
        items = json.loads(json_str)
        if not isinstance(items, list):
            logger.warning("Follow-up response is not a JSON array")
            return []

        # Validate and filter items
        valid_items = []
        for item in items[:5]:  # Cap at 5
            if not isinstance(item, dict):
                continue
            if "title" not in item or "body" not in item:
                logger.warning(f"Skipping follow-up item missing required fields: {item}")
                continue

            # Ensure labels is a list
            if "labels" not in item or not isinstance(item["labels"], list):
                item["labels"] = []

            valid_items.append(item)

        return valid_items

    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse follow-up JSON: {e}")
        return []


def run_follow_up_issues(
    session_id: str,
    worktree_path: Path,
    issue_number: int,
    state_dir: Path,
    status_tracker: Any | None = None,
    slot_id: int | None = None,
) -> None:
    """Resume Claude session to identify and file follow-up issues.

    Args:
        session_id: Claude session ID to resume
        worktree_path: Path to git worktree
        issue_number: Parent issue number
        state_dir: Directory for state/log files
        status_tracker: StatusTracker instance for slot updates (optional)
        slot_id: Worker slot ID for status updates

    """
    state_dir.mkdir(parents=True, exist_ok=True)

    # Write follow-up prompt to temp file in worktree
    prompt_file = worktree_path / f".claude-followup-{issue_number}.md"
    prompt_file.write_text(get_follow_up_prompt(issue_number))

    try:
        # Resume session and get follow-up items
        result = run(
            [
                "claude",
                "--resume",
                session_id,
                str(prompt_file),
                "--output-format",
                "json",
            ],
            cwd=worktree_path,
            timeout=600,  # 10 minutes
        )

        # Save successful output to log file
        follow_up_log = state_dir / f"follow-up-{issue_number}.log"
        follow_up_log.write_text(result.stdout or "")

        # Parse JSON output
        try:
            data = json.loads(result.stdout)
            response_text = data.get("result", "")
        except (json.JSONDecodeError, AttributeError) as e:
            logger.warning(f"Could not parse follow-up response for issue #{issue_number}: {e}")
            return

        # Extract follow-up items
        items = parse_follow_up_items(response_text)

        if not items:
            logger.info(f"No follow-up items identified for issue #{issue_number}")
            return

        # Create follow-up issues
        created_issues = []
        for i, item in enumerate(items, 1):
            try:
                # Update status
                if slot_id is not None and status_tracker is not None:
                    status_tracker.update_slot(
                        slot_id, f"#{issue_number}: Creating follow-up {i}/{len(items)}"
                    )

                # Append reference to parent issue
                body_with_ref = f"{item['body']}\n\n_Follow-up from #{issue_number}_"

                # Create issue with labels
                new_issue_num = gh_issue_create(
                    title=item["title"],
                    body=body_with_ref,
                    labels=item.get("labels"),
                )
                created_issues.append(new_issue_num)

                # Rate limit: sleep between creates
                time.sleep(1)

            except (
                Exception
            ) as e:  # broad catch: GitHub API can fail in many ways; continue with others
                logger.warning(f"Failed to create follow-up issue '{item['title']}': {e}")
                # Continue with remaining items

        # Post summary comment on parent issue
        if created_issues:
            summary = f"Created {len(created_issues)} follow-up issue(s): " + ", ".join(
                f"#{num}" for num in created_issues
            )
            try:
                gh_issue_comment(issue_number, summary)
                logger.info(f"Posted follow-up summary to issue #{issue_number}")
            except Exception as e:  # broad catch: GitHub API call; non-critical summary post
                logger.warning(f"Failed to post follow-up summary: {e}")

        logger.info(
            f"Follow-up issues completed for #{issue_number}: created {len(created_issues)}"
        )

    except (
        Exception
    ) as e:  # broad catch: top-level follow-up boundary; non-blocking, must not propagate
        logger.warning(f"Follow-up issues failed for issue #{issue_number}: {e}")

        # Save failure output to log file
        follow_up_log = state_dir / f"follow-up-{issue_number}.log"
        error_output = f"FAILED: {e}\n"
        if hasattr(e, "stdout"):
            error_output += f"\nSTDOUT:\n{e.stdout or ''}"
        if hasattr(e, "stderr"):
            error_output += f"\nSTDERR:\n{e.stderr or ''}"
        follow_up_log.write_text(error_output)

        # Non-blocking: never re-raise
    finally:
        # Clean up temp file
        with contextlib.suppress(Exception):
            prompt_file.unlink()
