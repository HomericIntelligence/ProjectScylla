"""Configuration validation utilities."""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_REFERENCE_EXTENSIONS = ("*.yaml", "*.py")

# Model families to recognize in filenames
_MODEL_FAMILIES = {"sonnet", "opus", "haiku"}


def extract_model_family(stem: str) -> str | None:
    """Extract model family from filename stem.

    Searches for "sonnet", "opus", or "haiku" in the stem (case-insensitive).

    Args:
        stem: Filename stem (without extension)

    Returns:
        The model family ("sonnet", "opus", or "haiku") if found, None otherwise

    """
    if not stem:
        return None

    stem_lower = stem.lower()
    for family in _MODEL_FAMILIES:
        if family in stem_lower:
            return family

    return None


def validate_name_model_family_consistency(config_path: Path, name: str) -> list[str]:
    """Validate that model name contains the expected model family.

    Extracts the model family from the config filename and checks if the
    name field contains that family (case-insensitive). Skips test fixtures
    (prefixed with _).

    Args:
        config_path: Path to config file
        name: The model name field from config

    Returns:
        List of warning messages (empty if valid or family not recognized)

    """
    warnings = []
    filename_stem = config_path.stem

    # Skip validation for test fixtures
    if filename_stem.startswith("_"):
        return warnings

    family = extract_model_family(filename_stem)
    if family is None:
        # Unknown model family - no validation needed
        return warnings

    # Check if name contains the family (case-insensitive)
    if not name:
        warnings.append(
            f"Model name is empty but config filename '{filename_stem}.yaml' "
            f"indicates model family '{family}'"
        )
        return warnings

    if family.lower() not in name.lower():
        warnings.append(
            f"Model name '{name}' does not contain expected model family '{family}' "
            f"based on config filename '{filename_stem}.yaml'"
        )

    return warnings


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


def validate_defaults_filename(config_path: Path) -> list[str]:
    """Validate that the defaults config file is named 'defaults.yaml'.

    DefaultsConfig has no single ID field (unlike ModelConfig which has
    model_id), so field-level filename consistency is not applicable.
    This function checks only that the file stem is 'defaults' — catching
    accidental misconfiguration (e.g., loading the wrong file entirely).

    Args:
        config_path: Path to the defaults YAML file.

    Returns:
        List of warning strings; empty if validation passes.

    """
    warnings: list[str] = []
    if config_path.stem != "defaults":
        warnings.append(
            f"Defaults config loaded from unexpected filename "
            f"'{config_path.name}' (expected 'defaults.yaml'). "
            f"Note: DefaultsConfig has no ID field — filename consistency "
            f"validation is intentionally limited to stem check only."
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
