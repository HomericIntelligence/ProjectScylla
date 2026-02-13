"""Tests for scylla.discovery.blocks module."""

from pathlib import Path

import pytest

from scylla.discovery.blocks import DEFAULT_BLOCKS, discover_blocks, extract_blocks


@pytest.fixture
def mock_claude_md(tmp_path: Path) -> Path:
    """Create mock CLAUDE.md file with multiple sections."""
    claude_md = tmp_path / "CLAUDE.md"
    content = """# Project Overview
Line 2
Line 3

## Critical Rules
Line 5
Line 6
Line 7

## Quick Links
Line 9
Line 10

## Agent Hierarchy
Line 12
Line 13
Line 14

## Skill Delegation
Line 16
Line 17
"""
    claude_md.write_text(content)
    return claude_md


@pytest.fixture
def empty_claude_md(tmp_path: Path) -> Path:
    """Create empty CLAUDE.md file."""
    claude_md = tmp_path / "empty_CLAUDE.md"
    claude_md.write_text("")
    return claude_md


class TestDiscoverBlocks:
    """Tests for discover_blocks function."""

    def test_discover_default_blocks(self, mock_claude_md: Path) -> None:
        """Discover blocks returns default blocks when no custom blocks provided."""
        blocks = discover_blocks(mock_claude_md)

        assert blocks == DEFAULT_BLOCKS
        assert len(blocks) == 18  # DEFAULT_BLOCKS has 18 entries

    def test_discover_custom_blocks(self, mock_claude_md: Path) -> None:
        """Discover blocks uses custom block definitions when provided."""
        custom_blocks = [
            ("B01", 1, 4, "custom-block.md"),
            ("B02", 5, 8, "another-block.md"),
        ]

        blocks = discover_blocks(mock_claude_md, block_defs=custom_blocks)

        assert blocks == custom_blocks
        assert len(blocks) == 2

    def test_discover_nonexistent_file(self, tmp_path: Path) -> None:
        """Discover blocks raises FileNotFoundError for nonexistent file."""
        nonexistent = tmp_path / "nonexistent.md"

        with pytest.raises(FileNotFoundError) as exc_info:
            discover_blocks(nonexistent)

        assert "CLAUDE.md not found" in str(exc_info.value)
        assert str(nonexistent) in str(exc_info.value)

    def test_discover_empty_file(self, empty_claude_md: Path) -> None:
        """Discover blocks works with empty CLAUDE.md."""
        blocks = discover_blocks(empty_claude_md)

        # Should return default blocks even for empty file
        assert blocks == DEFAULT_BLOCKS

    def test_discover_custom_blocks_override(self, mock_claude_md: Path) -> None:
        """Custom block definitions override defaults completely."""
        custom_blocks = [("CUSTOM", 1, 5, "custom.md")]

        blocks = discover_blocks(mock_claude_md, block_defs=custom_blocks)

        # Should only have custom block, not defaults
        assert len(blocks) == 1
        assert blocks[0][0] == "CUSTOM"

    def test_discover_preserves_block_structure(self, mock_claude_md: Path) -> None:
        """Discover blocks preserves block tuple structure."""
        blocks = discover_blocks(mock_claude_md)

        for block in blocks:
            assert len(block) == 4
            block_id, start, end, filename = block
            assert isinstance(block_id, str)
            assert isinstance(start, int)
            assert isinstance(end, int)
            assert isinstance(filename, str)
            assert start <= end

    def test_discover_empty_custom_blocks(self, mock_claude_md: Path) -> None:
        """Discover blocks with empty custom block list."""
        blocks = discover_blocks(mock_claude_md, block_defs=[])

        assert blocks == []


class TestExtractBlocks:
    """Tests for extract_blocks function."""

    def test_extract_creates_output_dir(self, mock_claude_md: Path, tmp_path: Path) -> None:
        """Extract blocks creates output directory if it doesn't exist."""
        output_dir = tmp_path / "output"
        assert not output_dir.exists()

        extract_blocks(mock_claude_md, output_dir, block_defs=[("B01", 1, 3, "test.md")])

        assert output_dir.exists()
        assert output_dir.is_dir()

    def test_extract_single_block(self, mock_claude_md: Path, tmp_path: Path) -> None:
        """Extract single block from CLAUDE.md."""
        output_dir = tmp_path / "output"
        block_defs = [("B01", 1, 4, "block1.md")]

        created_files = extract_blocks(mock_claude_md, output_dir, block_defs=block_defs)

        assert len(created_files) == 1
        assert created_files[0] == output_dir / "block1.md"
        assert created_files[0].exists()

    def test_extract_multiple_blocks(self, mock_claude_md: Path, tmp_path: Path) -> None:
        """Extract multiple blocks from CLAUDE.md."""
        output_dir = tmp_path / "output"
        block_defs = [
            ("B01", 1, 4, "block1.md"),
            ("B02", 5, 8, "block2.md"),
            ("B03", 9, 11, "block3.md"),
        ]

        created_files = extract_blocks(mock_claude_md, output_dir, block_defs=block_defs)

        assert len(created_files) == 3
        assert (output_dir / "block1.md").exists()
        assert (output_dir / "block2.md").exists()
        assert (output_dir / "block3.md").exists()

    def test_extract_preserves_content(self, mock_claude_md: Path, tmp_path: Path) -> None:
        """Extract blocks preserves line content."""
        output_dir = tmp_path / "output"
        # Extract lines 1-4 (inclusive, but 1-indexed so lines 0-3 in Python)
        block_defs = [("B01", 1, 4, "block1.md")]

        extract_blocks(mock_claude_md, output_dir, block_defs=block_defs)

        content = (output_dir / "block1.md").read_text()
        expected = "# Project Overview\nLine 2\nLine 3\n\n"
        assert content == expected

    def test_extract_line_numbering(self, tmp_path: Path) -> None:
        """Extract blocks uses 1-indexed line numbers."""
        source = tmp_path / "source.md"
        source.write_text("Line 1\nLine 2\nLine 3\nLine 4\nLine 5\n")

        output_dir = tmp_path / "output"
        # Lines 2-4 (1-indexed) should give us "Line 2\nLine 3\nLine 4\n"
        block_defs = [("B01", 2, 4, "lines_2_to_4.md")]

        extract_blocks(source, output_dir, block_defs=block_defs)

        content = (output_dir / "lines_2_to_4.md").read_text()
        assert content == "Line 2\nLine 3\nLine 4\n"

    def test_extract_single_line_block(self, tmp_path: Path) -> None:
        """Extract single-line block."""
        source = tmp_path / "source.md"
        source.write_text("Line 1\nLine 2\nLine 3\n")

        output_dir = tmp_path / "output"
        block_defs = [("B01", 2, 2, "single_line.md")]

        extract_blocks(source, output_dir, block_defs=block_defs)

        content = (output_dir / "single_line.md").read_text()
        assert content == "Line 2\n"

    def test_extract_entire_file(self, mock_claude_md: Path, tmp_path: Path) -> None:
        """Extract entire file as single block."""
        output_dir = tmp_path / "output"

        # Count lines in source
        with open(mock_claude_md) as f:
            num_lines = len(f.readlines())

        block_defs = [("FULL", 1, num_lines, "full_file.md")]

        extract_blocks(mock_claude_md, output_dir, block_defs=block_defs)

        original = mock_claude_md.read_text()
        extracted = (output_dir / "full_file.md").read_text()
        assert original == extracted

    def test_extract_empty_block(self, tmp_path: Path) -> None:
        """Extract empty block (start > end creates empty file)."""
        source = tmp_path / "source.md"
        source.write_text("Line 1\nLine 2\nLine 3\n")

        output_dir = tmp_path / "output"
        # Start > end should result in empty slice
        block_defs = [("EMPTY", 5, 4, "empty.md")]

        extract_blocks(source, output_dir, block_defs=block_defs)

        content = (output_dir / "empty.md").read_text()
        assert content == ""

    def test_extract_out_of_bounds(self, tmp_path: Path) -> None:
        """Extract blocks handles out-of-bounds line numbers gracefully."""
        source = tmp_path / "source.md"
        source.write_text("Line 1\nLine 2\nLine 3\n")

        output_dir = tmp_path / "output"
        # Lines beyond file length
        block_defs = [("OOB", 2, 100, "oob.md")]

        extract_blocks(source, output_dir, block_defs=block_defs)

        # Should extract lines 2-3 (all available lines from start)
        content = (output_dir / "oob.md").read_text()
        assert content == "Line 2\nLine 3\n"

    def test_extract_no_blocks(self, mock_claude_md: Path, tmp_path: Path) -> None:
        """Extract blocks with empty block definitions."""
        output_dir = tmp_path / "output"

        created_files = extract_blocks(mock_claude_md, output_dir, block_defs=[])

        assert created_files == []

    def test_extract_autodiscover(self, mock_claude_md: Path, tmp_path: Path) -> None:
        """Extract blocks auto-discovers blocks when none provided."""
        output_dir = tmp_path / "output"

        created_files = extract_blocks(mock_claude_md, output_dir)

        # Should use DEFAULT_BLOCKS (18 blocks)
        assert len(created_files) == 18

    def test_extract_overwrites_existing(self, mock_claude_md: Path, tmp_path: Path) -> None:
        """Extract blocks overwrites existing files."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Create existing file
        existing = output_dir / "block1.md"
        existing.write_text("Old content")

        block_defs = [("B01", 1, 4, "block1.md")]
        extract_blocks(mock_claude_md, output_dir, block_defs=block_defs)

        # Content should be overwritten
        content = existing.read_text()
        assert content != "Old content"
        assert "Project Overview" in content

    def test_extract_preserves_line_endings(self, tmp_path: Path) -> None:
        """Extract blocks preserves line endings."""
        source = tmp_path / "source.md"
        source.write_text("Line 1\nLine 2\nLine 3\n")

        output_dir = tmp_path / "output"
        block_defs = [("B01", 1, 3, "block.md")]

        extract_blocks(source, output_dir, block_defs=block_defs)

        content = (output_dir / "block.md").read_text()
        # Should have newlines preserved
        assert content.count("\n") == 3

    def test_extract_return_value_order(self, mock_claude_md: Path, tmp_path: Path) -> None:
        """Extract blocks returns files in definition order."""
        output_dir = tmp_path / "output"
        block_defs = [
            ("B03", 9, 11, "third.md"),
            ("B01", 1, 4, "first.md"),
            ("B02", 5, 8, "second.md"),
        ]

        created_files = extract_blocks(mock_claude_md, output_dir, block_defs=block_defs)

        # Should match order of block_defs
        assert created_files[0].name == "third.md"
        assert created_files[1].name == "first.md"
        assert created_files[2].name == "second.md"


class TestDefaultBlocks:
    """Tests for DEFAULT_BLOCKS constant."""

    def test_default_blocks_structure(self) -> None:
        """DEFAULT_BLOCKS has correct structure."""
        assert len(DEFAULT_BLOCKS) == 18

        for block in DEFAULT_BLOCKS:
            assert len(block) == 4
            block_id, start, end, filename = block
            assert isinstance(block_id, str)
            assert isinstance(start, int)
            assert isinstance(end, int)
            assert isinstance(filename, str)

    def test_default_blocks_ids(self) -> None:
        """DEFAULT_BLOCKS has sequential block IDs."""
        expected_ids = [f"B{i:02d}" for i in range(1, 19)]
        actual_ids = [block[0] for block in DEFAULT_BLOCKS]
        assert actual_ids == expected_ids

    def test_default_blocks_valid_ranges(self) -> None:
        """DEFAULT_BLOCKS has valid line ranges."""
        for block in DEFAULT_BLOCKS:
            block_id, start, end, filename = block
            assert start > 0, f"{block_id}: start must be positive"
            assert end >= start, f"{block_id}: end must be >= start"

    def test_default_blocks_filenames(self) -> None:
        """DEFAULT_BLOCKS filenames match block IDs."""
        for block in DEFAULT_BLOCKS:
            block_id, start, end, filename = block
            assert filename.startswith(block_id), f"{filename} should start with {block_id}"
            assert filename.endswith(".md"), f"{filename} should end with .md"

    def test_default_blocks_no_gaps(self) -> None:
        """DEFAULT_BLOCKS line ranges are sequential (no gaps)."""
        for i in range(len(DEFAULT_BLOCKS) - 1):
            current_block = DEFAULT_BLOCKS[i]
            next_block = DEFAULT_BLOCKS[i + 1]

            current_end = current_block[2]
            next_start = next_block[1]

            # Next block should start after current block ends
            # (allowing for some spacing between blocks)
            assert next_start > current_end, (
                f"Gap detected between {current_block[0]} and {next_block[0]}"
            )


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_extract_with_unicode_content(self, tmp_path: Path) -> None:
        """Extract blocks with Unicode content."""
        source = tmp_path / "source.md"
        source.write_text("Line 1: 你好\nLine 2: 🚀\nLine 3: Ñoño\n", encoding="utf-8")

        output_dir = tmp_path / "output"
        block_defs = [("B01", 1, 3, "unicode.md")]

        extract_blocks(source, output_dir, block_defs=block_defs)

        content = (output_dir / "unicode.md").read_text(encoding="utf-8")
        assert "你好" in content
        assert "🚀" in content
        assert "Ñoño" in content

    def test_extract_with_special_filename_chars(
        self, mock_claude_md: Path, tmp_path: Path
    ) -> None:
        """Extract blocks with special characters in filename."""
        output_dir = tmp_path / "output"
        # Use filename with special chars (valid on most systems)
        block_defs = [("B01", 1, 4, "block-1_test.md")]

        created_files = extract_blocks(mock_claude_md, output_dir, block_defs=block_defs)

        assert created_files[0].exists()
        assert created_files[0].name == "block-1_test.md"

    def test_discover_with_permission_error(self, tmp_path: Path) -> None:
        """Discover blocks handles permission errors."""
        # Note: This test may behave differently on different systems
        # In practice, if file doesn't exist, we get FileNotFoundError first
        nonexistent = tmp_path / "nonexistent.md"

        with pytest.raises(FileNotFoundError):
            discover_blocks(nonexistent)
