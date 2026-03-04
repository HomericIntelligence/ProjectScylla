#!/usr/bin/env python3
"""Check Python docstrings for genuine sentence fragments.

Parses Python source files using the ``ast`` module to extract docstrings as
complete strings (not line-by-line), then validates that the first sentence of
each docstring is not a genuine fragment.

This prevents the false-positive class of errors where a correctly wrapped
multi-line docstring is flagged as a fragment because the continuation line
is evaluated in isolation — the triggering case from the March 2026 audit of
``scylla/executor/runner.py`` lines 4-5.

A **genuine fragment** is a docstring whose first line, when taken alone, is
clearly a partial sentence continuation (e.g., starts with a lowercase
connector word like ``"across"``, ``"and"``, ``"or"``, ``"but"``).  Normal
noun-phrase summaries and complete sentences are always allowed.

Excluded paths (archived / test-fixture content that is not authoritative):
  - ``.pixi/``
  - ``build/``
  - ``node_modules/``
  - ``tests/claude-code/``

Usage::

    python scripts/check_docstring_fragments.py
    python scripts/check_docstring_fragments.py --verbose

Exit codes:
    0: No violations found
    1: One or more violations found
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path

from scylla.automation.git_utils import get_repo_root

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class FragmentFinding:
    """A genuine docstring fragment found in a Python source file."""

    file: str
    line: int
    docstring_first_line: str
    context: str

    def format(self) -> str:
        """Return a human-readable description of this finding."""
        return (
            f"  {self.file}:{self.line}\n"
            f"    Context: {self.context}\n"
            f"    First line: {self.docstring_first_line!r}\n"
        )


# ---------------------------------------------------------------------------
# Fragment detection logic
# ---------------------------------------------------------------------------

# Lowercase connector words that indicate a line is a mid-sentence continuation
# rather than the start of a valid docstring.
_CONTINUATION_STARTERS = frozenset(
    {
        "across",
        "after",
        "against",
        "along",
        "also",
        "although",
        "among",
        "and",
        "around",
        "as",
        "at",
        "because",
        "before",
        "beneath",
        "beside",
        "between",
        "beyond",
        "but",
        "by",
        "despite",
        "during",
        "except",
        "for",
        "from",
        "hence",
        "however",
        "if",
        "in",
        "including",
        "instead",
        "into",
        "nor",
        "of",
        "on",
        "or",
        "over",
        "plus",
        "since",
        "so",
        "than",
        "that",
        "the",
        "then",
        "thereby",
        "therefore",
        "though",
        "through",
        "throughout",
        "thus",
        "to",
        "toward",
        "under",
        "unless",
        "until",
        "upon",
        "via",
        "when",
        "where",
        "whereas",
        "whether",
        "which",
        "while",
        "with",
        "within",
        "without",
        "yet",
    }
)


def _is_genuine_fragment(docstring: str) -> bool:
    """Return True if the docstring's first line is a genuine sentence fragment.

    A genuine fragment is detected when the very first non-empty line of the
    docstring starts with a lowercase continuation word (e.g. ``"across"``,
    ``"and"``, ``"or"``).  This catches cases where an auditor's line-by-line
    tool would flag the second line of a wrapped sentence as a standalone
    docstring.

    Normal noun-phrase titles, imperative sentences, and complete sentences all
    start with a capitalised word or a recognised technical prefix and are
    therefore not flagged.
    """
    lines = docstring.splitlines()
    # Find the first non-empty line
    first_line = ""
    for line in lines:
        stripped = line.strip()
        if stripped:
            first_line = stripped
            break

    if not first_line:
        return False

    # Extract the first word
    first_word = first_line.split()[0].rstrip(".,;:!?")

    # A genuine fragment starts with a pure lowercase continuation word
    # (not a capitalised word, not a technical token, not an abbreviation).
    if first_word and first_word == first_word.lower() and first_word.isalpha():
        return first_word in _CONTINUATION_STARTERS

    return False


# ---------------------------------------------------------------------------
# AST-based docstring extraction
# ---------------------------------------------------------------------------


def _context_label(node: ast.AST) -> str:
    """Return a human-readable label for the AST node containing a docstring."""
    if isinstance(node, ast.Module):
        return "module"
    if isinstance(node, ast.ClassDef):
        return f"class {node.name}"
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return f"def {node.name}"
    return "unknown"


def _docstring_nodes(
    tree: ast.Module,
) -> list[tuple[ast.AST, str, int]]:
    """Yield (node, docstring_text, line_number) for all docstring-bearing nodes."""
    results: list[tuple[ast.AST, str, int]] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body = getattr(node, "body", [])
        if not body:
            continue
        first_stmt = body[0]
        if not isinstance(first_stmt, ast.Expr):
            continue
        value = first_stmt.value
        if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
            continue
        results.append((node, value.value, first_stmt.lineno))

    return results


def scan_file(file_path: Path, repo_root: Path) -> list[FragmentFinding]:
    """Scan a single Python file and return genuine fragment findings."""
    findings: list[FragmentFinding] = []
    try:
        source = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return findings

    try:
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError:
        return findings

    relative_path = str(file_path.relative_to(repo_root))

    for node, docstring, lineno in _docstring_nodes(tree):
        if _is_genuine_fragment(docstring):
            first_line = next((ln.strip() for ln in docstring.splitlines() if ln.strip()), "")
            findings.append(
                FragmentFinding(
                    file=relative_path,
                    line=lineno,
                    docstring_first_line=first_line,
                    context=_context_label(node),
                )
            )

    return findings


# ---------------------------------------------------------------------------
# Paths to exclude from scanning
# ---------------------------------------------------------------------------

EXCLUDED_PREFIXES = (
    ".pixi/",
    ".worktrees/",
    ".claude/worktrees/",
    "build/",
    "node_modules/",
    "tests/claude-code/",
)


def scan_repository(repo_root: Path) -> list[FragmentFinding]:
    """Scan all non-excluded Python files in the repository."""
    all_findings: list[FragmentFinding] = []

    for py_file in sorted(repo_root.rglob("*.py")):
        relative = py_file.relative_to(repo_root)
        relative_str = str(relative).replace("\\", "/")
        if any(relative_str.startswith(prefix) for prefix in EXCLUDED_PREFIXES):
            continue
        all_findings.extend(scan_file(py_file, repo_root))

    return all_findings


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def format_report(findings: list[FragmentFinding]) -> str:
    """Format findings as a human-readable text report."""
    if not findings:
        return "No docstring fragment violations found.\n"

    lines: list[str] = [
        f"Found {len(findings)} genuine docstring fragment(s):",
        "",
    ]
    for f in findings:
        lines.append(f.format())

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    """Run the docstring fragment check."""
    repo_root = get_repo_root()
    findings = scan_repository(repo_root)

    print(format_report(findings))

    return 0 if not findings else 1


if __name__ == "__main__":
    sys.exit(main())
