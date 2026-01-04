"""Rate limit detection and handling for E2E testing.

This module provides rate limit detection from both agent (Claude Code subprocess)
and judge (Opus API) responses, along with wait/retry logic.

Python Justification: Required for JSON parsing, regex patterns, and subprocess interaction.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from scylla.e2e.checkpoint import E2ECheckpoint

logger = logging.getLogger(__name__)


@dataclass
class RateLimitInfo:
    """Information about a detected rate limit.

    Attributes:
        source: Where rate limit occurred (agent or judge)
        retry_after_seconds: Seconds to wait before retry (with buffer)
        error_message: Human-readable error message
        detected_at: ISO timestamp when detected
    """

    source: str  # "agent" or "judge"
    retry_after_seconds: float | None
    error_message: str
    detected_at: str

    def __post_init__(self) -> None:
        """Validate source field."""
        if self.source not in ("agent", "judge"):
            raise ValueError(f"Invalid source: {self.source}. Must be 'agent' or 'judge'.")


class RateLimitError(Exception):
    """Raised when rate limit is detected from agent or judge.

    This exception carries rate limit details for handling by the
    pause/resume system.

    Attributes:
        info: RateLimitInfo with detection details
    """

    def __init__(self, info: RateLimitInfo):
        """Initialize with rate limit info.

        Args:
            info: Rate limit detection information
        """
        self.info = info
        super().__init__(f"Rate limit from {info.source}: {info.error_message}")


def parse_retry_after(stderr: str) -> float | None:
    """Extract Retry-After value from stderr/headers with 10% buffer.

    Handles:
    - Retry-After: 30 (seconds)
    - resets 4pm (America/Los_Angeles) format
    - Retry-After header in various formats

    Args:
        stderr: Standard error output containing headers

    Returns:
        Seconds to wait (with 10% buffer added), or None if not found
    """
    # Pattern 1: "Retry-After: <seconds>"
    match = re.search(r"Retry-After:\s*(\d+)", stderr, re.IGNORECASE)
    if match:
        seconds = float(match.group(1))
        # Add 10% buffer to be conservative
        return seconds * 1.1

    # Pattern 2: "resets 4pm (America/Los_Angeles)" or similar time format
    # Match patterns like "resets 4pm", "resets 12am", "resets 11:30pm"
    match = re.search(r"resets\s+(\d{1,2}):?(\d{2})?\s*(am|pm)", stderr, re.IGNORECASE)
    if match:
        from datetime import datetime, timezone
        import zoneinfo

        hour = int(match.group(1))
        minute = int(match.group(2)) if match.group(2) else 0
        am_pm = match.group(3).lower()

        # Convert to 24-hour format
        if am_pm == "pm" and hour != 12:
            hour += 12
        elif am_pm == "am" and hour == 12:
            hour = 0

        # Try to extract timezone, default to America/Los_Angeles if not found
        tz_match = re.search(r"\(([^)]+)\)", stderr)
        tz_str = tz_match.group(1) if tz_match else "America/Los_Angeles"

        try:
            tz = zoneinfo.ZoneInfo(tz_str)
        except Exception:
            # Fallback to UTC if timezone parsing fails
            tz = timezone.utc

        # Get current time and target reset time
        now = datetime.now(tz)
        reset_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

        # If reset time is in the past today, it means tomorrow
        if reset_time <= now:
            from datetime import timedelta

            reset_time += timedelta(days=1)

        # Calculate seconds until reset
        seconds = (reset_time - now).total_seconds()

        # Add 10% buffer to be conservative
        return seconds * 1.1

    return None


def detect_rate_limit(stdout: str, stderr: str, source: str = "agent") -> RateLimitInfo | None:
    """Detect rate limit from JSON output or stderr patterns.

    Detection order (requirement: JSON first, then stderr patterns):
    1. Parse JSON `is_error` field (if stdout is JSON)
    2. Scan stderr for patterns: 429, "rate limit", "overloaded"

    Args:
        stdout: Standard output from subprocess
        stderr: Standard error from subprocess
        source: Source of output ("agent" or "judge")

    Returns:
        RateLimitInfo if rate limit detected, None otherwise
    """
    retry_after = None
    error_msg = ""

    # 1. Try JSON detection first (primary method)
    try:
        data = json.loads(stdout.strip())

        # Check is_error field (from Claude Code JSON output)
        # Rate-limited runs have is_error: true combined with rate-limit indicators
        if data.get("is_error"):
            result = data.get("result", data.get("error", ""))
            error_str = str(result).lower()

            # Check for rate limit keywords in error message
            if any(
                keyword in error_str
                for keyword in [
                    "rate limit",
                    "rate_limit",
                    "ratelimit",
                    "overloaded",
                    "429",
                    "hit your limit",
                    "resets",
                ]
            ):
                error_msg = str(result)
                # Try parsing from error message first (JSON result field), then stderr
                retry_after = parse_retry_after(error_msg) or parse_retry_after(stderr)

                return RateLimitInfo(
                    source=source,
                    retry_after_seconds=retry_after,
                    error_message=error_msg or "Rate limit detected (JSON is_error)",
                    detected_at=datetime.now(UTC).isoformat(),
                )

    except (json.JSONDecodeError, ValueError, TypeError):
        # stdout is not JSON, try stderr patterns
        pass

    # 2. Scan stderr for rate limit patterns (fallback)
    stderr_lower = stderr.lower()

    # Pattern 1: HTTP 429 status
    if "429" in stderr:
        error_msg = "HTTP 429: Rate limit exceeded"
        retry_after = parse_retry_after(stderr)

    # Pattern 2: "rate limit" text
    elif "rate limit" in stderr_lower or "ratelimit" in stderr_lower:
        error_msg = "Rate limit detected in stderr"
        retry_after = parse_retry_after(stderr)

    # Pattern 3: "hit your limit" text
    elif "hit your limit" in stderr_lower:
        error_msg = "API limit hit"
        retry_after = parse_retry_after(stderr)

    # Pattern 4: "overloaded" text
    elif "overloaded" in stderr_lower:
        error_msg = "API overloaded"
        retry_after = parse_retry_after(stderr)

    if error_msg:
        return RateLimitInfo(
            source=source,
            retry_after_seconds=retry_after,
            error_message=error_msg,
            detected_at=datetime.now(UTC).isoformat(),
        )

    return None


def wait_for_rate_limit(
    retry_after: float | None,
    checkpoint: E2ECheckpoint,
    checkpoint_path: Path,
    log_func: Callable[[str], None] | None = None,
) -> None:
    """Wait for rate limit to expire with status updates.

    Updates checkpoint with pause status, waits, then updates to running.
    Provides periodic status updates during wait.

    Args:
        retry_after: Seconds to wait (already includes 10% buffer)
        checkpoint: Checkpoint to update with pause status
        checkpoint_path: Path to save updated checkpoint
        log_func: Function for status logging (default: logger.info)
    """
    if log_func is None:
        log_func = logger.info

    # Default wait if no Retry-After header
    if retry_after is None:
        retry_after = 60.0  # Default 60 seconds
        log_func("No Retry-After header found, using default 60s wait")

    # Ensure 10% buffer (should already be added by parse_retry_after)
    wait_time = retry_after

    # Update checkpoint with pause status
    from scylla.e2e.checkpoint import save_checkpoint

    checkpoint.status = "paused_rate_limit"
    checkpoint.rate_limit_until = (datetime.now(UTC) + timedelta(seconds=wait_time)).isoformat()
    checkpoint.pause_count += 1
    save_checkpoint(checkpoint, checkpoint_path)

    # Log to console (requirement: visible status)
    log_func(
        f"⏸️  Rate limit hit. Pausing for {wait_time:.0f}s (until {checkpoint.rate_limit_until})"
    )

    # Wait with periodic status updates
    remaining = wait_time
    update_interval = 30  # Update every 30 seconds

    while remaining > 0:
        sleep_chunk = min(update_interval, remaining)
        time.sleep(sleep_chunk)
        remaining -= sleep_chunk

        if remaining > 0:
            minutes = remaining / 60
            if minutes >= 1:
                log_func(f"   Rate limit wait: {minutes:.1f} minutes remaining")
            else:
                log_func(f"   Rate limit wait: {remaining:.0f} seconds remaining")

    # Update checkpoint - resuming
    checkpoint.status = "running"
    checkpoint.rate_limit_until = None
    checkpoint.rate_limit_source = None
    save_checkpoint(checkpoint, checkpoint_path)

    log_func("▶️  Rate limit wait complete. Resuming...")
