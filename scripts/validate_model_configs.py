#!/usr/bin/env python3
"""Validate that config/models/*.yaml filenames match their model_id field.

Scans all non-underscore-prefixed YAML files in config/models/ and checks
that each filename stem matches the model_id field. Optionally renames
mismatched files with --fix.

Usage:
    python scripts/validate_model_configs.py [--fix] [--yes] [--models-dir PATH] [--verbose]

Exit codes:
    0  All configs OK (or fixes applied successfully)
    1  Mismatches found (--fix not passed)
    2  Error during fix (collision or I/O failure)
"""

import argparse
import sys
from pathlib import Path

import yaml
from common import get_repo_root

from scylla.config.validation import get_expected_filename, validate_filename_model_id_consistency

_REPO_ROOT = get_repo_root()
_CONFIG_MODELS_DIR = _REPO_ROOT / "config" / "models"


def _load_model_id(path: Path) -> str | None:
    """Load the model_id field from a YAML config file.

    Args:
        path: Path to the YAML file.

    Returns:
        The model_id string, or None if the file cannot be read or lacks model_id.

    """
    try:
        with path.open() as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            return None
        return data.get("model_id")
    except Exception as exc:
        print(f"WARNING: Could not read {path}: {exc}", file=sys.stderr)
        return None


def _collect_mismatches(models_dir: Path) -> list[tuple[Path, str, Path]]:
    """Collect all filename/model_id mismatches in models_dir.

    Args:
        models_dir: Directory containing model YAML configs.

    Returns:
        List of (current_path, model_id, expected_path) tuples for each mismatch.

    """
    mismatches: list[tuple[Path, str, Path]] = []
    for yaml_path in sorted(models_dir.glob("*.yaml")):
        model_id = _load_model_id(yaml_path)
        if model_id is None:
            continue
        warnings = validate_filename_model_id_consistency(yaml_path, model_id)
        if warnings:
            expected_stem = get_expected_filename(model_id)
            expected_path = yaml_path.parent / f"{expected_stem}.yaml"
            mismatches.append((yaml_path, model_id, expected_path))
    return mismatches


def _confirm_rename(current: Path, target: Path) -> bool:
    """Prompt the user to confirm a rename operation.

    Args:
        current: Current file path.
        target: Target file path after rename.

    Returns:
        True if the user confirms, False otherwise.

    """
    answer = input(f"Rename {current.name} → {target.name}? [y/N]: ").strip().lower()
    return answer == "y"


def _fix_mismatch(current: Path, target: Path, yes: bool) -> bool:
    """Attempt to rename a mismatched config file.

    Args:
        current: Current file path.
        target: Expected file path (rename destination).
        yes: If True, skip interactive confirmation.

    Returns:
        True on successful rename, False on failure.

    """
    if target.exists():
        print(
            f"ERROR: Cannot rename {current.name} → {target.name}: target already exists.",
            file=sys.stderr,
        )
        return False

    print(f"Renaming: {current} → {target}")

    if not yes and not _confirm_rename(current, target):
        print(f"Skipped: {current.name}")
        return True  # Skipped is not an error

    try:
        current.rename(target)
        print(f"Renamed: {current.name} → {target.name}")
        return True
    except OSError as exc:
        print(f"ERROR: Failed to rename {current.name}: {exc}", file=sys.stderr)
        return False


def main() -> None:
    """Entry point for validate_model_configs script."""
    parser = argparse.ArgumentParser(
        description="Validate that config/models/*.yaml filenames match their model_id field.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Rename mismatched files to {model_id}.yaml",
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Skip [y/N] confirmation (use with --fix for automation)",
    )
    parser.add_argument(
        "--models-dir",
        type=Path,
        default=_CONFIG_MODELS_DIR,
        help="Override default config/models/ path",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show all checked files, not just mismatches",
    )
    args = parser.parse_args()

    models_dir: Path = args.models_dir
    if not models_dir.exists():
        print(f"ERROR: models directory not found: {models_dir}", file=sys.stderr)
        sys.exit(2)

    print(f"Checking {models_dir}/*.yaml for filename/model_id mismatches...")

    if args.verbose:
        for yaml_path in sorted(models_dir.glob("*.yaml")):
            print(f"  Checking: {yaml_path.name}")

    mismatches = _collect_mismatches(models_dir)

    if not mismatches:
        print("All model configs OK.")
        sys.exit(0)

    # Report mismatches
    for current_path, model_id, expected_path in mismatches:
        print(f"\nMISMATCH: {current_path}")
        print(f"  filename stem : {current_path.stem}")
        print(f"  model_id      : {model_id}")
        print(f"  expected file : {expected_path}")

    if not args.fix:
        print(f"\n{len(mismatches)} mismatch(es) found. Re-run with --fix to rename automatically.")
        sys.exit(1)

    # Apply fixes
    print()
    all_ok = True
    for current_path, _model_id, expected_path in mismatches:
        if not _fix_mismatch(current_path, expected_path, args.yes):
            all_ok = False

    if not all_ok:
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
