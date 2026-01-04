#!/usr/bin/env python3
"""Extract CLAUDE.md blocks from ProjectOdyssey.

This script reads the CLAUDE.md file and extracts it into 18 separate block files
for use in tier testing.
"""

import sys
from pathlib import Path

# Block definitions: (block_id, start_line, end_line, filename)
BLOCKS = [
    ("B01", 1, 11, "B01-project-overview.md"),
    ("B02", 13, 67, "B02-critical-rules.md"),
    ("B03", 69, 85, "B03-quick-links.md"),
    ("B04", 87, 109, "B04-agent-hierarchy-intro.md"),
    ("B05", 110, 178, "B05-skill-delegation.md"),
    ("B06", 181, 209, "B06-dev-principles.md"),
    ("B07", 211, 258, "B07-language-preference.md"),
    ("B08", 260, 326, "B08-extended-thinking.md"),
    ("B09", 327, 395, "B09-skills-vs-subagents.md"),
    ("B10", 397, 462, "B10-hooks-best-practices.md"),
    ("B11", 464, 611, "B11-output-style.md"),
    ("B12", 612, 714, "B12-tool-use-optimization.md"),
    ("B13", 716, 831, "B13-agentic-loops.md"),
    ("B14", 833, 880, "B14-delegation-mojo.md"),
    ("B15", 882, 1099, "B15-common-commands.md"),
    ("B16", 1101, 1234, "B16-repo-architecture.md"),
    ("B17", 1236, 1347, "B17-testing-strategy.md"),
    ("B18", 1349, 1787, "B18-github-git-workflow.md"),
]


def extract_blocks(source_file: Path, output_dir: Path) -> None:
    """Extract all blocks from CLAUDE.md to separate files."""
    # Read the source file
    with open(source_file) as f:
        lines = f.readlines()

    print(f"Read {len(lines)} lines from {source_file}")

    # Extract each block
    for block_id, start, end, filename in BLOCKS:
        # Lines are 1-indexed in the plan, but 0-indexed in Python
        block_lines = lines[start - 1 : end]
        output_path = output_dir / filename

        with open(output_path, "w") as f:
            f.writelines(block_lines)

        print(f"  {block_id}: lines {start}-{end} ({len(block_lines)} lines) -> {filename}")

    print(f"\nExtracted {len(BLOCKS)} blocks to {output_dir}")


def main():
    """Extract CLAUDE.md blocks to separate files."""
    # Default paths
    source_file = Path("/home/mvillmow/ProjectOdysseyManual/CLAUDE.md")
    output_dir = Path("/tmp/ProjectScylla/tests/claude-code/shared/blocks")

    # Allow overrides from command line
    if len(sys.argv) > 1:
        source_file = Path(sys.argv[1])
    if len(sys.argv) > 2:
        output_dir = Path(sys.argv[2])

    # Validate paths
    if not source_file.exists():
        print(f"Error: Source file not found: {source_file}")
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    # Extract blocks
    extract_blocks(source_file, output_dir)


if __name__ == "__main__":
    main()
