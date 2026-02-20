"""Configuration validation utilities."""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

KNOWN_FAMILIES: frozenset[str] = frozenset({"sonnet", "haiku", "opus"})


def get_expected_filename(model_id: str) -> str:
    """Get expected filename for a model_id.

    Converts model_id to valid filename format by replacing ':' with '-'.

    Args:
        model_id: Model identifier (e.g., 'claude-sonnet-4-5')

    Returns:
        Expected filename stem (without .yaml extension)

    """
    return model_id.replace(":", "-")


def extract_model_family(filename_stem: str) -> str | None:
    """Extract model family from filename stem.

    Splits the stem on '-' and returns the first part that matches a known
    model family (case-insensitive).

    Args:
        filename_stem: Filename without extension (e.g., 'claude-sonnet-4-5')

    Returns:
        Lowercase family name (e.g., 'sonnet'), or None if not recognized

    """
    for part in filename_stem.split("-"):
        if part.lower() in KNOWN_FAMILIES:
            return part.lower()
    return None


def validate_name_model_family_consistency(config_path: Path, name: str) -> list[str]:
    """Validate that the name field contains the model family from the filename.

    Derives the expected model family from the filename stem and checks that
    the human-readable name contains that family (case-insensitive). Skips
    test fixtures (stems prefixed with '_') and unknown families.

    Args:
        config_path: Path to the config file
        name: Human-readable name field from the config

    Returns:
        List of warning messages (empty if valid)

    """
    warnings = []
    filename_stem = config_path.stem

    if filename_stem.startswith("_"):
        return warnings

    family = extract_model_family(filename_stem)
    if family is None:
        return warnings

    if family not in name.lower():
        warnings.append(
            f"name '{name}' does not contain expected model family "
            f"'{family}' (derived from filename '{filename_stem}')"
        )

    return warnings


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
