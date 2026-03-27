"""Rate limiting utilities for API calls.

Handles:
- GitHub API rate limit detection and waiting
- Claude usage limit detection
- Time parsing and waiting logic
"""

import json
import logging
import re
import subprocess
import time
from datetime import datetime
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)


def parse_reset_epoch(reset_str: str) -> int | None:
    """Parse GitHub rate limit reset timestamp from various formats.

    Supports:
    - Unix epoch: "1234567890"
    - ISO 8601: "2024-01-15T12:30:45Z"
    - Human readable: "2024-01-15 12:30:45 +0000 UTC"

    Args:
        reset_str: Reset timestamp string

    Returns:
        Unix epoch timestamp or None if parsing fails

    """
    reset_str = reset_str.strip()

    # Try unix epoch
    if reset_str.isdigit():
        return int(reset_str)

    # Try ISO 8601 format
    if "T" in reset_str and reset_str.endswith("Z"):
        try:
            dt = datetime.fromisoformat(reset_str.replace("Z", "+00:00"))
            return int(dt.timestamp())
        except ValueError:
            pass

    # Try human readable format with timezone
    try:
        # Remove timezone name if present
        reset_str = re.sub(r"\s+[A-Z]{3,4}$", "", reset_str)
        dt = datetime.strptime(reset_str, "%Y-%m-%d %H:%M:%S %z")
        return int(dt.timestamp())
    except ValueError:
        pass

    logger.warning(f"Unable to parse reset timestamp: {reset_str}")
    return None


def detect_rate_limit(stderr: str) -> tuple[bool, int]:
    """Detect GitHub API rate limit from error output.

    Args:
        stderr: Standard error output from gh command

    Returns:
        Tuple of (is_rate_limited, reset_epoch_or_0)

    """
    # Pattern: "API rate limit exceeded ... resets at 2024-01-15 12:30:45 +0000 UTC"
    match = re.search(
        r"API rate limit exceeded.*?(?:resets? at|reset time:)\s*([^\n]+)",
        stderr,
        re.IGNORECASE,
    )

    if match:
        reset_str = match.group(1).strip()
        reset_epoch = parse_reset_epoch(reset_str)
        if reset_epoch:
            logger.info(f"Rate limit detected, resets at epoch {reset_epoch}")
            return True, reset_epoch

    # Fallback: check for rate limit keywords without reset time
    # Use word boundary for 429 to avoid matching port numbers
    if re.search(r"rate limit|too many requests|\b429\b", stderr, re.IGNORECASE):
        logger.warning("Rate limit detected but no reset time found")
        return True, 0

    return False, 0


def detect_claude_usage_limit(stderr: str) -> bool:
    """Detect Claude API usage limit from error output.

    Args:
        stderr: Standard error output

    Returns:
        True if usage limit detected

    """
    patterns = [
        r"usage limit",
        r"quota exceeded",
        r"credit.*exhausted",
        r"billing.*limit|billing.*exceeded",  # More specific to avoid false positives
    ]

    for pattern in patterns:
        if re.search(pattern, stderr, re.IGNORECASE):
            logger.error(f"Claude usage limit detected: {pattern}")
            return True

    return False


def wait_until(epoch: int, reason: str = "rate limit") -> None:
    """Wait until the specified epoch timestamp.

    Args:
        epoch: Unix epoch timestamp to wait until
        reason: Description of why we're waiting

    """
    now = int(time.time())
    wait_seconds = max(0, epoch - now)

    if wait_seconds == 0:
        logger.debug(f"No wait needed for {reason}")
        return

    wait_minutes = wait_seconds / 60
    reset_time = datetime.fromtimestamp(epoch, tz=ZoneInfo("UTC"))

    logger.info(
        f"Waiting {wait_minutes:.1f} minutes for {reason} "
        f"(until {reset_time.strftime('%H:%M:%S UTC')})"
    )

    # Wait in chunks to allow for interruption
    chunk_size = 10  # seconds
    chunks = wait_seconds // chunk_size
    remainder = wait_seconds % chunk_size

    for i in range(chunks):
        time.sleep(chunk_size)
        remaining = wait_seconds - ((i + 1) * chunk_size)
        # Log progress at minute boundaries (allow some slack for chunk alignment)
        if remaining > 0 and remaining % 60 < chunk_size:
            logger.debug(f"{remaining // 60} minutes remaining...")

    if remainder > 0:
        time.sleep(remainder)

    logger.info("Wait complete, resuming operations")


def check_rate_limit_status() -> tuple[int, int, int]:
    """Check current GitHub API rate limit status.

    Returns:
        Tuple of (remaining, limit, reset_epoch)
        Returns (0, 0, 0) if unable to check

    """
    try:
        result = subprocess.run(
            ["gh", "api", "rate_limit"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )

        data = json.loads(result.stdout)
        core = data.get("rate", {})

        return (
            core.get("remaining", 0),
            core.get("limit", 0),
            core.get("reset", 0),
        )
    except Exception as e:
        logger.warning(f"Failed to check rate limit status: {e}")
        return 0, 0, 0
