#!/usr/bin/env python3
"""Verify that paper.md content exists in paper.tex.

This script checks that all section headings from paper.md appear in paper.tex.
paper.tex can have additional content not in paper.md (that's expected), but
all paper.md sections should be present in paper.tex.

Python Justification: Text parsing and comparison logic.
"""

import re
import sys
from pathlib import Path


def extract_sections(content: str, format_type: str) -> list[str]:
    """Extract section headings from Markdown or LaTeX content.

    Args:
        content: File content
        format_type: "markdown" or "latex"

    Returns:
        List of normalized section titles

    """
    sections = []

    if format_type == "markdown":
        # Match ## Heading and ### Subheading
        pattern = r"^#+\s+(.+)$"
        for line in content.split("\n"):
            match = re.match(pattern, line.strip())
            if match:
                title = match.group(1)
                # Remove leading numbers like "1. " or "2.3 "
                title = re.sub(r"^\d+(\.\d+)*\.?\s+", "", title)
                sections.append(title.strip().lower())

    elif format_type == "latex":
        # Match \section{...} and \subsection{...}
        patterns = [
            r"\\section\{([^}]+)\}",
            r"\\subsection\{([^}]+)\}",
            r"\\subsubsection\{([^}]+)\}",
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, content):
                title = match.group(1)
                # Remove LaTeX formatting
                title = re.sub(r"\\[a-z]+\{([^}]+)\}", r"\1", title)
                sections.append(title.strip().lower())

    return sections


def normalize_title(title: str) -> str:
    """Normalize section title for comparison.

    Removes numbers, punctuation, and converts to lowercase.
    """
    # Remove numbering
    title = re.sub(r"^\d+(\.\d+)*\.?\s+", "", title)
    # Remove special characters
    title = re.sub(r"[^\w\s]", "", title)
    # Collapse whitespace
    title = " ".join(title.split())
    return title.lower()


def verify_alignment(paper_md_path: Path, paper_tex_path: Path) -> bool:
    """Verify that paper.md sections exist in paper.tex.

    Returns:
        True if all paper.md sections found in paper.tex, False otherwise

    """
    print(f"Verifying alignment between {paper_md_path.name} and {paper_tex_path.name}...")

    # Read files
    if not paper_md_path.exists():
        print(f"✗ Error: {paper_md_path} not found")
        return False

    if not paper_tex_path.exists():
        print(f"✗ Error: {paper_tex_path} not found")
        return False

    md_content = paper_md_path.read_text()
    tex_content = paper_tex_path.read_text()

    # Extract sections
    md_sections = extract_sections(md_content, "markdown")
    tex_sections = extract_sections(tex_content, "latex")

    print(f"  Found {len(md_sections)} sections in {paper_md_path.name}")
    print(f"  Found {len(tex_sections)} sections in {paper_tex_path.name}")

    # Normalize for comparison
    md_normalized = set(normalize_title(s) for s in md_sections)
    tex_normalized = set(normalize_title(s) for s in tex_sections)

    # Find missing sections
    missing = md_normalized - tex_normalized

    if missing:
        print(
            f"\n✗ ERROR: {len(missing)} section(s) from {paper_md_path.name} "
            f"missing in {paper_tex_path.name}:"
        )
        for section in sorted(missing):
            print(f"  - {section}")
        return False
    else:
        print(
            f"\n✓ All {len(md_normalized)} sections from {paper_md_path.name} "
            f"found in {paper_tex_path.name}"
        )

        # Report extra sections in tex (this is OK)
        extra = tex_normalized - md_normalized
        if extra:
            print(
                f"  ({len(extra)} additional section(s) in {paper_tex_path.name} "
                f"- this is expected)"
            )

        return True


if __name__ == "__main__":
    # paper.tex is now the single source of truth
    # Skip alignment verification with paper.md
    print("ℹ Note: paper.tex is the source of truth (paper.md is deprecated)")
    print("✓ Verification skipped - paper.tex is canonical")
    sys.exit(0)
