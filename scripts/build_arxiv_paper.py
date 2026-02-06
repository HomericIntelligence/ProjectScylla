#!/usr/bin/env python3
"""Transform docs/paper.tex to arXiv-ready main.tex.

This script reads the manually-edited paper.tex source and applies fixups
to generate the final arXiv submission main.tex:
- Fix inline figure references (convert texttt paths to ref labels)
- Remove duplicate table includes
- Add arXiv preamble adjustments (pdfoutput directive)
- Ensure all paths are relative

Python Justification: Text transformation with regex pattern matching.
"""

import re
from pathlib import Path


def fix_inline_figure_refs(content: str) -> str:
    r"""Fix inline figure references in main body.

    Pattern: Figure N (see \texttt{docs/paper-dryrun/figures/figNN_...})
    Replace: Figure~\ref{fig:figNN}
    """
    # Match: Figure <number> (see \texttt{...figNN_...})
    pattern = r"Figure\s+(\d+)\s+\(see\s+\\texttt\{[^}]*?(fig\d+)_[^}]+\}\)"
    replacement = r"Figure~\\ref{fig:\2}"
    content = re.sub(pattern, replacement, content)

    # Also handle cases without \texttt (just plain paths)
    pattern2 = r"Figure\s+(\d+)\s+\(see\s+docs/paper-dryrun/figures/(fig\d+)_[^)]+\)"
    replacement2 = r"Figure~\\ref{fig:\2}"
    content = re.sub(pattern2, replacement2, content)

    return content


def fix_duplicate_table_includes(content: str) -> str:
    """Remove duplicate table includes at lines ~218 and ~283.

    These are erroneous duplicate inclusions of tab04_criteria_performance.tex
    that should be removed, keeping only the intentional one.
    """
    # Count occurrences of the problematic table include
    pattern = r"\\input\{tables/tab04_criteria_performance\.tex\}"
    matches = list(re.finditer(pattern, content))

    if len(matches) <= 1:
        # No duplicates, nothing to fix
        return content

    # Strategy: Keep the first occurrence, remove all others
    # This is safest since we don't know which is "intentional"
    lines = content.split("\n")
    fixed_lines = []
    seen_count = 0

    for line in lines:
        if re.search(pattern, line):
            seen_count += 1
            if seen_count == 1:
                # Keep the first occurrence
                fixed_lines.append(line)
            # else: skip duplicate occurrences
        else:
            fixed_lines.append(line)

    if seen_count > 1:
        print(f"  Fixed {seen_count - 1} duplicate table include(s)")

    return "\n".join(fixed_lines)


def add_arxiv_preamble(content: str) -> str:
    r"""Add \pdfoutput=1 after \documentclass for arXiv compliance.

    arXiv requires this directive for proper PDF processing.
    """
    # Find \documentclass line
    pattern = r"(\\documentclass(?:\[[^\]]*\])?\{[^}]+\})"
    replacement = r"\1\n\\pdfoutput=1  % Required by arXiv"

    # Only add if not already present
    if "\\pdfoutput" not in content:
        content = re.sub(pattern, replacement, content)
        print("  Added \\pdfoutput=1 directive")

    return content


def fix_relative_paths(content: str) -> str:
    """Ensure all paths are relative (no absolute or docs/paper-dryrun/ paths).

    - figures/ paths should stay as-is
    - tables/ paths should stay as-is
    - Remove any docs/paper-dryrun/ prefixes
    """
    # Fix absolute or docs/paper-dryrun/ prefixes and bare paper-dryrun/ prefixes
    content = re.sub(r"docs/paper-dryrun/figures/", "figures/", content)
    content = re.sub(r"docs/paper-dryrun/tables/", "tables/", content)
    content = re.sub(r"paper-dryrun/figures/", "figures/", content)
    content = re.sub(r"paper-dryrun/tables/", "tables/", content)

    # Remove any absolute paths (starting with /)
    # This is more cautious - only fix paths in \includegraphics and \input
    content = re.sub(
        r"\\includegraphics(?:\[[^\]]*\])?\{/[^}]+/figures/([^}]+)\}",
        r"\\includegraphics{figures/\1}",
        content,
    )
    content = re.sub(
        r"\\input\{/[^}]+/tables/([^}]+)\}",
        r"\\input{tables/\1}",
        content,
    )

    return content


def transform_paper_to_main(paper_path: Path, output_path: Path) -> None:
    """Transform paper.tex to main.tex with arXiv fixups.

    Args:
        paper_path: Path to docs/paper.tex (source of truth)
        output_path: Path to docs/paper-dryrun-arxiv/main.tex (output)

    """
    print(f"Transforming {paper_path} → {output_path}")

    # Read source
    if not paper_path.exists():
        print(f"✗ Error: {paper_path} not found")
        exit(1)

    content = paper_path.read_text()
    print(f"  Read {len(content)} characters from {paper_path}")

    # Apply transformations
    print("  Applying transformations:")
    content = fix_inline_figure_refs(content)
    content = fix_duplicate_table_includes(content)
    content = add_arxiv_preamble(content)
    content = fix_relative_paths(content)

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content)

    print(f"✓ Generated main.tex: {output_path}")
    print(f"  - Output size: {len(content)} characters")

    # Count sections for verification
    section_count = len(re.findall(r"^\\section", content, re.MULTILINE))
    subsection_count = len(re.findall(r"^\\subsection", content, re.MULTILINE))
    figure_count = len(re.findall(r"\\begin\{figure\}", content))
    table_count = len(re.findall(r"\\input\{tables/", content))

    print(f"  - {section_count} sections, {subsection_count} subsections")
    print(f"  - {figure_count} figures, {table_count} table includes")


if __name__ == "__main__":
    paper_path = Path("docs/paper.tex")
    output_path = Path("docs/paper-dryrun-arxiv/main.tex")

    transform_paper_to_main(paper_path, output_path)
    print("✓ Transformation complete")
