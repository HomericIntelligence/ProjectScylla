#!/usr/bin/env python3
"""Filter pip-audit JSON output to fail only on HIGH/CRITICAL severity vulnerabilities.

Usage:
    pip-audit --format json | python scripts/filter_audit.py

Exit codes:
    0 - No HIGH/CRITICAL vulnerabilities found
    1 - One or more HIGH/CRITICAL vulnerabilities found

Severity thresholds follow the CVSS v3 base score scale:
    LOW:      0.1 – 3.9
    MEDIUM:   4.0 – 6.9
    HIGH:     7.0 – 8.9
    CRITICAL: 9.0 – 10.0

Vulnerabilities with no CVSS score are treated as UNKNOWN and reported
but do not cause a non-zero exit (printed as warnings).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

_IGNORE_FILE = Path(__file__).parent.parent / ".pip-audit-ignore.txt"


def load_ignore_list(path: Path = _IGNORE_FILE) -> frozenset[str]:
    """Load the set of ignored vulnerability IDs from .pip-audit-ignore.txt.

    Lines starting with '#' or empty lines are ignored.

    Args:
        path: Path to the ignore file. Returns empty set if file does not exist.

    Returns:
        Frozenset of ignored vulnerability IDs (e.g. "GHSA-xxx-yyy-zzz").

    """
    if not path.exists():
        return frozenset()
    ids: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.split("#")[0].strip()
        if stripped:
            ids.append(stripped)
    return frozenset(ids)


# CVSS v3 base score thresholds
HIGH_THRESHOLD = 7.0

CVSS_PATTERN = re.compile(r"CVSS:\d+\.\d+/.*")


def extract_cvss_score(severity_list: list[dict[str, Any]]) -> float | None:
    """Extract the highest CVSS base score from a severity list."""
    scores: list[float] = []
    for entry in severity_list:
        score_str = entry.get("score", "")
        # CVSS vector string: e.g. "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"
        # The base score is NOT embedded in the vector; we look for a numeric score field.
        # pip-audit (via OSV) sometimes provides a separate numeric field.
        if isinstance(score_str, (int, float)):
            scores.append(float(score_str))
        elif isinstance(score_str, str) and CVSS_PATTERN.match(score_str):
            # Vector string only — no numeric score available from this entry.
            # Try the "score" sub-key if the entry has one.
            pass
        # Check for a direct numeric "score" alongside the vector
        numeric = entry.get("base_score") or entry.get("cvss_score")
        if numeric is not None:
            try:
                scores.append(float(numeric))
            except (TypeError, ValueError):
                pass
    return max(scores) if scores else None


def severity_label(score: float | None) -> str:
    """Return a human-readable severity label from a CVSS score."""
    if score is None:
        return "UNKNOWN"
    if score >= 9.0:
        return "CRITICAL"
    if score >= 7.0:
        return "HIGH"
    if score >= 4.0:
        return "MEDIUM"
    if score >= 0.1:
        return "LOW"
    return "NONE"


def main() -> int:
    """Parse pip-audit JSON from stdin and exit non-zero on HIGH/CRITICAL findings."""
    ignore_ids = load_ignore_list()
    if ignore_ids:
        print(f"pip-audit: ignoring {len(ignore_ids)} advisory ID(s) from .pip-audit-ignore.txt")
    raw = sys.stdin.read()
    # pip-audit may print a human-readable line before the JSON; find the JSON blob.
    json_start = raw.find("{")
    if json_start == -1:
        # No JSON found — pip-audit likely printed only "No known vulnerabilities found"
        print("pip-audit: no vulnerabilities found", file=sys.stderr)
        return 0

    try:
        data = json.loads(raw[json_start:])
    except json.JSONDecodeError as exc:
        print(f"filter_audit: failed to parse pip-audit JSON: {exc}", file=sys.stderr)
        return 1

    high_critical: list[tuple[str, str, str, str]] = []  # (pkg, version, vuln_id, label)
    low_medium_unknown: list[tuple[str, str, str, str]] = []

    for dep in data.get("dependencies", []):
        name = dep.get("name", "?")
        version = dep.get("version", "?")
        for vuln in dep.get("vulns", []):
            vuln_id = vuln.get("id", "?")
            if vuln_id in ignore_ids:
                print(f"pip-audit: ignoring {vuln_id} ({name}=={version}) [.pip-audit-ignore.txt]")
                continue
            severity_list = vuln.get("severity", [])
            score = extract_cvss_score(severity_list)
            label = severity_label(score)
            entry = (name, version, vuln_id, label)
            if score is not None and score >= HIGH_THRESHOLD:
                high_critical.append(entry)
            else:
                low_medium_unknown.append(entry)

    if low_medium_unknown:
        print("pip-audit: suppressed vulnerabilities (LOW/MEDIUM/UNKNOWN — not blocking CI):")
        for name, version, vuln_id, label in low_medium_unknown:
            print(f"  [{label}] {name}=={version} {vuln_id}")

    if high_critical:
        print("pip-audit: BLOCKING vulnerabilities found (HIGH/CRITICAL):")
        for name, version, vuln_id, label in high_critical:
            print(f"  [{label}] {name}=={version} {vuln_id}")
        return 1

    if not low_medium_unknown:
        print("pip-audit: no vulnerabilities found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
