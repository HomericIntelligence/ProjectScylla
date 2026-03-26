"""Regression tests ensuring all GitHub Actions references are SHA-pinned.

Verifies that all external ``uses:`` references in workflow and composite action
YAML files use immutable full commit SHAs (40 hex chars) instead of mutable
version tags, with the original version retained as a trailing comment.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# Project root — two levels above tests/unit/ci/
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_GITHUB_DIR = _PROJECT_ROOT / ".github"

# Patterns
_USES_LINE_RE = re.compile(r"^\s*-?\s*uses:\s*(.+)$")
_LOCAL_ACTION_RE = re.compile(r"^\./")
_SHA_REF_RE = re.compile(r"^[\w./-]+@([0-9a-f]{40})\s+#\s+\S+")
_MUTABLE_VTAG_RE = re.compile(r"@v\d+")
_BARE_SEMVER_RE = re.compile(r"@\d+\.\d+")


def _collect_yaml_files() -> list[Path]:
    """Collect all YAML files under .github/ recursively."""
    return sorted(_GITHUB_DIR.rglob("*.yml"))


def _extract_uses_lines(path: Path) -> list[tuple[int, str]]:
    """Extract (line_number, uses_value) pairs from a YAML file."""
    results: list[tuple[int, str]] = []
    for i, line in enumerate(path.read_text().splitlines(), start=1):
        m = _USES_LINE_RE.match(line)
        if m:
            value = m.group(1).strip()
            if not _LOCAL_ACTION_RE.match(value):
                results.append((i, value))
    return results


_YAML_FILES = _collect_yaml_files()


@pytest.mark.parametrize(
    "yaml_file",
    _YAML_FILES,
    ids=[str(p.relative_to(_PROJECT_ROOT)) for p in _YAML_FILES],
)
def test_no_mutable_version_tags(yaml_file: Path) -> None:
    """Every external uses: ref must not use a mutable v-tag (e.g. @v6)."""
    violations: list[str] = []
    for lineno, value in _extract_uses_lines(yaml_file):
        if _MUTABLE_VTAG_RE.search(value) and "#" not in value:
            violations.append(f"  {yaml_file}:{lineno}: {value}")
    assert not violations, (
        "Found mutable version tag references (supply chain risk):\n" + "\n".join(violations)
    )


@pytest.mark.parametrize(
    "yaml_file",
    _YAML_FILES,
    ids=[str(p.relative_to(_PROJECT_ROOT)) for p in _YAML_FILES],
)
def test_sha_pinned_refs_have_version_comments(yaml_file: Path) -> None:
    """Every SHA-pinned uses: ref must have a trailing # version comment."""
    violations: list[str] = []
    for lineno, value in _extract_uses_lines(yaml_file):
        # Check if it looks SHA-pinned (40 hex chars after @)
        if re.search(r"@[0-9a-f]{40}", value) and "#" not in value:
            violations.append(f"  {yaml_file}:{lineno}: {value}")
    assert not violations, "Found SHA-pinned refs without version comment:\n" + "\n".join(
        violations
    )


@pytest.mark.parametrize(
    "yaml_file",
    _YAML_FILES,
    ids=[str(p.relative_to(_PROJECT_ROOT)) for p in _YAML_FILES],
)
def test_no_bare_semver_tags(yaml_file: Path) -> None:
    """No external uses: ref should use a bare semver tag without SHA pinning."""
    violations: list[str] = []
    for lineno, value in _extract_uses_lines(yaml_file):
        # Has a semver-like tag but no 40-char hex SHA
        if _BARE_SEMVER_RE.search(value) and not re.search(r"@[0-9a-f]{40}", value):
            violations.append(f"  {yaml_file}:{lineno}: {value}")
    assert not violations, "Found bare semver tag references (should be SHA-pinned):\n" + "\n".join(
        violations
    )
