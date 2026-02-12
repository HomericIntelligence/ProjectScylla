#!/usr/bin/env python3
"""Comprehensive validation of agent configuration files.

This script performs comprehensive validation of agent configurations including:
- YAML frontmatter validity
- Required fields presence and types
- Tool names validation
- File structure and sections
- Delegation patterns
- Workflow phases

Usage:
    python scripts/agents/validate_agents.py [--verbose]
    python scripts/agents/validate_agents.py --help

Exit Codes:
    0 - All validations passed
    1 - Errors found in one or more files
"""

import argparse
import re
import sys
from pathlib import Path
from typing import Any

# Enable importing from repository root and scripts directory
_SCRIPT_DIR = Path(__file__).parent
_SCRIPTS_DIR = _SCRIPT_DIR.parent
_REPO_ROOT = _SCRIPTS_DIR.parent
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_SCRIPTS_DIR))
sys.path.insert(0, str(_SCRIPT_DIR))

from agent_utils import extract_frontmatter_parsed  # noqa: E402
from common import get_agents_dir, get_repo_root  # noqa: E402

# Required fields and their types
REQUIRED_FIELDS = {
    "name": str,
    "description": str,
    "tools": str,
    "model": str,
}

# Valid model names
VALID_MODELS = {
    "sonnet",
    "opus",
    "haiku",
    "claude-3-5-sonnet",
    "claude-3-opus",
    "claude-3-haiku",
}

# Valid tool names (based on common Claude Code tools)
VALID_TOOLS = {
    "Read",
    "Write",
    "Edit",
    "Grep",
    "Glob",
    "Bash",
    "WebFetch",
    "WebSearch",
    "TodoWrite",
    "SlashCommand",
    "AskUserQuestion",
    "NotebookEdit",
    "BashOutput",
    "KillShell",
}

# Required sections in agent markdown files
REQUIRED_SECTIONS = {
    "Role",
    "Scope",
    "Responsibilities",
    "Workflow",
    "Constraints",
    "Evaluation Focus",  # Scylla-specific
}

# Sections that should mention delegation
DELEGATION_SECTIONS = {
    "Delegation",
    "Delegates To",
    "Coordinates With",
    "No Delegation",  # For junior engineers
}

# Workflow phases for Scylla
WORKFLOW_PHASES = [
    "Plan",
    "Test",
    "Implementation",
    "Review",
]


class ValidationResult:
    """Result of validating an agent file."""

    def __init__(self, file_path: Path) -> None:
        """Initialize validation result.

        Args:
            file_path: Path to the agent file being validated

        """
        self.file_path: Path = file_path
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def add_error(self, message: str) -> None:
        """Add an error message."""
        self.errors.append(message)

    def add_warning(self, message: str) -> None:
        """Add a warning message."""
        self.warnings.append(message)

    def is_valid(self) -> bool:
        """Check if validation passed (no errors)."""
        return len(self.errors) == 0

    def has_issues(self) -> bool:
        """Check if there are any errors or warnings."""
        return len(self.errors) > 0 or len(self.warnings) > 0


def validate_frontmatter(frontmatter: dict[str, Any], result: ValidationResult) -> None:
    """Validate YAML frontmatter content.

    Args:
        frontmatter: Parsed frontmatter dictionary
        result: ValidationResult to add errors/warnings to

    """
    # Check required fields
    for field, expected_type in REQUIRED_FIELDS.items():
        if field not in frontmatter:
            result.add_error(f"Missing required field: '{field}'")
        else:
            value = frontmatter[field]
            if not isinstance(value, expected_type):
                expected = expected_type.__name__
                actual = type(value).__name__
                result.add_error(f"Field '{field}' should be {expected}, got {actual}")

    # Validate model
    if "model" in frontmatter:
        model = frontmatter["model"]
        if model not in VALID_MODELS:
            result.add_error(
                f"Invalid model '{model}'. Valid models: {', '.join(sorted(VALID_MODELS))}"
            )

    # Validate name format
    if "name" in frontmatter:
        name = frontmatter["name"]
        if not re.match(r"^[a-z][a-z0-9-]*$", name):
            result.add_error(
                f"Name '{name}' should be lowercase with hyphens (e.g., 'chief-architect')"
            )

    # Validate tools
    if "tools" in frontmatter:
        tools_str = frontmatter["tools"]
        if not tools_str.strip():
            result.add_error("Tools field cannot be empty")
        else:
            tools = [t.strip() for t in tools_str.split(",")]
            invalid_tools = [t for t in tools if t not in VALID_TOOLS]
            if invalid_tools:
                unknown = ", ".join(invalid_tools)
                valid = ", ".join(sorted(VALID_TOOLS))
                result.add_warning(f"Unknown tools: {unknown}. Valid tools: {valid}")


def extract_sections(content: str) -> set[str]:
    """Extract section headers from markdown content.

    Args:
        content: The markdown file content

    Returns:
        Set of section header texts (without ## prefix).

    """
    # Match level 2 headers (##)
    pattern = r"^##\s+(.+)$"
    headers = re.findall(pattern, content, re.MULTILINE)
    return set(headers)


def validate_structure(content: str, result: ValidationResult) -> None:
    """Validate file structure and required sections.

    Args:
        content: The markdown file content
        result: ValidationResult to add errors/warnings to

    """
    sections = extract_sections(content)

    # Check for required sections
    missing_sections = REQUIRED_SECTIONS - sections
    if missing_sections:
        result.add_error(f"Missing required sections: {', '.join(sorted(missing_sections))}")

    # Check for delegation information
    has_delegation_section = bool(DELEGATION_SECTIONS & sections)
    if not has_delegation_section:
        result.add_warning(
            "No delegation section found (should have 'Delegation' or 'No Delegation')"
        )


def validate_workflow_phases(content: str, result: ValidationResult) -> None:
    """Validate workflow phases are mentioned.

    Args:
        content: The markdown file content
        result: ValidationResult to add errors/warnings to

    """
    # Check if workflow phases are mentioned
    phases_found = [phase for phase in WORKFLOW_PHASES if phase in content]

    if len(phases_found) < 2:
        result.add_warning(
            f"Limited workflow phase coverage ({len(phases_found)}/{len(WORKFLOW_PHASES)}). "
            f"Consider mentioning: {', '.join(WORKFLOW_PHASES)}"
        )


def validate_delegation_patterns(
    content: str, frontmatter: dict[str, Any], result: ValidationResult
) -> None:
    """Validate delegation patterns are properly defined.

    Args:
        content: The markdown file content
        frontmatter: Parsed frontmatter
        result: ValidationResult to add errors/warnings to

    """
    agent_name = frontmatter.get("name", "")

    # Junior engineers should have "No Delegation"
    if "junior" in agent_name.lower():
        if "No Delegation" not in content and "no delegation" not in content.lower():
            result.add_warning("Junior engineers should explicitly state 'No Delegation'")
        return

    # Other agents should have delegation information
    delegation_keywords = [
        "Delegates To",
        "delegates to",
        "Coordinates With",
        "coordinates with",
    ]
    has_delegation = any(keyword in content for keyword in delegation_keywords)

    if not has_delegation and "orchestrator" in agent_name.lower():
        result.add_warning("Orchestrators should define delegation patterns")

    # Check for markdown links to other agents
    agent_links = re.findall(r"\[([^\]]+)\]\(\./([^)]+)\.md\)", content)
    if agent_links:
        # Validate linked files exist
        agents_dir = result.file_path.parent
        for link_text, link_target in agent_links:
            linked_file = agents_dir / f"{link_target}.md"
            if not linked_file.exists():
                result.add_error(f"Broken link to agent: {link_target}.md")


def validate_workflow_phase(content: str, result: ValidationResult) -> None:
    """Validate that workflow phase is defined.

    Args:
        content: The markdown file content
        result: ValidationResult to add errors/warnings to

    """
    workflow_phases = ["Plan", "Test", "Implementation", "Packaging", "Cleanup"]

    # Check for "Workflow Phase" section
    if "Workflow Phase" not in content and "## Workflow" not in content:
        result.add_warning("No 'Workflow Phase' section found")
        return

    # Check if at least one workflow phase is mentioned
    mentioned_phases = [phase for phase in workflow_phases if phase in content]
    if not mentioned_phases:
        result.add_warning(
            f"No workflow phases mentioned. Expected one of: {', '.join(workflow_phases)}"
        )


def validate_file(file_path: Path, verbose: bool = False) -> ValidationResult:
    """Perform comprehensive validation of an agent configuration file.

    Args:
        file_path: Path to the agent markdown file
        verbose: Whether to perform extra checks

    Returns:
        ValidationResult with all errors and warnings

    """
    result: ValidationResult = ValidationResult(file_path)

    # Read file
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        result.add_error(f"Failed to read file: {e}")
        return result

    # Extract and validate frontmatter
    fm_result = extract_frontmatter_parsed(content)
    if fm_result is None:
        result.add_error("No valid YAML frontmatter found")
        return result

    frontmatter_text, frontmatter = fm_result
    validate_frontmatter(frontmatter, result)

    # Validate file structure
    validate_structure(content, result)

    # Validate workflow phases
    validate_workflow_phases(content, result)

    # Validate delegation patterns
    validate_delegation_patterns(content, frontmatter, result)

    # Validate workflow phase (single phase check)
    validate_workflow_phase(content, result)

    # Check file length (should be substantive)
    lines = content.split("\n")
    if len(lines) < 50:
        result.add_warning(f"File is short ({len(lines)} lines). Consider adding more detail.")

    # Check for Skills section
    if verbose:
        if "Skills to Use" not in content and "Skills" not in content:
            result.add_warning("No 'Skills to Use' section found")

        # Check for Error Handling section
        if "Error Handling" not in content:
            result.add_warning("No 'Error Handling' section found")

    return result


def main() -> int:
    """Run the agent validation script."""
    parser = argparse.ArgumentParser(
        description="Comprehensive validation of agent configuration files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Validation Checks:
    - YAML frontmatter syntax and required fields
    - Tool names are valid
    - Required sections present (Role, Scope, Responsibilities, etc.)
    - Delegation patterns defined
    - Workflow phases specified
    - Links to other agents are valid

Examples:
    # Validate all agent files
    python scripts/agents/validate_agents.py

    # Validate with verbose output
    python scripts/agents/validate_agents.py --verbose

    # Show warnings as well as errors
    python scripts/agents/validate_agents.py --verbose
        """,
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show verbose output including warnings",
    )
    parser.add_argument(
        "--agents-dir",
        type=Path,
        default=None,  # Will use get_agents_dir() if not specified
        help="Path to agents directory (default: .claude/agents)",
    )

    args = parser.parse_args()

    # Get repository root
    try:
        repo_root = get_repo_root()
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    # Determine agents directory
    if args.agents_dir is None:
        agents_dir = get_agents_dir()
    else:
        agents_dir = repo_root / args.agents_dir

    if not agents_dir.exists():
        print(f"Error: Agents directory not found: {agents_dir}", file=sys.stderr)
        return 1

    if not agents_dir.is_dir():
        print(f"Error: Not a directory: {agents_dir}", file=sys.stderr)
        return 1

    # Find all markdown files
    agent_files = sorted(agents_dir.glob("*.md"))

    if not agent_files:
        print(f"Error: No .md files found in {agents_dir}", file=sys.stderr)
        return 1

    rel_path = agents_dir.relative_to(repo_root)
    count = len(agent_files)
    print(f"Validating {count} agent configuration files in {rel_path}/\n")

    # Validate each file
    results = []
    for file_path in agent_files:
        result = validate_file(file_path, verbose=args.verbose)
        results.append(result)

        # Display results
        if not result.has_issues():
            if args.verbose:
                print(f"✓ {file_path.name}")
        else:
            print(f"{'✗' if result.errors else '⚠'} {file_path.name}")

            if result.errors:
                print("  Errors:")
                for error in result.errors:
                    print(f"    - {error}")

            if result.warnings and args.verbose:
                print("  Warnings:")
                for warning in result.warnings:
                    print(f"    - {warning}")

            print()

    # Summary
    print("=" * 70)

    total_files = len(results)
    files_with_errors = sum(1 for r in results if r.errors)
    files_with_warnings = sum(1 for r in results if r.warnings)
    total_errors = sum(len(r.errors) for r in results)
    total_warnings = sum(len(r.warnings) for r in results)

    print(f"Total files:     {total_files}")
    print(f"Files with errors:   {files_with_errors}")
    print(f"Files with warnings: {files_with_warnings}")
    print(f"Total errors:    {total_errors}")
    print(f"Total warnings:  {total_warnings}")

    if files_with_errors == 0:
        print("\n✓ All agent files passed validation")
        return 0
    else:
        print(f"\n✗ {files_with_errors} file(s) have errors")
        return 1


if __name__ == "__main__":
    sys.exit(main())
