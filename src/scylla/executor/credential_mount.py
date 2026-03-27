"""Context manager for temporary credential directory lifecycle.

This module provides safe, leak-proof management of temporary credential
directories used when mounting Claude credentials into Docker containers.

The core problem solved: Docker may hold file locks on mounted directories
even after container exit, causing shutil.rmtree() to silently fail and
leaving credential copies scattered in the home directory.
"""

from __future__ import annotations

import contextlib
import logging
import shutil
import time
import uuid
from collections.abc import Generator
from pathlib import Path

logger = logging.getLogger(__name__)


@contextlib.contextmanager
def temporary_credential_mount() -> Generator[Path | None, None, None]:
    """Context manager for temporary credential directory lifecycle.

    Creates a temp dir with credentials, yields its path for volume mounting,
    and ensures cleanup with retry logic to handle Docker mount release delays.

    Yields:
        Path to the temporary credential directory, or None if no credentials
        file exists at ~/.claude/.credentials.json.

    Example:
        >>> with temporary_credential_mount() as creds_dir:
        ...     if creds_dir:
        ...         volumes[str(creds_dir)] = {"bind": "/mnt/claude-creds", "mode": "ro"}

    """
    credentials_path = Path.home() / ".claude" / ".credentials.json"
    if not credentials_path.exists():
        yield None
        return

    temp_dir = Path.home() / f".scylla-temp-creds-{uuid.uuid4().hex[:8]}"
    temp_dir.mkdir(exist_ok=True)
    temp_dir.chmod(0o755)

    temp_creds = temp_dir / ".credentials.json"
    temp_creds.write_text(credentials_path.read_text())
    temp_creds.chmod(0o644)

    try:
        yield temp_dir
    finally:
        _cleanup_temp_dir(temp_dir)


def _cleanup_temp_dir(temp_dir: Path, retries: int = 3, delay: float = 0.5) -> None:
    """Clean up temp credential directory with retry for Docker mount release.

    Args:
        temp_dir: Path to the temporary directory to remove.
        retries: Number of removal attempts before giving up.
        delay: Seconds to wait between attempts.

    """
    for attempt in range(retries):
        try:
            shutil.rmtree(temp_dir)
            return
        except OSError:
            if attempt < retries - 1:
                time.sleep(delay)
            else:
                logger.warning(
                    "Failed to clean up temp credentials dir after %d attempts: %s",
                    retries,
                    temp_dir,
                )


def cleanup_stale_credential_dirs() -> int:
    """Remove any leftover .scylla-temp-creds-* dirs from home directory.

    This is a recovery utility for cleaning up leaked directories caused by
    previous silent cleanup failures.

    Returns:
        Number of directories removed.

    """
    count = 0
    for path in Path.home().glob(".scylla-temp-creds-*"):
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
            count += 1
    return count


__all__ = [
    "cleanup_stale_credential_dirs",
    "temporary_credential_mount",
]
