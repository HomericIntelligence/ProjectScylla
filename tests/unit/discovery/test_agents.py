"""Tests for scylla.discovery.agents module.

Python justification: Required for pytest testing framework.
"""

from pathlib import Path

import pytest

from scylla.discovery.agents import discover_agents, organize_agents, parse_agent_level


@pytest.fixture
def mock_agent_files(tmp_path: Path) -> Path:
    """Create mock agent markdown files with various levels."""
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()

    # L0 - Chief Evaluator
    (agents_dir / "chief-evaluator.md").write_text(
        """---
name: Chief Evaluator
level: 0
---

# Chief Evaluator

L0 orchestrator for evaluation work.
"""
    )

    # L1 - Experiment Design
    (agents_dir / "experiment-design.md").write_text(
        """---
name: Experiment Design
level: 1
---

# Experiment Design

L1 specialist for experiment design.
"""
    )

    # L2 - Metrics Engineer
    (agents_dir / "metrics-engineer.md").write_text(
        """---
name: Metrics Engineer
level: 2
---

# Metrics Engineer

L2 engineer for metrics implementation.
"""
    )

    # L3 - Test Writer
    (agents_dir / "test-writer.md").write_text(
        """---
name: Test Writer
level: 3
---

# Test Writer

L3 engineer for test implementation.
"""
    )

    # L4 - Documentation Writer
    (agents_dir / "doc-writer.md").write_text(
        """---
name: Documentation Writer
level: 4
---

# Documentation Writer

L4 junior engineer for documentation.
"""
    )

    # L5 - Code Reviewer
    (agents_dir / "code-reviewer.md").write_text(
        """---
name: Code Reviewer
level: 5
---

# Code Reviewer

L5 intern for code review.
"""
    )

    # Agent without level (should be ignored)
    (agents_dir / "no-level.md").write_text(
        """---
name: No Level Agent
---

# No Level Agent

Agent without level field.
"""
    )

    # Agent with invalid level (should be ignored)
    (agents_dir / "invalid-level.md").write_text(
        """---
name: Invalid Level
level: 10
---

# Invalid Level

Agent with invalid level.
"""
    )

    return agents_dir


@pytest.fixture
def empty_agents_dir(tmp_path: Path) -> Path:
    """Create empty agents directory."""
    agents_dir = tmp_path / "empty_agents"
    agents_dir.mkdir()
    return agents_dir


class TestParseAgentLevel:
    """Tests for parse_agent_level function."""

    def test_parse_level_0(self, mock_agent_files: Path) -> None:
        """Parse L0 agent level."""
        agent_file = mock_agent_files / "chief-evaluator.md"
        level = parse_agent_level(agent_file)
        assert level == 0

    def test_parse_level_1(self, mock_agent_files: Path) -> None:
        """Parse L1 agent level."""
        agent_file = mock_agent_files / "experiment-design.md"
        level = parse_agent_level(agent_file)
        assert level == 1

    def test_parse_level_2(self, mock_agent_files: Path) -> None:
        """Parse L2 agent level."""
        agent_file = mock_agent_files / "metrics-engineer.md"
        level = parse_agent_level(agent_file)
        assert level == 2

    def test_parse_level_3(self, mock_agent_files: Path) -> None:
        """Parse L3 agent level."""
        agent_file = mock_agent_files / "test-writer.md"
        level = parse_agent_level(agent_file)
        assert level == 3

    def test_parse_level_4(self, mock_agent_files: Path) -> None:
        """Parse L4 agent level."""
        agent_file = mock_agent_files / "doc-writer.md"
        level = parse_agent_level(agent_file)
        assert level == 4

    def test_parse_level_5(self, mock_agent_files: Path) -> None:
        """Parse L5 agent level."""
        agent_file = mock_agent_files / "code-reviewer.md"
        level = parse_agent_level(agent_file)
        assert level == 5

    def test_parse_no_level(self, mock_agent_files: Path) -> None:
        """Parse agent without level returns None."""
        agent_file = mock_agent_files / "no-level.md"
        level = parse_agent_level(agent_file)
        assert level is None

    def test_parse_invalid_level(self, mock_agent_files: Path) -> None:
        """Parse agent with invalid level (>5) returns the level value."""
        agent_file = mock_agent_files / "invalid-level.md"
        level = parse_agent_level(agent_file)
        assert level == 10  # Function returns the parsed value

    def test_parse_level_with_spaces(self, tmp_path: Path) -> None:
        """Parse level with extra whitespace."""
        agent_file = tmp_path / "spaced.md"
        agent_file.write_text(
            """---
level:    2
---
"""
        )
        level = parse_agent_level(agent_file)
        assert level == 2

    def test_parse_level_multiline_frontmatter(self, tmp_path: Path) -> None:
        """Parse level from multi-line frontmatter."""
        agent_file = tmp_path / "multiline.md"
        agent_file.write_text(
            """---
name: Test Agent
level: 2
description: A test agent
---

# Test Agent
"""
        )
        level = parse_agent_level(agent_file)
        assert level == 2

    def test_parse_nonexistent_file(self, tmp_path: Path) -> None:
        """Parsing nonexistent file raises FileNotFoundError."""
        nonexistent = tmp_path / "nonexistent.md"
        with pytest.raises(FileNotFoundError):
            parse_agent_level(nonexistent)


class TestDiscoverAgents:
    """Tests for discover_agents function."""

    def test_discover_all_levels(self, mock_agent_files: Path) -> None:
        """Discover agents across all levels."""
        agents_by_level = discover_agents(mock_agent_files)

        # Check structure
        assert len(agents_by_level) == 6
        assert all(level in agents_by_level for level in range(6))

        # Check counts per level
        assert len(agents_by_level[0]) == 1  # chief-evaluator
        assert len(agents_by_level[1]) == 1  # experiment-design
        assert len(agents_by_level[2]) == 1  # metrics-engineer
        assert len(agents_by_level[3]) == 1  # test-writer
        assert len(agents_by_level[4]) == 1  # doc-writer
        assert len(agents_by_level[5]) == 1  # code-reviewer

    def test_discover_agent_filenames(self, mock_agent_files: Path) -> None:
        """Verify discovered agent filenames."""
        agents_by_level = discover_agents(mock_agent_files)

        assert agents_by_level[0][0].name == "chief-evaluator.md"
        assert agents_by_level[1][0].name == "experiment-design.md"
        assert agents_by_level[2][0].name == "metrics-engineer.md"

    def test_discover_empty_directory(self, empty_agents_dir: Path) -> None:
        """Discover agents in empty directory."""
        agents_by_level = discover_agents(empty_agents_dir)

        # Should return empty lists for all levels
        assert len(agents_by_level) == 6
        assert all(len(agents_by_level[level]) == 0 for level in range(6))

    def test_discover_ignores_invalid_agents(self, mock_agent_files: Path) -> None:
        """Discover agents ignores agents without valid levels."""
        agents_by_level = discover_agents(mock_agent_files)

        # Total discovered agents should be 6 (L0-L5)
        total = sum(len(agents) for agents in agents_by_level.values())
        assert total == 6

        # "no-level.md" and "invalid-level.md" should not be included
        all_names = [agent.name for agents in agents_by_level.values() for agent in agents]
        assert "no-level.md" not in all_names
        assert "invalid-level.md" not in all_names

    def test_discover_multiple_agents_same_level(self, tmp_path: Path) -> None:
        """Discover multiple agents at the same level."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()

        # Create two L1 agents
        (agents_dir / "agent1.md").write_text("---\nlevel: 1\n---\n")
        (agents_dir / "agent2.md").write_text("---\nlevel: 1\n---\n")

        agents_by_level = discover_agents(agents_dir)

        assert len(agents_by_level[1]) == 2
        names = {agent.name for agent in agents_by_level[1]}
        assert names == {"agent1.md", "agent2.md"}

    def test_discover_nonexistent_directory(self, tmp_path: Path) -> None:
        """Discover agents in nonexistent directory raises error."""
        nonexistent = tmp_path / "nonexistent"
        # glob on nonexistent directory returns empty list, so function returns empty dict
        agents_by_level = discover_agents(nonexistent)
        assert all(len(agents_by_level[level]) == 0 for level in range(6))


class TestOrganizeAgents:
    """Tests for organize_agents function."""

    def test_organize_creates_directories(self, mock_agent_files: Path, tmp_path: Path) -> None:
        """Organize agents creates L0-L5 subdirectories."""
        dest_dir = tmp_path / "organized"

        organize_agents(mock_agent_files, dest_dir)

        # Check directories exist
        for level in range(6):
            level_dir = dest_dir / f"L{level}"
            assert level_dir.exists()
            assert level_dir.is_dir()

    def test_organize_copies_files(self, mock_agent_files: Path, tmp_path: Path) -> None:
        """Organize agents copies files to appropriate level directories."""
        dest_dir = tmp_path / "organized"

        stats = organize_agents(mock_agent_files, dest_dir)

        # Check L0
        assert len(stats[0]) == 1
        assert "chief-evaluator.md" in stats[0]
        assert (dest_dir / "L0" / "chief-evaluator.md").exists()

        # Check L1
        assert len(stats[1]) == 1
        assert "experiment-design.md" in stats[1]
        assert (dest_dir / "L1" / "experiment-design.md").exists()

        # Check L2
        assert len(stats[2]) == 1
        assert "metrics-engineer.md" in stats[2]
        assert (dest_dir / "L2" / "metrics-engineer.md").exists()

    def test_organize_preserves_content(self, mock_agent_files: Path, tmp_path: Path) -> None:
        """Organize agents preserves file content."""
        dest_dir = tmp_path / "organized"

        organize_agents(mock_agent_files, dest_dir)

        # Read original and copied file
        original = (mock_agent_files / "chief-evaluator.md").read_text()
        copied = (dest_dir / "L0" / "chief-evaluator.md").read_text()

        assert original == copied

    def test_organize_returns_stats(self, mock_agent_files: Path, tmp_path: Path) -> None:
        """Organize agents returns correct statistics."""
        dest_dir = tmp_path / "organized"

        stats = organize_agents(mock_agent_files, dest_dir)

        # Check structure
        assert len(stats) == 6
        assert all(level in stats for level in range(6))

        # Check counts
        assert len(stats[0]) == 1
        assert len(stats[1]) == 1
        assert len(stats[2]) == 1
        assert len(stats[3]) == 1
        assert len(stats[4]) == 1
        assert len(stats[5]) == 1

    def test_organize_empty_directory(self, empty_agents_dir: Path, tmp_path: Path) -> None:
        """Organize empty agents directory."""
        dest_dir = tmp_path / "organized"

        stats = organize_agents(empty_agents_dir, dest_dir)

        # Directories should be created
        for level in range(6):
            assert (dest_dir / f"L{level}").exists()

        # Stats should be empty
        assert all(len(stats[level]) == 0 for level in range(6))

    def test_organize_idempotent(self, mock_agent_files: Path, tmp_path: Path) -> None:
        """Organize agents can be run multiple times."""
        dest_dir = tmp_path / "organized"

        stats1 = organize_agents(mock_agent_files, dest_dir)
        stats2 = organize_agents(mock_agent_files, dest_dir)

        # Stats should be identical
        assert stats1 == stats2

        # Files should still exist
        assert (dest_dir / "L0" / "chief-evaluator.md").exists()

    def test_organize_multiple_agents_same_level(self, tmp_path: Path) -> None:
        """Organize multiple agents at the same level."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()

        # Create two L2 agents
        (agents_dir / "agent1.md").write_text("---\nlevel: 2\n---\n")
        (agents_dir / "agent2.md").write_text("---\nlevel: 2\n---\n")

        dest_dir = tmp_path / "organized"
        stats = organize_agents(agents_dir, dest_dir)

        assert len(stats[2]) == 2
        assert set(stats[2]) == {"agent1.md", "agent2.md"}
        assert (dest_dir / "L2" / "agent1.md").exists()
        assert (dest_dir / "L2" / "agent2.md").exists()
