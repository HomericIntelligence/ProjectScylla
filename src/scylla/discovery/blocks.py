"""CLAUDE.md block discovery and extraction.

Extracted from scripts/extract_blocks.py to provide reusable discovery logic
for the dynamic benchmark generator.
"""

from pathlib import Path

# Default block definitions for ProjectOdyssey CLAUDE.md
# Format: (block_id, start_line, end_line, filename)
DEFAULT_BLOCKS = [
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


def discover_blocks(
    claude_md_path: Path, block_defs: list[tuple[str, int, int, str]] | None = None
) -> list[tuple[str, int, int, str]]:
    """Analyze CLAUDE.md structure and return block definitions.

    Currently returns hardcoded block definitions. Future versions will
    implement heuristic section detection.

    Args:
        claude_md_path: Path to CLAUDE.md file
        block_defs: Optional explicit block definitions. If None, uses DEFAULT_BLOCKS.

    Returns:
        List of (block_id, start_line, end_line, filename) tuples

    Example:
        >>> blocks = discover_blocks(Path("CLAUDE.md"))
        >>> blocks[0]
        ('B01', 1, 11, 'B01-project-overview.md')

    """
    if block_defs is not None:
        return block_defs

    # Validate file exists
    if not claude_md_path.exists():
        raise FileNotFoundError(f"CLAUDE.md not found: {claude_md_path}")

    # Note: Section detection uses explicit markers only.
    # Heuristic detection would be unreliable due to variable markdown formatting.
    return DEFAULT_BLOCKS


def extract_blocks(
    source_file: Path,
    output_dir: Path,
    block_defs: list[tuple[str, int, int, str]] | None = None,
) -> list[Path]:
    """Extract CLAUDE.md blocks to separate files.

    Args:
        source_file: Path to source CLAUDE.md file
        output_dir: Directory to write block files
        block_defs: Optional block definitions. If None, auto-discovers.

    Returns:
        List of created block file paths

    Example:
        >>> extract_blocks(
        ...     Path("CLAUDE.md"),
        ...     Path("tests/shared/blocks")
        ... )
        [Path("tests/shared/blocks/B01-project-overview.md"), ...]

    """
    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Get block definitions
    if block_defs is None:
        block_defs = discover_blocks(source_file)

    # Read source file
    with open(source_file) as f:
        lines = f.readlines()

    # Extract each block
    created_files = []
    for _block_id, start, end, filename in block_defs:
        # Lines are 1-indexed in definitions, but 0-indexed in Python
        block_lines = lines[start - 1 : end]
        output_path = output_dir / filename

        with open(output_path, "w") as f:
            f.writelines(block_lines)

        created_files.append(output_path)

    return created_files
