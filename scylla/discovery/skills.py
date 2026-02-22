"""Skill discovery and organization.

Extracted from scripts/organize_skills.py to provide reusable discovery logic
for the dynamic benchmark generator.
"""

import shutil
from pathlib import Path

# Category mappings based on skill prefix and explicit names
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


def get_skill_category(skill_name: str) -> str:
    """Determine which category a skill belongs to.

    Uses explicit mapping first, then falls back to prefix-based matching.

    Args:
        skill_name: Name of the skill (directory or file name without extension)

    Returns:
        Category name ("github", "mojo", "workflow", etc.) or "other"

    Example:
        >>> get_skill_category("gh-review-pr")
        'github'
        >>> get_skill_category("mojo-format")
        'mojo'
        >>> get_skill_category("custom-skill")
        'other'

    """
    # Check explicit mappings first
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


def discover_skills(source_dir: Path) -> dict[str, list[Path]]:
    """Scan skills directory and classify by category.

    Args:
        source_dir: Directory containing skill directories/files

    Returns:
        Dictionary mapping category to list of skill paths (dirs or files)

    Example:
        >>> skills = discover_skills(Path(".claude/skills"))
        >>> skills["github"]
        [Path(".claude/skills/gh-review-pr"), ...]

    """
    # Get all skill directories (exclude template files and hidden dirs)
    skill_dirs = [d for d in source_dir.iterdir() if d.is_dir() and not d.name.startswith(".")]

    # Also get skill files that aren't directories
    skill_files = [
        f
        for f in source_dir.iterdir()
        if f.is_file() and f.suffix == ".md" and "TEMPLATE" not in f.name
    ]

    all_skills = skill_dirs + skill_files

    # Classify by category
    all_categories = [*list(CATEGORY_MAPPINGS.keys()), "other"]
    result: dict[str, list[Path]] = {cat: [] for cat in all_categories}

    for skill_path in all_skills:
        skill_name = skill_path.stem if skill_path.is_file() else skill_path.name
        category = get_skill_category(skill_name)
        result[category].append(skill_path)

    return result


def organize_skills(source_dir: Path, dest_dir: Path) -> dict[str, list[str]]:
    """Copy skills from source to destination, organized by category.

    Creates category subdirectories and copies skill directories/files into
    the appropriate category directory.

    Args:
        source_dir: Directory containing source skill dirs/files
        dest_dir: Destination directory (will create category subdirs)

    Returns:
        Dictionary mapping category to list of organized skill names

    Example:
        >>> organize_skills(
        ...     Path(".claude/skills"),
        ...     Path("tests/shared/skills")
        ... )
        {'github': ['gh-review-pr', ...], 'mojo': [...], ...}

    """
    # Ensure destination directories exist
    all_categories = [*list(CATEGORY_MAPPINGS.keys()), "other"]
    for category in all_categories:
        (dest_dir / category).mkdir(parents=True, exist_ok=True)

    # Discover and organize
    skills_by_category = discover_skills(source_dir)
    stats: dict[str, list[str]] = {cat: [] for cat in all_categories}

    for category, skill_paths in skills_by_category.items():
        for skill_path in skill_paths:
            skill_name = skill_path.stem if skill_path.is_file() else skill_path.name
            dest_path = dest_dir / category / skill_name

            if skill_path.is_dir():
                if dest_path.exists():
                    shutil.rmtree(dest_path)
                shutil.copytree(skill_path, dest_path)
            else:
                shutil.copy2(skill_path, dest_path.with_suffix(skill_path.suffix))

            stats[category].append(skill_name)

    return stats
