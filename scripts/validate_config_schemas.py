#!/usr/bin/env python3
"""Validate config files against their JSON schemas as a pre-commit gate.

Receives file paths as positional arguments (via ``pass_filenames: true``) and
dispatches each file to the correct JSON schema based on path pattern.  Exits 1
if any validation error is found, blocking the commit.

Supported file patterns:
- ``config/defaults.yaml`` → ``schemas/defaults.schema.json``
- ``config/models/*.yaml`` → ``schemas/model.schema.json``
- ``tests/fixtures/config/tiers/*.yaml`` → ``schemas/tier.schema.json``

Usage:
    python scripts/validate_config_schemas.py config/defaults.yaml
    python scripts/validate_config_schemas.py config/models/claude-sonnet.yaml
    python scripts/validate_config_schemas.py --verbose config/defaults.yaml

Exit codes:
    0: All files valid (or no matching schema found — warned, not failed)
    1: One or more schema violations found
"""

import argparse
import json
import re
import sys
from pathlib import Path

import jsonschema
import yaml

_REPO_ROOT = Path(__file__).parent.parent

# Ordered list of (regex_pattern, schema_relative_path) pairs.
# The relative path is resolved against the repo root at runtime.
_SCHEMA_MAP: list[tuple[re.Pattern[str], Path]] = [
    (re.compile(r"^config/defaults\.yaml$"), Path("schemas/defaults.schema.json")),
    (re.compile(r"^config/models/.+\.yaml$"), Path("schemas/model.schema.json")),
    (
        re.compile(r"^tests/fixtures/config/tiers/.+\.yaml$"),
        Path("schemas/tier.schema.json"),
    ),
]


def resolve_schema(file_path: Path, repo_root: Path) -> Path | None:
    """Return the schema path for *file_path*, or ``None`` if no match.

    Args:
        file_path: Absolute or relative path to the config file.
        repo_root: Root of the repository (used to compute the relative path).

    Returns:
        Absolute path to the matching JSON schema file, or ``None``.

    """
    try:
        rel = file_path.resolve().relative_to(repo_root.resolve())
    except ValueError:
        # file_path is not under repo_root — try treating it as already relative
        rel = Path(str(file_path))

    rel_str = rel.as_posix()
    for pattern, schema_rel in _SCHEMA_MAP:
        if pattern.match(rel_str):
            return repo_root / schema_rel
    return None


def validate_file(file_path: Path, schema: dict[str, object]) -> list[str]:
    """Validate a YAML config file against *schema*.

    Args:
        file_path: Path to the YAML config file to validate.
        schema: Parsed JSON schema dict.

    Returns:
        List of human-readable error strings (empty list means valid).

    """
    try:
        with open(file_path) as fh:
            content = yaml.safe_load(fh)
    except (OSError, yaml.YAMLError) as exc:
        return [f"Could not read/parse YAML: {exc}"]

    errors: list[str] = []
    validator = jsonschema.Draft7Validator(schema)
    for error in sorted(validator.iter_errors(content), key=lambda e: list(e.path)):
        path = ".".join(str(p) for p in error.absolute_path) or "<root>"
        errors.append(f"  [{path}] {error.message}")
    return errors


def check_files(files: list[Path], repo_root: Path, verbose: bool = False) -> int:
    """Validate each file against its matching schema.

    Args:
        files: List of file paths to check.
        repo_root: Repository root used for schema resolution.
        verbose: If True, print ``PASS:`` lines for valid files.

    Returns:
        0 if all files are valid, 1 if any violations are found.

    """
    if not files:
        return 0

    schema_cache: dict[Path, dict[str, object]] = {}
    any_failure = False

    for file_path in files:
        schema_path = resolve_schema(file_path, repo_root)
        if schema_path is None:
            print(
                f"WARNING: No schema mapping for {file_path} — skipping",
                file=sys.stderr,
            )
            continue

        if schema_path not in schema_cache:
            try:
                schema_cache[schema_path] = json.loads(schema_path.read_text())
            except (OSError, json.JSONDecodeError) as exc:
                print(
                    f"ERROR: Could not load schema {schema_path}: {exc}",
                    file=sys.stderr,
                )
                any_failure = True
                continue

        errors = validate_file(file_path, schema_cache[schema_path])
        if errors:
            print(f"FAIL: {file_path}", file=sys.stderr)
            for error in errors:
                print(error, file=sys.stderr)
            any_failure = True
        elif verbose:
            print(f"PASS: {file_path}")

    return 1 if any_failure else 0


def main() -> int:
    """CLI entry point for config schema validation.

    Returns:
        Exit code (0 if clean, 1 if violations found).

    """
    parser = argparse.ArgumentParser(
        description="Validate config files against their JSON schemas",
        epilog="Example: %(prog)s config/defaults.yaml config/models/*.yaml",
    )
    parser.add_argument(
        "files",
        nargs="*",
        type=Path,
        help="Config files to validate (passed by pre-commit via pass_filenames: true)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print passing file names as well",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=_REPO_ROOT,
        help="Repository root for resolving schema paths (default: parent of this script)",
    )

    args = parser.parse_args()
    return check_files(args.files, args.repo_root, verbose=args.verbose)


if __name__ == "__main__":
    sys.exit(main())
