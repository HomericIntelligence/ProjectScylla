#!/usr/bin/env python3
"""Organize skills by category.

This script reads skill directories from ProjectOdyssey and organizes them
into category directories based on their prefix/function.
"""

import shutil
from pathlib import Path

# Source and destination directories
SOURCE_DIR = Path("/home/mvillmow/ProjectOdysseyManual/.claude/skills")
DEST_DIR = Path("/tmp/ProjectScylla/tests/claude-code/shared/skills")

# Category mappings based on skill prefix
CATEGORY_MAPPINGS = {
    "github": [
        "gh-review-pr",
        "gh-fix-pr-feedback",
        "gh-create-pr-linked",
        "gh-check-ci-status",
        "gh-implement-issue",
        "gh-reply-review-comment",
        "gh-get-review-comments",
        "gh-batch-merge-by-labels",
        "gh-read-issue-context",
        "gh-post-issue-update",
    ],
    "mojo": [
        "mojo-format",
        "mojo-test-runner",
        "mojo-build-package",
        "mojo-simd-optimize",
        "mojo-memory-check",
        "mojo-type-safety",
        "mojo-lint-syntax",
        "validate-mojo-patterns",
        "check-memory-safety",
        "analyze-simd-usage",
    ],
    "workflow": [
        "phase-plan-generate",
        "phase-test-tdd",
        "phase-implement",
        "phase-package",
        "phase-cleanup",
    ],
    "quality": [
        "quality-run-linters",
        "quality-fix-formatting",
        "quality-coverage-report",
        "quality-security-scan",
        "quality-complexity-check",
    ],
    "worktree": ["worktree-create", "worktree-cleanup", "worktree-switch", "worktree-sync"],
    "documentation": [
        "doc-generate-adr",
        "doc-issue-readme",
        "doc-update-blog",
        "doc-validate-markdown",
    ],
    "agent": [
        "agent-run-orchestrator",
        "agent-validate-config",
        "agent-test-delegation",
        "agent-coverage-check",
        "agent-hierarchy-diagram",
    ],
    "cicd": [
        "run-precommit",
        "validate-workflow",
        "fix-ci-failures",
        "install-workflow",
        "analyze-ci-failure-logs",
        "build-run-local",
        "verify-pr-ready",
        "merge-ready",
    ],
}

# Everything else goes to "other"


def get_skill_category(skill_name: str) -> str:
    """Determine which category a skill belongs to."""
    for category, skills in CATEGORY_MAPPINGS.items():
        if skill_name in skills:
            return category

    # Fallback pattern matching for skills not explicitly listed
    if skill_name.startswith("gh-"):
        return "github"
    if skill_name.startswith("mojo-"):
        return "mojo"
    if skill_name.startswith("phase-"):
        return "workflow"
    if skill_name.startswith("quality-"):
        return "quality"
    if skill_name.startswith("worktree-"):
        return "worktree"
    if skill_name.startswith("doc-"):
        return "documentation"
    if skill_name.startswith("agent-"):
        return "agent"

    return "other"


def organize_skills() -> None:
    """Organize all skills by their category."""
    # Get all skill directories (exclude template files)
    skill_dirs = [d for d in SOURCE_DIR.iterdir() if d.is_dir() and not d.name.startswith(".")]

    # Also get skill files that aren't directories
    skill_files = [
        f
        for f in SOURCE_DIR.iterdir()
        if f.is_file() and f.suffix == ".md" and "TEMPLATE" not in f.name
    ]

    print(f"Found {len(skill_dirs)} skill directories and {len(skill_files)} skill files")

    # Track statistics
    stats = {cat: [] for cat in list(CATEGORY_MAPPINGS.keys()) + ["other"]}

    # Organize directories
    for skill_dir in skill_dirs:
        skill_name = skill_dir.name
        category = get_skill_category(skill_name)

        dest_path = DEST_DIR / category / skill_name
        if dest_path.exists():
            shutil.rmtree(dest_path)
        shutil.copytree(skill_dir, dest_path)
        stats[category].append(skill_name)

    # Print results
    print("\nSkills organized by category:")
    for category in list(CATEGORY_MAPPINGS.keys()) + ["other"]:
        skills = stats[category]
        if skills:
            print(f"\n  {category}: {len(skills)} skills")
            for skill in sorted(skills):
                print(f"    - {skill}")

    total = sum(len(v) for v in stats.values())
    print(f"\nTotal: {total} skills organized")


def main():
    """Organize skill configuration files into category-based directories."""
    # Ensure destination directories exist
    for category in list(CATEGORY_MAPPINGS.keys()) + ["other"]:
        (DEST_DIR / category).mkdir(parents=True, exist_ok=True)

    organize_skills()


if __name__ == "__main__":
    main()
