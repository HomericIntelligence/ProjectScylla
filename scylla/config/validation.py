"""Configuration validation utilities."""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_REFERENCE_EXTENSIONS = ("*.yaml", "*.py")


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


def validate_model_config_referenced(config_path: Path, search_roots: list[Path]) -> list[str]:
    """Warn if model config file is not referenced by any file under search_roots.

    Scans .yaml and .py files under each root for the config's filename stem.
    Skips _-prefixed test fixtures. Does not count the config file itself as
    a reference.

    Args:
        config_path: Path to the model config file
        search_roots: Directories to search for references

    Returns:
        List of warning messages (empty if referenced or a test fixture)

    """
    stem = config_path.stem

    # Skip test fixtures
    if stem.startswith("_"):
        return []

    for root in search_roots:
        if not root.exists():
            continue
        for ext_pattern in _REFERENCE_EXTENSIONS:
            for f in root.rglob(ext_pattern):
                if f == config_path:
                    continue  # don't count self as reference
                try:
                    if stem in f.read_text(encoding="utf-8", errors="ignore"):
                        return []
                except (OSError, PermissionError):
                    continue

    return [
        f"Model config '{config_path.name}' is not referenced by any file under "
        f"{[str(r) for r in search_roots]}. It may be orphaned."
    ]
