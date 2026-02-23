"""Model validation utilities for E2E testing.

Extracted from scripts/run_e2e_experiment.py to be usable as a library module.
"""

from __future__ import annotations

import logging
import subprocess
import time

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


def validate_model(model_id: str, max_retries: int = 3, base_delay: int = 60) -> bool:
    """Validate that a model is available by running a test prompt.

    This function intelligently handles rate limits by waiting for them to reset
    rather than failing immediately.

    Args:
        model_id: Full model ID to test
        max_retries: Maximum number of retry attempts for rate limits
        base_delay: Base delay in seconds between retries

    Returns:
        True if model appears available, False otherwise

    """
    for attempt in range(max_retries + 1):
        try:
            logger.info(f"Validating model '{model_id}' (attempt {attempt + 1}/{max_retries + 1})")

            result = subprocess.run(
                [
                    "claude",
                    "--model",
                    model_id,
                    "--output-format",
                    "json",
                    "Say 'OK'",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            combined_output = result.stdout + result.stderr

            is_rate_limit, wait_time = is_rate_limit_error(combined_output)

            if is_rate_limit and attempt < max_retries:
                logger.warning(
                    f"Rate limit detected for model '{model_id}'. "
                    f"Waiting {wait_time} seconds before retry..."
                )
                time.sleep(wait_time)
                continue

            if result.returncode == 0 and '"is_error":false' in result.stdout:
                logger.info(f"✓ Model '{model_id}' validated successfully")
                return True
            else:
                if "not_found_error" in combined_output:
                    logger.warning(f"Model '{model_id}' not found on server")
                    return False
                elif attempt < max_retries:
                    logger.warning(
                        f"Validation attempt {attempt + 1} failed for model "
                        f"'{model_id}', retrying..."
                    )
                    time.sleep(base_delay * (2**attempt))
                    continue
                else:
                    logger.warning(f"All validation attempts failed for model '{model_id}'")
                    return False

        except subprocess.TimeoutExpired:
            if attempt < max_retries:
                logger.warning(f"Validation timed out for model '{model_id}', retrying...")
                time.sleep(base_delay)
                continue
            else:
                logger.warning(
                    f"Validation timed out for model '{model_id}' after {max_retries + 1} attempts"
                )
                return False
        except FileNotFoundError:
            logger.error("Claude CLI not found. Is it installed?")
            return False
        except Exception as e:
            if attempt < max_retries:
                logger.warning(f"Validation error for model '{model_id}': {e}, retrying...")
                time.sleep(base_delay)
                continue
            else:
                logger.error(f"Validation failed for model '{model_id}': {e}")
                return False

    return False
