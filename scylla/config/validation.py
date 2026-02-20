"""Configuration validation utilities."""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def get_expected_filename(model_id: str) -> str:
    """Get expected filename for a model_id.

    Converts model_id to valid filename format by replacing ':' with '-'.

    Args:
        model_id: Model identifier (e.g., 'claude-sonnet-4-5')

    Returns:
        Expected filename stem (without .yaml extension)

    """
    return model_id.replace(":", "-")


def validate_filename_model_id_consistency(config_path: Path, model_id: str) -> list[str]:
    """Validate config filename matches model_id.

    Checks two patterns:
    1. Exact match: filename.stem == model_id
    2. Simplified match: normalized versions match (: → -)

    Args:
        config_path: Path to config file
        model_id: model_id field from config

    Returns:
        List of warning messages (empty if valid)

    """
    warnings = []
    filename_stem = config_path.stem

    # Skip validation for test fixtures (prefixed with _)
    if filename_stem.startswith("_"):
        return warnings

    # Check exact match
    if filename_stem == model_id:
        return warnings

    # Check simplified match
    expected = get_expected_filename(model_id)
    if filename_stem == expected:
        return warnings

    # Mismatch detected
    warnings.append(
        f"Config filename '{filename_stem}.yaml' does not match model_id "
        f"'{model_id}'. Expected '{expected}.yaml'"
    )

    return warnings


def validate_filename_tier_consistency(config_path: Path, tier: str) -> list[str]:
    """Validate that config filename matches the tier field.

    Args:
        config_path: Path to config file
        tier: tier field from config (e.g., 't0')

    Returns:
        List of warning messages (empty if valid)

    """
    warnings = []
    filename_stem = config_path.stem

    # Skip validation for test fixtures (prefixed with _)
    if filename_stem.startswith("_"):
        return warnings

    # Check exact match
    if filename_stem == tier:
        return warnings

    # Mismatch detected
    warnings.append(
        f"Config filename '{filename_stem}.yaml' does not match tier "
        f"'{tier}'. Expected '{tier}.yaml'"
    )

    return warnings
