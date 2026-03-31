#!/usr/bin/env python3
"""Validate README files for required sections and formatting.

Thin wrapper — delegates to hephaestus.validation.markdown.check_readmes_main().
Install homericintelligence-hephaestus>=0.6.0 to use this script.

Note: hephaestus.validation.markdown exposes find_readmes, extract_sections,
check_markdown_formatting, and related helpers. check_readmes_main() and
validate_readme() will be available in hephaestus>=0.6.0. Until then, a local
shim is provided below so that existing tests continue to work.
"""
import sys
from pathlib import Path
from typing import Any

# Import what hephaestus already provides
from hephaestus.validation.markdown import (  # noqa: F401
    check_markdown_formatting,
    extract_sections,
    find_readmes,
)

# hephaestus check_required_sections has a different signature:
#   (content: str, required_sections: list[str], file_path=None) -> tuple
# Scylla tests call it as check_required_sections(readme_path, sections).
# Provide a compatibility shim that accepts either calling convention.
from hephaestus.validation.markdown import (  # noqa: F401
    check_required_sections as _hephaestus_check_required_sections,
)

# Required sections for different README types (kept here for compatibility)
REQUIRED_SECTIONS: dict[str, list[str]] = {
    "default": ["Overview", "Installation", "Usage"],
    "directory": ["Overview", "Structure"],
    "evaluation": ["Overview", "Metrics", "Usage", "Examples"],
}


def check_required_sections(  # type: ignore[misc]
    readme_path: Path, sections: list[str]
) -> tuple[bool, list[str]]:
    """Check if README has required sections.

    Compatibility shim: Scylla tests pass (readme_path, sections) while
    hephaestus expects (content, required_sections). Delegates to hephaestus
    when given a Path in the first argument; falls through gracefully.
    """
    if isinstance(readme_path, Path) and readme_path.exists():
        content = readme_path.read_text(encoding="utf-8", errors="replace")
    elif isinstance(readme_path, str) and Path(readme_path).exists():
        content = Path(readme_path).read_text(encoding="utf-8", errors="replace")
    else:
        # First arg might already be content (hephaestus calling convention)
        content = str(readme_path)

    # Determine readme type from path
    readme_type = "default"
    if isinstance(readme_path, Path):
        parent_dir = readme_path.parent.name
        if parent_dir in ["docs", "agents", "experiments", "results", "tests", ".claude"]:
            readme_type = "directory"
        elif parent_dir in ["scylla", "scripts"]:
            readme_type = "evaluation"

    required = REQUIRED_SECTIONS.get(readme_type, REQUIRED_SECTIONS["default"])
    missing = [s for s in required if not any(s.lower() in e.lower() for e in sections)]
    return len(missing) == 0, missing


def validate_readme(readme_path: Path, verbose: bool = False) -> dict[str, Any]:
    """Validate a single README file."""
    result: dict[str, Any] = {
        "path": str(readme_path),
        "passed": True,
        "issues": [],
    }

    try:
        content = readme_path.read_text()
        sections = extract_sections(content)
        sections_ok, missing = check_required_sections(readme_path, sections)
        if not sections_ok:
            result["passed"] = False
            result["issues"].append(f"Missing sections: {', '.join(missing)}")

        formatting_issues = check_markdown_formatting(content)
        if formatting_issues:
            result["passed"] = False
            result["issues"].extend(formatting_issues)

        if not content.endswith("\n"):
            result["passed"] = False
            result["issues"].append("File must end with newline")

    except Exception as e:
        result["passed"] = False
        result["issues"].append(f"Error reading file: {e!s}")

    return result


def check_readmes_main() -> int:
    """Run the README validation script."""
    verbose = "--verbose" in sys.argv or "-v" in sys.argv

    directory = None
    for i, arg in enumerate(sys.argv):
        if arg in ["--directory", "-d"] and i + 1 < len(sys.argv):
            directory = Path(sys.argv[i + 1])
            break

    if directory is None:
        try:
            from hephaestus.utils.helpers import get_repo_root
            directory = get_repo_root()
        except Exception:
            directory = Path.cwd()

    print(f"Validating READMEs in: {directory}\n")
    readmes = find_readmes(directory)

    if not readmes:
        print(f"No README.md files found in {directory}")
        return 0

    print(f"Found {len(readmes)} README files\n")

    passed: list[str] = []
    failed: list[dict[str, Any]] = []

    for readme_path in readmes:
        relative_path = readme_path.relative_to(directory)
        result = validate_readme(readme_path, verbose)
        if result["passed"]:
            passed.append(str(relative_path))
            if verbose:
                print(f"  {relative_path}")
        else:
            failed.append(result)
            print(f"  {relative_path}")
            for issue in result["issues"]:
                print(f"    - {issue}")

    total = len(passed) + len(failed)
    print(f"\nTotal READMEs: {total}")
    print(f"Passed: {len(passed)}")
    print(f"Failed: {len(failed)}")

    return 0 if not failed else 1


# Alias for backwards compatibility
main = check_readmes_main

if __name__ == "__main__":
    sys.exit(check_readmes_main())
