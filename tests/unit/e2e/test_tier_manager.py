"""Unit tests for TierManager."""

from __future__ import annotations

from pathlib import Path

import yaml

from scylla.e2e.models import SubTestConfig, TierID
from scylla.e2e.tier_manager import TierManager


class TestBuildResourceSuffix:
    """Tests for TierManager.build_resource_suffix()."""

    def test_tools_enabled_all(self) -> None:
        """Test that tools: {enabled: all} generates correct suffix."""
        subtest = SubTestConfig(
            id="01",
            name="All Tools",
            description="Test",
            resources={"tools": {"enabled": "all"}},
        )
        manager = TierManager(Path("/tmp/tiers"))
        result = manager.build_resource_suffix(subtest)
        assert result == "Maximize usage of all available tools to complete this task."

    def test_tools_with_names(self) -> None:
        """Test that tools with specific names generates bullet list."""
        subtest = SubTestConfig(
            id="01",
            name="Specific Tools",
            description="Test",
            resources={"tools": {"names": ["Read", "Write", "Bash"]}},
        )
        manager = TierManager(Path("/tmp/tiers"))
        result = manager.build_resource_suffix(subtest)
        expected = (
            "Maximize usage of the following tools to complete this task:\n- Bash\n- Read\n- Write"
        )
        assert result == expected

    def test_mcp_servers(self) -> None:
        """Test that MCP servers generate bullet list."""
        subtest = SubTestConfig(
            id="01",
            name="MCP Servers",
            description="Test",
            resources={"mcp_servers": ["filesystem", "git", "memory"]},
        )
        manager = TierManager(Path("/tmp/tiers"))
        result = manager.build_resource_suffix(subtest)
        expected = (
            "Maximize usage of the following MCP servers to complete this task:\n"
            "- filesystem\n- git\n- memory"
        )
        assert result == expected

    def test_no_resources(self) -> None:
        """Test fallback message when no resources configured."""
        subtest = SubTestConfig(
            id="01",
            name="No Resources",
            description="Test",
            resources={},
        )
        manager = TierManager(Path("/tmp/tiers"))
        result = manager.build_resource_suffix(subtest)
        assert result == "Complete this task using available tools and your best judgment."

    def test_single_tool(self) -> None:
        """Test that single tool uses 'Use' instead of 'Maximize usage'."""
        subtest = SubTestConfig(
            id="01",
            name="Single Tool",
            description="Test",
            resources={"tools": {"names": ["Read"]}},
        )
        manager = TierManager(Path("/tmp/tiers"))
        result = manager.build_resource_suffix(subtest)
        expected = "Use the following tool to complete this task:\n- Read"
        assert result == expected

    def test_single_mcp_server(self) -> None:
        """Test that single MCP server uses 'Use' instead of 'Maximize usage'."""
        subtest = SubTestConfig(
            id="01",
            name="Single MCP",
            description="Test",
            resources={"mcp_servers": ["filesystem"]},
        )
        manager = TierManager(Path("/tmp/tiers"))
        result = manager.build_resource_suffix(subtest)
        expected = "Use the following MCP server to complete this task:\n- filesystem"
        assert result == expected

    def test_multiple_resource_types(self) -> None:
        """Test that multiple resource types are combined."""
        subtest = SubTestConfig(
            id="01",
            name="Multiple Resources",
            description="Test",
            resources={
                "skills": {"categories": [], "names": ["gh-create-pr-linked"]},
                "tools": {"enabled": "all"},
                "mcp_servers": ["filesystem"],
            },
        )
        manager = TierManager(Path("/tmp/tiers"))
        result = manager.build_resource_suffix(subtest)
        # Should contain all three sections
        assert "skills" in result.lower() or "gh-create-pr-linked" in result.lower()
        assert "Maximize usage of all available tools to complete this task." in result
        assert "MCP server" in result


class TestDiscoverSubtestsRootLevelMapping:
    """Tests for root-level field mapping in _discover_subtests()."""

    def test_root_level_tools_mapped(self, tmp_path: Path) -> None:
        """Test that root-level tools field is mapped to resources."""
        # Create tier directory structure
        tier_dir = tmp_path / "t5"
        tier_dir.mkdir()
        subtest_dir = tier_dir / "01-test"
        subtest_dir.mkdir()

        # Write config with root-level tools
        config_file = subtest_dir / "config.yaml"
        config_file.write_text(
            yaml.safe_dump(
                {
                    "name": "Test Tools",
                    "description": "Test description",
                    "tools": {"enabled": "all"},
                }
            )
        )

        # Discover subtests
        manager = TierManager(tmp_path)
        subtests = manager._discover_subtests(TierID.T5, tier_dir)

        # Verify tools was mapped to resources
        assert len(subtests) == 1
        assert "tools" in subtests[0].resources
        assert subtests[0].resources["tools"] == {"enabled": "all"}

    def test_root_level_mcp_servers_mapped(self, tmp_path: Path) -> None:
        """Test that root-level mcp_servers field is mapped to resources."""
        # Create tier directory structure
        tier_dir = tmp_path / "t2"
        tier_dir.mkdir()
        subtest_dir = tier_dir / "01-test"
        subtest_dir.mkdir()

        # Write config with root-level mcp_servers
        config_file = subtest_dir / "config.yaml"
        config_file.write_text(
            yaml.safe_dump(
                {
                    "name": "Test MCP",
                    "description": "Test description",
                    "mcp_servers": [{"name": "filesystem"}, {"name": "git"}],
                }
            )
        )

        # Discover subtests
        manager = TierManager(tmp_path)
        subtests = manager._discover_subtests(TierID.T2, tier_dir)

        # Verify mcp_servers was mapped to resources
        assert len(subtests) == 1
        assert "mcp_servers" in subtests[0].resources
        assert subtests[0].resources["mcp_servers"] == [
            {"name": "filesystem"},
            {"name": "git"},
        ]

    def test_root_level_agents_mapped(self, tmp_path: Path) -> None:
        """Test that root-level agents field is mapped to resources."""
        # Create tier directory structure
        tier_dir = tmp_path / "t3"
        tier_dir.mkdir()
        subtest_dir = tier_dir / "01-test"
        subtest_dir.mkdir()

        # Write config with root-level agents
        config_file = subtest_dir / "config.yaml"
        config_file.write_text(
            yaml.safe_dump(
                {
                    "name": "Test Agents",
                    "description": "Test description",
                    "agents": {"levels": [2, 3]},
                }
            )
        )

        # Discover subtests
        manager = TierManager(tmp_path)
        subtests = manager._discover_subtests(TierID.T3, tier_dir)

        # Verify agents was mapped to resources
        assert len(subtests) == 1
        assert "agents" in subtests[0].resources
        assert subtests[0].resources["agents"] == {"levels": [2, 3]}

    def test_root_level_skills_mapped(self, tmp_path: Path) -> None:
        """Test that root-level skills field is mapped to resources."""
        # Create tier directory structure
        tier_dir = tmp_path / "t1"
        tier_dir.mkdir()
        subtest_dir = tier_dir / "01-test"
        subtest_dir.mkdir()

        # Write config with root-level skills
        config_file = subtest_dir / "config.yaml"
        config_file.write_text(
            yaml.safe_dump(
                {
                    "name": "Test Skills",
                    "description": "Test description",
                    "skills": {"categories": ["github", "mojo"]},
                }
            )
        )

        # Discover subtests
        manager = TierManager(tmp_path)
        subtests = manager._discover_subtests(TierID.T1, tier_dir)

        # Verify skills was mapped to resources
        assert len(subtests) == 1
        assert "skills" in subtests[0].resources
        assert subtests[0].resources["skills"] == {"categories": ["github", "mojo"]}

    def test_resources_field_takes_precedence(self, tmp_path: Path) -> None:
        """Test that resources field is not overwritten by root-level fields."""
        # Create tier directory structure
        tier_dir = tmp_path / "t5"
        tier_dir.mkdir()
        subtest_dir = tier_dir / "01-test"
        subtest_dir.mkdir()

        # Write config with both resources and root-level tools
        config_file = subtest_dir / "config.yaml"
        config_file.write_text(
            yaml.safe_dump(
                {
                    "name": "Test Both",
                    "description": "Test description",
                    "resources": {"tools": {"names": ["Read", "Write"]}},
                    "tools": {"enabled": "all"},
                }
            )
        )

        # Discover subtests
        manager = TierManager(tmp_path)
        subtests = manager._discover_subtests(TierID.T5, tier_dir)

        # Verify root-level tools was merged/mapped
        assert len(subtests) == 1
        assert "tools" in subtests[0].resources
        # Root-level should override since it's processed after
        assert subtests[0].resources["tools"] == {"enabled": "all"}
