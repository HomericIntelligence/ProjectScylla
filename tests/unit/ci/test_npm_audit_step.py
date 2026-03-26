"""Regression tests for the npm audit CI step in docker-test.yml.

Verifies that the Docker validation workflow contains a non-blocking npm audit
step that checks for high/critical vulnerabilities and reports via annotations.
Issue: #1592
"""

from __future__ import annotations

from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DOCKER_TEST_WORKFLOW = _PROJECT_ROOT / ".github" / "workflows" / "docker-test.yml"


def test_npm_audit_step_exists() -> None:
    """docker-test.yml must contain an npm audit step."""
    content = _DOCKER_TEST_WORKFLOW.read_text()
    assert "npm audit" in content, "docker-test.yml is missing the npm audit step (issue #1592)"


def test_npm_audit_uses_high_level() -> None:
    """Npm audit step must use --audit-level=high."""
    content = _DOCKER_TEST_WORKFLOW.read_text()
    assert "--audit-level=high" in content, (
        "npm audit step must use --audit-level=high to filter noise"
    )


def test_npm_audit_is_non_blocking() -> None:
    """Npm audit step must use continue-on-error: true."""
    content = _DOCKER_TEST_WORKFLOW.read_text()
    lines = content.splitlines()
    in_audit_step = False
    found_continue_on_error = False
    for line in lines:
        if "npm audit" in line and "name:" in line.lower():
            in_audit_step = True
        elif in_audit_step and "continue-on-error: true" in line:
            found_continue_on_error = True
            break
        elif in_audit_step and line.strip().startswith("- name:"):
            break
    assert found_continue_on_error, (
        "npm audit step must have continue-on-error: true to avoid blocking PRs"
    )


def test_npm_audit_emits_warning_annotation() -> None:
    """Npm audit step must emit a ::warning:: annotation on findings."""
    content = _DOCKER_TEST_WORKFLOW.read_text()
    assert "::warning" in content and "npm audit" in content, (
        "npm audit step must emit ::warning:: annotations for visibility"
    )
