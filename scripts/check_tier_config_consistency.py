#!/usr/bin/env python3
"""Enforce tier config filename/tier-id consistency as a pre-commit gate.

Scans all non-underscore-prefixed YAML files in config/tiers/, loads the
``tier`` field from each, and validates that the filename stem matches the
tier identifier. Exits 1 if any mismatch is found, blocking the commit.

Mirrors the pattern of check_model_config_consistency.py for model configs.

Usage:
    python scripts/check_tier_config_consistency.py
    python scripts/check_tier_config_consistency.py --config-dir config/tiers/
    python scripts/check_tier_config_consistency.py --verbose

Exit codes:
    0: No violations found
    1: One or more violations found
"""

import argparse
import sys
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scylla.config.validation import validate_filename_tier_consistency  # noqa: E402


def find_tier_configs(config_dir: Path) -> list[Path]:
    """Find all production tier config YAML files, skipping test fixtures.

    Args:
        config_dir: Directory containing tier config YAML files.

    Returns:
        Sorted list of YAML file paths, excluding files prefixed with ``_``.

    """
    return sorted(f for f in config_dir.glob("*.yaml") if not f.name.startswith("_"))


def _load_tier_id(path: Path) -> str | None:
    """Load the tier field from a YAML config file.

    Args:
        path: Path to the YAML file.

    Returns:
        The tier string, or None if the file cannot be read or lacks a tier field.

    """
    try:
        with path.open() as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            return None
        return data.get("tier")
    except Exception as exc:
        print(f"WARNING: Could not read {path}: {exc}", file=sys.stderr)
        return None


def check_configs(config_dir: Path, verbose: bool = False) -> int:
    """Check all tier configs in *config_dir* for filename/tier consistency.

    Args:
        config_dir: Directory to scan.
        verbose: If True, print each file checked.

    Returns:
        0 if all configs pass, 1 if any violations found.

    """
    tier_files = find_tier_configs(config_dir)
    violations: list[str] = []

    for yaml_path in tier_files:
        if verbose:
            print(f"  Checking: {yaml_path.name}")

        tier_id = _load_tier_id(yaml_path)
        if tier_id is None:
            violations.append(f"{yaml_path.name}: missing or unreadable 'tier' field")
            continue

        warnings = validate_filename_tier_consistency(yaml_path, tier_id)
        violations.extend(warnings)

    if violations:
        for v in violations:
            print(f"ERROR: {v}", file=sys.stderr)
        print(
            f"\n{len(violations)} violation(s) found in {config_dir}.",
            file=sys.stderr,
        )
        return 1

    if verbose:
        print(f"All {len(tier_files)} tier config(s) OK.")
    return 0


def main() -> int:
    """Entry point for check_tier_config_consistency script."""
    parser = argparse.ArgumentParser(
        description="Validate that config/tiers/*.yaml filenames match their tier field.",
    )
    parser.add_argument(
        "--config-dir",
        type=Path,
        default=_REPO_ROOT / "config" / "tiers",
        help="Override default config/tiers/ path",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show all checked files, not just violations",
    )
    args = parser.parse_args()

    config_dir: Path = args.config_dir
    if not config_dir.exists():
        # No tiers directory — nothing to validate
        return 0

    return check_configs(config_dir, verbose=args.verbose)


if __name__ == "__main__":
    sys.exit(main())
