"""Unit tests for E2E subtest provider implementations."""

from __future__ import annotations

from pathlib import Path

import yaml

from scylla.e2e.models import TierID
from scylla.e2e.subtest_provider import (
    DEFAULT_SYSTEM_PROMPT_MODE,
    SUBTEST_ID_PREFIX_LENGTH,
    T0_FIRST_EXTENDING_SUBTEST,
    FileSystemSubtestProvider,
)


class TestConstants:
    """Tests for module constants."""

    def test_subtest_id_prefix_length(self) -> None:
        """Test that SUBTEST_ID_PREFIX_LENGTH matches expected format."""
        assert SUBTEST_ID_PREFIX_LENGTH == 2

    def test_default_system_prompt_mode(self) -> None:
        """Test that DEFAULT_SYSTEM_PROMPT_MODE is 'custom'."""
        assert DEFAULT_SYSTEM_PROMPT_MODE == "custom"

    def test_t0_first_extending_subtest(self) -> None:
        """Test that T0_FIRST_EXTENDING_SUBTEST is 2."""
        assert T0_FIRST_EXTENDING_SUBTEST == 2


class TestFileSystemSubtestProvider:
    """Tests for FileSystemSubtestProvider."""

    def test_init(self, tmp_path: Path) -> None:
        """Test provider initialization."""
        shared_dir = tmp_path / "shared"
        provider = FileSystemSubtestProvider(shared_dir)

        assert provider.shared_dir == shared_dir

    def test_discover_subtests_no_directory(self, tmp_path: Path) -> None:
        """Test discovery when subtests directory doesn't exist."""
        provider = FileSystemSubtestProvider(tmp_path / "shared")

        subtests = provider.discover_subtests(TierID.T0)

        assert subtests == []

    def test_discover_subtests_empty_directory(self, tmp_path: Path) -> None:
        """Test discovery with empty subtests directory."""
        shared_dir = tmp_path / "shared"
        subtests_dir = shared_dir / "subtests" / "t0"
        subtests_dir.mkdir(parents=True)

        provider = FileSystemSubtestProvider(shared_dir)
        subtests = provider.discover_subtests(TierID.T0)

        assert subtests == []

    def test_discover_subtests_basic(self, tmp_path: Path) -> None:
        """Test basic subtest discovery from YAML file."""
        shared_dir = tmp_path / "shared"
        subtests_dir = shared_dir / "subtests" / "t1"
        subtests_dir.mkdir(parents=True)

        # Create a basic YAML config
        config_file = subtests_dir / "00-basic.yaml"
        config_data = {
            "name": "Basic Test",
            "description": "A basic test configuration",
        }
        config_file.write_text(yaml.dump(config_data))

        provider = FileSystemSubtestProvider(shared_dir)
        subtests = provider.discover_subtests(TierID.T1)

        assert len(subtests) == 1
        assert subtests[0].id == "00"
        assert subtests[0].name == "Basic Test"
        assert subtests[0].description == "A basic test configuration"
        assert subtests[0].extends_previous is True  # T1 always extends
        assert subtests[0].resources == {}

    def test_discover_subtests_t0_no_extension(self, tmp_path: Path) -> None:
        """Test T0 subtests 00 and 01 don't extend previous."""
        shared_dir = tmp_path / "shared"
        subtests_dir = shared_dir / "subtests" / "t0"
        subtests_dir.mkdir(parents=True)

        # Create T0/00 and T0/01
        for idx in ["00", "01"]:
            config_file = subtests_dir / f"{idx}-test.yaml"
            config_data = {"name": f"Test {idx}"}
            config_file.write_text(yaml.dump(config_data))

        provider = FileSystemSubtestProvider(shared_dir)
        subtests = provider.discover_subtests(TierID.T0)

        assert len(subtests) == 2
        assert subtests[0].id == "00"
        assert subtests[0].extends_previous is False
        assert subtests[1].id == "01"
        assert subtests[1].extends_previous is False

    def test_discover_subtests_t0_with_extension(self, tmp_path: Path) -> None:
        """Test T0 subtests 02+ extend previous by default."""
        shared_dir = tmp_path / "shared"
        subtests_dir = shared_dir / "subtests" / "t0"
        subtests_dir.mkdir(parents=True)

        # Create T0/02 and T0/03
        for idx in ["02", "03"]:
            config_file = subtests_dir / f"{idx}-test.yaml"
            config_data = {"name": f"Test {idx}"}
            config_file.write_text(yaml.dump(config_data))

        provider = FileSystemSubtestProvider(shared_dir)
        subtests = provider.discover_subtests(TierID.T0)

        assert len(subtests) == 2
        assert subtests[0].id == "02"
        assert subtests[0].extends_previous is True
        assert subtests[1].id == "03"
        assert subtests[1].extends_previous is True

    def test_discover_subtests_extends_previous_override(self, tmp_path: Path) -> None:
        """Test that config can override extends_previous."""
        shared_dir = tmp_path / "shared"
        subtests_dir = shared_dir / "subtests" / "t0"
        subtests_dir.mkdir(parents=True)

        # Create T0/02 with explicit extends_previous: false
        config_file = subtests_dir / "02-no-extend.yaml"
        config_data = {"name": "No Extend", "extends_previous": False}
        config_file.write_text(yaml.dump(config_data))

        provider = FileSystemSubtestProvider(shared_dir)
        subtests = provider.discover_subtests(TierID.T0)

        assert len(subtests) == 1
        assert subtests[0].extends_previous is False

    def test_discover_subtests_with_resources(self, tmp_path: Path) -> None:
        """Test subtest discovery with resources field."""
        shared_dir = tmp_path / "shared"
        subtests_dir = shared_dir / "subtests" / "t1"
        subtests_dir.mkdir(parents=True)

        config_file = subtests_dir / "00-with-resources.yaml"
        config_data = {
            "name": "With Resources",
            "resources": {
                "skills": {"categories": ["agent", "github"]},
                "agents": {"levels": [0, 1]},
            },
        }
        config_file.write_text(yaml.dump(config_data))

        provider = FileSystemSubtestProvider(shared_dir)
        subtests = provider.discover_subtests(TierID.T1)

        assert len(subtests) == 1
        assert "skills" in subtests[0].resources
        assert "agents" in subtests[0].resources
        assert subtests[0].resources["skills"]["categories"] == ["agent", "github"]

    def test_discover_subtests_with_mcp_servers(self, tmp_path: Path) -> None:
        """Test that mcp_servers at root level are added to resources."""
        shared_dir = tmp_path / "shared"
        subtests_dir = shared_dir / "subtests" / "t2"
        subtests_dir.mkdir(parents=True)

        config_file = subtests_dir / "00-mcp.yaml"
        config_data = {
            "name": "MCP Test",
            "mcp_servers": ["server1", "server2"],
        }
        config_file.write_text(yaml.dump(config_data))

        provider = FileSystemSubtestProvider(shared_dir)
        subtests = provider.discover_subtests(TierID.T2)

        assert len(subtests) == 1
        assert "mcp_servers" in subtests[0].resources
        assert subtests[0].resources["mcp_servers"] == ["server1", "server2"]

    def test_discover_subtests_with_tools(self, tmp_path: Path) -> None:
        """Test that tools at root level are added to resources."""
        shared_dir = tmp_path / "shared"
        subtests_dir = shared_dir / "subtests" / "t2"
        subtests_dir.mkdir(parents=True)

        config_file = subtests_dir / "00-tools.yaml"
        config_data = {
            "name": "Tools Test",
            "tools": {"enabled": True, "list": ["tool1", "tool2"]},
        }
        config_file.write_text(yaml.dump(config_data))

        provider = FileSystemSubtestProvider(shared_dir)
        subtests = provider.discover_subtests(TierID.T2)

        assert len(subtests) == 1
        assert "tools" in subtests[0].resources
        assert subtests[0].resources["tools"]["enabled"] is True

    def test_discover_subtests_with_agents_root(self, tmp_path: Path) -> None:
        """Test that agents at root level are added to resources."""
        shared_dir = tmp_path / "shared"
        subtests_dir = shared_dir / "subtests" / "t3"
        subtests_dir.mkdir(parents=True)

        config_file = subtests_dir / "00-agents.yaml"
        config_data = {
            "name": "Agents Test",
            "agents": {"levels": [0, 1, 2]},
        }
        config_file.write_text(yaml.dump(config_data))

        provider = FileSystemSubtestProvider(shared_dir)
        subtests = provider.discover_subtests(TierID.T3)

        assert len(subtests) == 1
        assert "agents" in subtests[0].resources
        assert subtests[0].resources["agents"]["levels"] == [0, 1, 2]

    def test_discover_subtests_with_skills_root(self, tmp_path: Path) -> None:
        """Test that skills at root level are added to resources."""
        shared_dir = tmp_path / "shared"
        subtests_dir = shared_dir / "subtests" / "t1"
        subtests_dir.mkdir(parents=True)

        config_file = subtests_dir / "00-skills.yaml"
        config_data = {
            "name": "Skills Test",
            "skills": {"categories": ["testing", "analysis"]},
        }
        config_file.write_text(yaml.dump(config_data))

        provider = FileSystemSubtestProvider(shared_dir)
        subtests = provider.discover_subtests(TierID.T1)

        assert len(subtests) == 1
        assert "skills" in subtests[0].resources
        assert subtests[0].resources["skills"]["categories"] == ["testing", "analysis"]

    def test_discover_subtests_with_inherit_best_from(self, tmp_path: Path) -> None:
        """Test parsing inherit_best_from for T5 subtests."""
        shared_dir = tmp_path / "shared"
        subtests_dir = shared_dir / "subtests" / "t5"
        subtests_dir.mkdir(parents=True)

        config_file = subtests_dir / "01-best-prompts.yaml"
        config_data = {
            "name": "Best Prompts",
            "inherit_best_from": ["T0"],
        }
        config_file.write_text(yaml.dump(config_data))

        provider = FileSystemSubtestProvider(shared_dir)
        subtests = provider.discover_subtests(TierID.T5)

        assert len(subtests) == 1
        assert subtests[0].inherit_best_from == [TierID.T0]

    def test_discover_subtests_with_multiple_inherit_best_from(self, tmp_path: Path) -> None:
        """Test parsing multiple tiers in inherit_best_from."""
        shared_dir = tmp_path / "shared"
        subtests_dir = shared_dir / "subtests" / "t5"
        subtests_dir.mkdir(parents=True)

        config_file = subtests_dir / "05-combined.yaml"
        config_data = {
            "name": "Combined Best",
            "inherit_best_from": ["T0", "T1", "T2"],
        }
        config_file.write_text(yaml.dump(config_data))

        provider = FileSystemSubtestProvider(shared_dir)
        subtests = provider.discover_subtests(TierID.T5)

        assert len(subtests) == 1
        assert subtests[0].inherit_best_from == [TierID.T0, TierID.T1, TierID.T2]

    def test_discover_subtests_with_agent_teams(self, tmp_path: Path) -> None:
        """Test parsing agent_teams flag."""
        shared_dir = tmp_path / "shared"
        subtests_dir = shared_dir / "subtests" / "t4"
        subtests_dir.mkdir(parents=True)

        config_file = subtests_dir / "08-teams.yaml"
        config_data = {
            "name": "Agent Teams",
            "agent_teams": True,
        }
        config_file.write_text(yaml.dump(config_data))

        provider = FileSystemSubtestProvider(shared_dir)
        subtests = provider.discover_subtests(TierID.T4)

        assert len(subtests) == 1
        assert subtests[0].agent_teams is True

    def test_discover_subtests_skip_agent_teams(self, tmp_path: Path) -> None:
        """Test that skip_agent_teams filters out agent team subtests."""
        shared_dir = tmp_path / "shared"
        subtests_dir = shared_dir / "subtests" / "t4"
        subtests_dir.mkdir(parents=True)

        # Create two subtests: one with agent_teams, one without
        config_normal = subtests_dir / "01-normal.yaml"
        config_normal.write_text(yaml.dump({"name": "Normal"}))

        config_teams = subtests_dir / "08-teams.yaml"
        config_teams.write_text(yaml.dump({"name": "Teams", "agent_teams": True}))

        provider = FileSystemSubtestProvider(shared_dir)

        # Without skip_agent_teams
        all_subtests = provider.discover_subtests(TierID.T4, skip_agent_teams=False)
        assert len(all_subtests) == 2

        # With skip_agent_teams
        filtered_subtests = provider.discover_subtests(TierID.T4, skip_agent_teams=True)
        assert len(filtered_subtests) == 1
        assert filtered_subtests[0].name == "Normal"

    def test_discover_subtests_with_system_prompt_mode(self, tmp_path: Path) -> None:
        """Test parsing system_prompt_mode field."""
        shared_dir = tmp_path / "shared"
        subtests_dir = shared_dir / "subtests" / "t0"
        subtests_dir.mkdir(parents=True)

        config_file = subtests_dir / "00-empty.yaml"
        config_data = {
            "name": "Empty",
            "system_prompt_mode": "none",
        }
        config_file.write_text(yaml.dump(config_data))

        provider = FileSystemSubtestProvider(shared_dir)
        subtests = provider.discover_subtests(TierID.T0)

        assert len(subtests) == 1
        assert subtests[0].system_prompt_mode == "none"

    def test_discover_subtests_default_system_prompt_mode(self, tmp_path: Path) -> None:
        """Test that system_prompt_mode defaults to 'custom'."""
        shared_dir = tmp_path / "shared"
        subtests_dir = shared_dir / "subtests" / "t1"
        subtests_dir.mkdir(parents=True)

        config_file = subtests_dir / "00-test.yaml"
        config_data = {"name": "Test"}
        config_file.write_text(yaml.dump(config_data))

        provider = FileSystemSubtestProvider(shared_dir)
        subtests = provider.discover_subtests(TierID.T1)

        assert len(subtests) == 1
        assert subtests[0].system_prompt_mode == "custom"

    def test_discover_subtests_default_name_and_description(self, tmp_path: Path) -> None:
        """Test default name and description when not provided."""
        shared_dir = tmp_path / "shared"
        subtests_dir = shared_dir / "subtests" / "t1"
        subtests_dir.mkdir(parents=True)

        config_file = subtests_dir / "05-minimal.yaml"
        config_data: dict[str, object] = {}  # Empty config
        config_file.write_text(yaml.dump(config_data))

        provider = FileSystemSubtestProvider(shared_dir)
        subtests = provider.discover_subtests(TierID.T1)

        assert len(subtests) == 1
        assert subtests[0].name == "T1 Sub-test 05"
        assert subtests[0].description == "Sub-test configuration 05-minimal"

    def test_discover_subtests_ignores_non_numeric_files(self, tmp_path: Path) -> None:
        """Test that files without numeric prefix are ignored."""
        shared_dir = tmp_path / "shared"
        subtests_dir = shared_dir / "subtests" / "t1"
        subtests_dir.mkdir(parents=True)

        # Create valid and invalid files
        valid_file = subtests_dir / "00-valid.yaml"
        valid_file.write_text(yaml.dump({"name": "Valid"}))

        invalid_file = subtests_dir / "invalid.yaml"
        invalid_file.write_text(yaml.dump({"name": "Invalid"}))

        readme_file = subtests_dir / "README.yaml"
        readme_file.write_text(yaml.dump({"name": "README"}))

        provider = FileSystemSubtestProvider(shared_dir)
        subtests = provider.discover_subtests(TierID.T1)

        assert len(subtests) == 1
        assert subtests[0].name == "Valid"

    def test_discover_subtests_sorted_by_filename(self, tmp_path: Path) -> None:
        """Test that subtests are discovered in sorted order."""
        shared_dir = tmp_path / "shared"
        subtests_dir = shared_dir / "subtests" / "t1"
        subtests_dir.mkdir(parents=True)

        # Create files out of order
        for idx in ["05", "01", "03", "00", "02"]:
            config_file = subtests_dir / f"{idx}-test.yaml"
            config_file.write_text(yaml.dump({"name": f"Test {idx}"}))

        provider = FileSystemSubtestProvider(shared_dir)
        subtests = provider.discover_subtests(TierID.T1)

        assert len(subtests) == 5
        assert [s.id for s in subtests] == ["00", "01", "02", "03", "05"]

    def test_discover_subtests_empty_yaml(self, tmp_path: Path) -> None:
        """Test handling of empty YAML file."""
        shared_dir = tmp_path / "shared"
        subtests_dir = shared_dir / "subtests" / "t1"
        subtests_dir.mkdir(parents=True)

        config_file = subtests_dir / "00-empty.yaml"
        config_file.write_text("")  # Empty file

        provider = FileSystemSubtestProvider(shared_dir)
        subtests = provider.discover_subtests(TierID.T1)

        assert len(subtests) == 1
        assert subtests[0].id == "00"
        assert subtests[0].resources == {}

    def test_discover_subtests_complex_resources(self, tmp_path: Path) -> None:
        """Test discovery with complex nested resources."""
        shared_dir = tmp_path / "shared"
        subtests_dir = shared_dir / "subtests" / "t5"
        subtests_dir.mkdir(parents=True)

        config_file = subtests_dir / "10-complex.yaml"
        config_data = {
            "name": "Complex",
            "resources": {
                "skills": {"categories": ["agent", "github"]},
                "claude_md": {"blocks": ["B02", "B05"]},
            },
            "mcp_servers": ["server1"],
            "tools": {"list": ["tool1"]},
            "agents": {"levels": [0]},
            "skills": {"names": ["custom-skill"]},
            "inherit_best_from": ["T0", "T1"],
            "agent_teams": True,
            "system_prompt_mode": "default",
        }
        config_file.write_text(yaml.dump(config_data))

        provider = FileSystemSubtestProvider(shared_dir)
        subtests = provider.discover_subtests(TierID.T5)

        assert len(subtests) == 1
        subtest = subtests[0]
        assert subtest.id == "10"
        assert subtest.name == "Complex"
        assert "skills" in subtest.resources
        assert "claude_md" in subtest.resources
        assert "mcp_servers" in subtest.resources
        assert "tools" in subtest.resources
        assert "agents" in subtest.resources
        assert subtest.inherit_best_from == [TierID.T0, TierID.T1]
        assert subtest.agent_teams is True
        assert subtest.system_prompt_mode == "default"

    def test_discover_subtests_null_paths(self, tmp_path: Path) -> None:
        """Test that claude_md_path and claude_dir_path are None."""
        shared_dir = tmp_path / "shared"
        subtests_dir = shared_dir / "subtests" / "t1"
        subtests_dir.mkdir(parents=True)

        config_file = subtests_dir / "00-test.yaml"
        config_file.write_text(yaml.dump({"name": "Test"}))

        provider = FileSystemSubtestProvider(shared_dir)
        subtests = provider.discover_subtests(TierID.T1)

        assert len(subtests) == 1
        assert subtests[0].claude_md_path is None
        assert subtests[0].claude_dir_path is None

    def test_discover_subtests_case_insensitive_tier(self, tmp_path: Path) -> None:
        """Test that tier directories are case-insensitive (lowercase)."""
        shared_dir = tmp_path / "shared"
        # Create lowercase tier directory
        subtests_dir = shared_dir / "subtests" / "t3"
        subtests_dir.mkdir(parents=True)

        config_file = subtests_dir / "00-test.yaml"
        config_file.write_text(yaml.dump({"name": "Test"}))

        provider = FileSystemSubtestProvider(shared_dir)
        # Pass uppercase TierID
        subtests = provider.discover_subtests(TierID.T3)

        assert len(subtests) == 1
        assert subtests[0].name == "Test"
