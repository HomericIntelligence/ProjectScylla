"""Model validation utilities for E2E testing.

Extracted from scripts/run_e2e_experiment.py to be usable as a library module.
Uses retry_with_backoff for consistent retry behavior across the codebase.
"""

from __future__ import annotations

import logging
import subprocess

from hephaestus.utils.retry import retry_with_backoff

logger = logging.getLogger(__name__)


def is_rate_limit_error(output: str) -> tuple[bool, int | None]:
    """Check if the output indicates a rate limit error.

    Args:
        output: The stdout or stderr content to check

    Returns:
        Tuple of (is_rate_limit, time_to_wait_seconds)

    """
    if "hit your limit" in output.lower() or "rate limit" in output.lower():
        import re

        time_patterns = [
            r"resets?\s+(\d{1,2})(am|pm)",
            r"(\d+)\s*minutes?",
            r"(\d+)\s*seconds?",
            r"in\s+(\d+)\s*minutes?",
            r"in\s+(\d+)\s*hours?",
        ]

        output_lower = output.lower()

        for pattern in time_patterns:
            match = re.search(pattern, output_lower)
            if match:
                if "am" in match.group(0) or "pm" in match.group(0):
                    return True, 12 * 3600
                else:
                    time_unit = match.group(1)
                    if "minute" in match.group(0):
                        return True, int(time_unit) * 60
                    elif "second" in match.group(0):
                        return True, int(time_unit)
                    elif "hour" in match.group(0):
                        return True, int(time_unit) * 3600

        return True, 3600

    return False, None


def _run_validation_attempt(model_id: str) -> subprocess.CompletedProcess[str]:
    """Run a single Claude CLI validation attempt.

    Args:
        model_id: Model ID to test.

    Returns:
        Completed process result.

    """
    return subprocess.run(
        ["claude", "--model", model_id, "--output-format", "json", "Say 'OK'"],
        capture_output=True,
        text=True,
        timeout=30,
    )


def _handle_validation_result(
    model_id: str,
    result: subprocess.CompletedProcess[str],
) -> bool:
    """Evaluate a single validation result.

    Args:
        model_id: Model ID being validated.
        result: Completed subprocess result.

    Returns:
        True if validation passed, False otherwise.

    Raises:
        RuntimeError: If validation should be retried.

    """
    combined_output = result.stdout + result.stderr
    is_rate_limit, wait_time = is_rate_limit_error(combined_output)

    if is_rate_limit:
        logger.warning(
            f"Rate limit detected for model '{model_id}'. "
            f"Would wait {wait_time} seconds but deferring to caller retry logic..."
        )
        raise RuntimeError(f"Rate limit for model '{model_id}'")

    if result.returncode == 0 and '"is_error":false' in result.stdout:
        logger.info(f"✓ Model '{model_id}' validated successfully")
        return True

    if "not_found_error" in combined_output:
        logger.warning(f"Model '{model_id}' not found on server")
        return False

    logger.warning(f"Validation failed for model '{model_id}', will retry...")
    raise RuntimeError(f"Validation failed for model '{model_id}'")


@retry_with_backoff(
    max_retries=3,
    initial_delay=60,
    backoff_factor=2,
    retry_on=(RuntimeError, subprocess.TimeoutExpired),
    logger=logger.warning,
    jitter=False,
)
def validate_model(model_id: str, max_retries: int = 3, base_delay: int = 60) -> bool:
    """Validate that a model is available by running a test prompt.

    This function intelligently handles rate limits by waiting for them to reset
    rather than failing immediately. Retry behavior is managed by the @retry_with_backoff
    decorator with exponential backoff.

    Args:
        model_id: Full model ID to test
        max_retries: Maximum number of retry attempts (ignored, decorator controls)
        base_delay: Base delay in seconds between retries (ignored, decorator controls)

    Returns:
        True if model appears available, False otherwise

    """
    try:
        logger.info(f"Validating model '{model_id}'")
        result = _run_validation_attempt(model_id)
        return _handle_validation_result(model_id, result)
    except FileNotFoundError:
        logger.error("Claude CLI not found. Is it installed?")
        return False
    except RuntimeError:
        raise
    except Exception as e:
        logger.error(f"Validation error for model '{model_id}': {e}")
        raise RuntimeError(f"Validation failed for model '{model_id}'") from e
