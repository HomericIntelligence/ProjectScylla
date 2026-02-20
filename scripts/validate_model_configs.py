#!/usr/bin/env python3
"""Validation script for model configuration naming consistency.

Checks all YAML files in config/models/ to ensure the filename stem matches
the model_id field. Skips test fixtures (files prefixed with '_').

Usage:
    python scripts/validate_model_configs.py [config_dir]
    python scripts/validate_model_configs.py config/models/
    python scripts/validate_model_configs.py config/models/ --verbose

Exit codes:
    0 - All configs are consistent
    1 - One or more configs have inconsistencies
"""

import argparse
import sys
from pathlib import Path

import yaml

REQUIRED_FIELDS = ["model_id", "name", "provider", "adapter"]


def find_model_configs(config_dir: Path) -> list[Path]:
    """Find all production model config files (skip test fixtures prefixed with '_').

    Args:
        config_dir: Directory containing model config YAML files

    Returns:
        Sorted list of YAML file paths, excluding test fixtures

    """
    return sorted(f for f in config_dir.glob("*.yaml") if not f.name.startswith("_"))


def parse_model_config(file_path: Path) -> tuple[dict | None, str | None]:
    """Parse a YAML model config file.

    Args:
        file_path: Path to the YAML file

    Returns:
        Tuple of (parsed_dict, error_message).
        On success: (dict, None). On failure: (None, error_message).

    """
    try:
        with open(file_path) as f:
            content = yaml.safe_load(f)
        if not isinstance(content, dict):
            return None, f"Expected a YAML mapping, got {type(content).__name__}"
        return content, None
    except yaml.YAMLError as e:
        return None, f"YAML parse error: {e}"
    except OSError as e:
        return None, f"File read error: {e}"


def check_required_fields(config: dict, file_path: Path) -> list[str]:
    """Check that all required fields are present in the config.

    Args:
        config: Parsed model configuration dictionary
        file_path: Path to the config file (for error messages)

    Returns:
        List of error message strings (empty if all fields present)

    """
    errors = []
    for field in REQUIRED_FIELDS:
        if field not in config:
            errors.append(f"  Missing required field: '{field}'")
    return errors


def check_filename_consistency(config: dict, file_path: Path) -> list[str]:
    """Check that the filename stem is consistent with the model_id field.

    The filename stem must be a prefix of the model_id (allowing version suffixes
    like date stamps). For example:
      - claude-sonnet-4-5.yaml with model_id "claude-sonnet-4-5-20250929" -> OK
      - claude-opus-4-1.yaml  with model_id "claude-opus-4-1"            -> OK
      - claude-opus-4.yaml    with model_id "claude-opus-4-1"            -> OK (legacy)
      - wrong-name.yaml       with model_id "claude-opus-4-5-20250929"   -> FAIL

    Args:
        config: Parsed model configuration dictionary
        file_path: Path to the config file

    Returns:
        List of error message strings (empty if consistent)

    """
    errors = []
    model_id = config.get("model_id")
    if not model_id or not isinstance(model_id, str):
        return errors  # Missing field already reported by check_required_fields

    stem = file_path.stem

    # The filename stem must match the start of model_id.
    # model_id may have an additional version suffix (e.g. date stamp).
    # Acceptable: stem == model_id, or model_id starts with stem + "-"
    if model_id != stem and not model_id.startswith(stem + "-"):
        errors.append(
            f"  Filename mismatch:\n"
            f"    Filename stem : '{stem}'\n"
            f"    model_id      : '{model_id}'\n"
            f"    Fix           : Rename file to '{model_id}.yaml' "
            f"or update model_id to start with '{stem}'"
        )
    return errors


def validate_model_config(file_path: Path, verbose: bool = False) -> list[str]:
    """Validate a single model config file.

    Args:
        file_path: Path to the YAML config file
        verbose: Print verbose output

    Returns:
        List of error message strings (empty if valid)

    """
    errors = []

    config, parse_error = parse_model_config(file_path)
    if parse_error is not None:
        return [f"  {parse_error}"]

    assert config is not None  # parse_error is None means config is valid
    errors.extend(check_required_fields(config, file_path))
    errors.extend(check_filename_consistency(config, file_path))

    return errors


def main() -> int:
    """Run model config validation and return exit code.

    Returns:
        0 if all configs pass, 1 if any fail

    """
    parser = argparse.ArgumentParser(
        description="Validate model config filenames match their model_id fields"
    )
    parser.add_argument(
        "config_dir",
        nargs="?",
        default="config/models",
        help="Directory containing model config YAML files (default: config/models)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show details for passing files too"
    )
    args = parser.parse_args()

    config_dir = Path(args.config_dir)
    if not config_dir.is_dir():
        print(f"ERROR: Directory not found: {config_dir}", file=sys.stderr)
        return 1

    configs = find_model_configs(config_dir)
    if not configs:
        print(f"No model config files found in {config_dir}")
        return 0

    failed: list[Path] = []
    for config_file in configs:
        errors = validate_model_config(config_file, verbose=args.verbose)
        if errors:
            failed.append(config_file)
            print(f"FAIL: {config_file}")
            for error in errors:
                print(error)
        elif args.verbose:
            print(f"PASS: {config_file}")

    total = len(configs)
    passed = total - len(failed)
    print(f"\nChecked {total} file(s): {passed} passed, {len(failed)} failed.")

    if failed:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
