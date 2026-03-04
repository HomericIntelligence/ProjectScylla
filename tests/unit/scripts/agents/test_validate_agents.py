"""Tests for scripts/agents/validate_agents.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from agents.validate_agents import (
    ValidationResult,
    extract_sections,
    validate_delegation_patterns,
    validate_frontmatter,
    validate_structure,
    validate_workflow_phases,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FULL_CONTENT = """\
---
name: test-agent
description: A test agent
tools: Read, Write
model: sonnet
---

## Role

This agent handles test scenarios.

## Scope

Limited to unit testing.

## Responsibilities

- Run tests
- Report results

## Workflow

Plan -> Test -> Review

## Constraints

No external calls.

## Evaluation Focus

Correctness and coverage.

## Delegation

Delegates To: junior-engineer
"""


def make_result(file_path: Path | None = None) -> ValidationResult:
    """Create a ValidationResult with a dummy file path."""
    return ValidationResult(file_path or Path("agent.md"))


# ---------------------------------------------------------------------------
# ValidationResult
# ---------------------------------------------------------------------------


class TestValidationResult:
    """Tests for ValidationResult class."""

    def test_starts_with_no_errors(self) -> None:
        """Fresh ValidationResult has no errors."""
        result = make_result()
        assert result.errors == []
        assert result.warnings == []

    def test_is_valid_with_no_errors(self) -> None:
        """is_valid() returns True when no errors added."""
        assert make_result().is_valid() is True

    def test_is_invalid_with_errors(self) -> None:
        """is_valid() returns False after an error is added."""
        result = make_result()
        result.add_error("Something went wrong")
        assert result.is_valid() is False

    def test_has_issues_with_warnings(self) -> None:
        """has_issues() returns True when warnings are present."""
        result = make_result()
        result.add_warning("Minor issue")
        assert result.has_issues() is True

    def test_no_issues_when_clean(self) -> None:
        """has_issues() returns False when no errors or warnings."""
        assert make_result().has_issues() is False


# ---------------------------------------------------------------------------
# extract_sections
# ---------------------------------------------------------------------------


class TestExtractSections:
    """Tests for extract_sections()."""

    def test_extracts_h2_headers(self) -> None:
        """Returns set of ## heading names."""
        content = "## Role\n\nContent\n\n## Scope\n"
        result = extract_sections(content)
        assert "Role" in result
        assert "Scope" in result

    def test_ignores_h1_and_h3(self) -> None:
        """Only ## headers are extracted."""
        content = "# Title\n### Sub\n## Real\n"
        result = extract_sections(content)
        assert "Real" in result
        assert "Title" not in result
        assert "Sub" not in result

    def test_empty_content(self) -> None:
        """Empty content returns empty set."""
        assert extract_sections("") == set()


# ---------------------------------------------------------------------------
# validate_frontmatter
# ---------------------------------------------------------------------------


class TestValidateFrontmatter:
    """Tests for validate_frontmatter()."""

    def test_passes_for_valid_frontmatter(self) -> None:
        """No errors for a fully valid frontmatter dict."""
        fm = {"name": "test-agent", "description": "Test", "tools": "Read", "model": "sonnet"}
        result = make_result()
        validate_frontmatter(fm, result)
        assert result.errors == []

    def test_error_for_missing_name(self) -> None:
        """Missing 'name' field adds an error."""
        fm = {"description": "Test", "tools": "Read", "model": "sonnet"}
        result = make_result()
        validate_frontmatter(fm, result)
        assert any("name" in e for e in result.errors)

    def test_error_for_invalid_model(self) -> None:
        """Invalid model name adds an error."""
        fm = {"name": "test-agent", "description": "T", "tools": "Read", "model": "gpt-4"}
        result = make_result()
        validate_frontmatter(fm, result)
        assert any("model" in e.lower() or "gpt-4" in e for e in result.errors)

    def test_error_for_invalid_name_format(self) -> None:
        """Name not in lowercase-hyphen format adds an error."""
        fm = {"name": "TestAgent", "description": "T", "tools": "Read", "model": "sonnet"}
        result = make_result()
        validate_frontmatter(fm, result)
        assert any("name" in e.lower() for e in result.errors)

    def test_warning_for_unknown_tool(self) -> None:
        """Unknown tool name adds a warning."""
        fm = {
            "name": "test-agent",
            "description": "T",
            "tools": "Read, UnknownTool",
            "model": "sonnet",
        }
        result = make_result()
        validate_frontmatter(fm, result)
        assert any("UnknownTool" in w for w in result.warnings)

    def test_error_for_empty_tools(self) -> None:
        """Empty tools field adds an error."""
        fm = {"name": "test-agent", "description": "T", "tools": "", "model": "sonnet"}
        result = make_result()
        validate_frontmatter(fm, result)
        assert any("tools" in e.lower() for e in result.errors)


# ---------------------------------------------------------------------------
# validate_structure
# ---------------------------------------------------------------------------


class TestValidateStructure:
    """Tests for validate_structure()."""

    def test_passes_with_all_required_sections(self) -> None:
        """No errors when all required sections are present."""
        result = make_result()
        validate_structure(FULL_CONTENT, result)
        assert result.errors == []

    def test_error_for_missing_required_section(self) -> None:
        """Missing required section adds an error."""
        content = "## Role\n\n## Scope\n"  # Missing many sections
        result = make_result()
        validate_structure(content, result)
        assert result.errors  # Should have missing section errors

    def test_warning_for_no_delegation_section(self) -> None:
        """Missing delegation section adds a warning."""
        # Content with required sections but no delegation info
        content = (
            "## Role\n\n## Scope\n\n## Responsibilities\n\n## Workflow\n\n"
            "## Constraints\n\n## Evaluation Focus\n"
        )
        result = make_result()
        validate_structure(content, result)
        assert any("delegation" in w.lower() for w in result.warnings)


# ---------------------------------------------------------------------------
# validate_workflow_phases
# ---------------------------------------------------------------------------


class TestValidateWorkflowPhases:
    """Tests for validate_workflow_phases()."""

    def test_no_warning_when_phases_mentioned(self) -> None:
        """No warning when at least 2 workflow phases are mentioned."""
        content = "This agent follows Plan and Test phases."
        result = make_result()
        validate_workflow_phases(content, result)
        assert not result.warnings

    def test_warning_when_no_phases_mentioned(self) -> None:
        """Warning when fewer than 2 workflow phases are in content."""
        content = "This agent does stuff."
        result = make_result()
        validate_workflow_phases(content, result)
        assert result.warnings


# ---------------------------------------------------------------------------
# validate_delegation_patterns
# ---------------------------------------------------------------------------


class TestValidateDelegationPatterns:
    """Tests for validate_delegation_patterns()."""

    def test_no_warning_for_junior_with_no_delegation(self, tmp_path: Path) -> None:
        """Junior engineer with 'No Delegation' gets no warning."""
        content = "No Delegation"
        fm = {"name": "junior-engineer"}
        result = ValidationResult(tmp_path / "junior.md")
        validate_delegation_patterns(content, fm, result)
        assert not result.warnings

    def test_warning_for_orchestrator_without_delegation(self, tmp_path: Path) -> None:
        """Orchestrator without delegation info gets a warning."""
        content = "## Role\n\nOrchestrates things."
        fm = {"name": "evaluation-orchestrator"}
        result = ValidationResult(tmp_path / "orch.md")
        validate_delegation_patterns(content, fm, result)
        assert any("delegation" in w.lower() for w in result.warnings)

    def test_no_warning_for_orchestrator_with_delegation(self, tmp_path: Path) -> None:
        """Orchestrator with delegation info gets no warning."""
        content = "Delegates To: specialist-agent"
        fm = {"name": "evaluation-orchestrator"}
        result = ValidationResult(tmp_path / "orch.md")
        validate_delegation_patterns(content, fm, result)
        assert not any("delegation" in w.lower() for w in result.warnings)

    def test_error_for_broken_agent_link(self, tmp_path: Path) -> None:
        """Broken link to another agent file adds an error."""
        content = "[some agent](./nonexistent-agent.md)"
        fm = {"name": "test-agent"}
        result = ValidationResult(tmp_path / "agent.md")
        validate_delegation_patterns(content, fm, result)
        assert any("nonexistent-agent" in e for e in result.errors)

    def test_no_error_for_valid_agent_link(self, tmp_path: Path) -> None:
        """Valid link to existing agent file adds no error."""
        other = tmp_path / "other-agent.md"
        other.write_text("# Other Agent")
        content = "[other agent](./other-agent.md)"
        fm = {"name": "test-agent"}
        result = ValidationResult(tmp_path / "agent.md")
        validate_delegation_patterns(content, fm, result)
        assert not result.errors
