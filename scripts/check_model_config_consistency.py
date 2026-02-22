#!/usr/bin/env python3
"""Enforce model config filename/model_id consistency as a pre-commit gate.

Scans all YAML files in config/models/, loads the ``model_id`` field from each,
and calls ``validate_filename_model_id_consistency`` from
``scylla.config.validation``.  Exits 1 if any mismatch is found, blocking the
commit.

Usage:
    python scripts/check_model_config_consistency.py
    python scripts/check_model_config_consistency.py --config-dir config/models/
    python scripts/check_model_config_consistency.py --verbose

Exit codes:
    0: No violations found
    1: One or more violations found
"""

import argparse
import sys
from pathlib import Path

import yaml

# Repo root is the parent of this script's directory so that imports work when
# invoked from pre-commit (which may not add the repo root to sys.path).
_REPO_ROOT = Path(__file__).parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scylla.config.validation import validate_filename_model_id_consistency  # noqa: E402


def find_model_configs(config_dir: Path) -> list[Path]:
    """Find all production model config YAML files, skipping test fixtures.

    Args:
        config_dir: Directory containing model config YAML files.

    Returns:
        Sorted list of YAML file paths, excluding files prefixed with ``_``.

    """
    return sorted(f for f in config_dir.glob("*.yaml") if not f.name.startswith("_"))


def check_configs(config_dir: Path, verbose: bool = False) -> int:  # noqa: C901  # config validation with many checks
    """Check all model configs in *config_dir* for filename/model_id consistency.

    For each YAML file the function:
    1. Loads the ``model_id`` field with ``yaml.safe_load``.
    2. Calls ``validate_filename_model_id_consistency`` from
       ``scylla.config.validation``.
    3. Collects all warnings and prints them to stderr.

    Args:
        config_dir: Directory containing model config YAML files.
        verbose: If True, also print passing file names to stdout.

    Returns:
        0 if all configs are consistent, 1 if any violation is found.

    """
    if not config_dir.is_dir():
        print(f"ERROR: Directory not found: {config_dir}", file=sys.stderr)
        return 1

    configs = find_model_configs(config_dir)
    if not configs:
        if verbose:
            print(f"No model config files found in {config_dir}")
        return 0

    all_violations: list[str] = []

    for config_file in configs:
        try:
            with open(config_file) as f:
                content = yaml.safe_load(f)
        except (OSError, yaml.YAMLError) as exc:
            all_violations.append(f"{config_file}: Could not read/parse YAML: {exc}")
            continue

        if not isinstance(content, dict):
            all_violations.append(
                f"{config_file}: Expected a YAML mapping, got {type(content).__name__}"
            )
            continue

        model_id = content.get("model_id")
        if not model_id or not isinstance(model_id, str):
            all_violations.append(f"{config_file}: Missing or invalid 'model_id' field")
            continue

        warnings = validate_filename_model_id_consistency(config_file, model_id)
        if warnings:
            for warning in warnings:
                all_violations.append(f"{config_file}: {warning}")
        elif verbose:
            print(f"PASS: {config_file}")

    if all_violations:
        for violation in all_violations:
            print(violation, file=sys.stderr)
        print(
            f"\nFound {len(all_violations)} model config consistency violation(s).",
            file=sys.stderr,
        )
        return 1

    return 0


def main() -> int:
    """CLI entry point for model config consistency checking.

    Returns:
        Exit code (0 if clean, 1 if violations found).

    """
    parser = argparse.ArgumentParser(
        description="Enforce model config filename/model_id consistency",
        epilog="Example: %(prog)s --config-dir config/models/",
    )
    parser.add_argument(
        "--config-dir",
        type=Path,
        default=Path("config/models"),
        help="Directory containing model config YAML files (default: config/models)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print passing file names as well",
    )

    args = parser.parse_args()
    return check_configs(args.config_dir, verbose=args.verbose)


if __name__ == "__main__":
    sys.exit(main())
