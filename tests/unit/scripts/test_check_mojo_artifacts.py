r"""Tests for the check-mojo-artifacts pre-commit hook regex pattern.

The hook uses pygrep with pattern ``(Mojo equivalents|no Mojo)`` against
files matching ``^scylla/.*\.py$``.  These tests unit-test that regex
directly, without invoking pre-commit itself.
"""

from __future__ import annotations

import re

import pytest

PATTERN = re.compile(r"(Mojo equivalents|no Mojo)")


@pytest.mark.parametrize(
    "line",
    [
        "# Mojo equivalents",
        "generate Mojo equivalents for all public functions",
        "# no Mojo",
        "has no Mojo support",
        "This function has no Mojo equivalent.",
        "# TODO: add Mojo equivalents later",
    ],
)
def test_pattern_matches_artifact_phrases(line: str) -> None:
    """Pattern must match lines containing the banned artifact phrases."""
    assert PATTERN.search(line) is not None, f"Expected match in: {line!r}"


@pytest.mark.parametrize(
    "line",
    [
        "# Mojo stdlib limitation",
        "mojo-format",
        "Python only",
        "# No mojo (lowercase)",
        "equivalent in Python",
        "# mojo equivalents (all lowercase)",
    ],
)
def test_pattern_does_not_match_legitimate_lines(line: str) -> None:
    """Pattern must not match legitimate lines that don't contain the banned phrases."""
    assert PATTERN.search(line) is None, f"Unexpected match in: {line!r}"
