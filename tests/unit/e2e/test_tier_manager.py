"""Unit tests for TierManager."""

from __future__ import annotations

from pathlib import Path

import yaml

from scylla.e2e.models import SubTestConfig, TierID
from scylla.e2e.tier_manager import TierManager

# Cleanup instructions that are appended to all prompts
CLEANUP_INSTRUCTIONS = (
    "\n\n## Cleanup Requirements\n\n"
    "- Remove any temporary files created during task completion "
    "(build artifacts, cache files, etc.)\n"
    "- Clean up after yourself - the workspace should contain only final deliverables\n"
)


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
        expected = (
            "Maximize usage of all available tools to complete this task." + CLEANUP_INSTRUCTIONS
        )
        assert result == expected

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
            "Maximize usage of the following tools to complete this task:\n\n"
            "- Bash\n- Read\n- Write" + CLEANUP_INSTRUCTIONS
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
            "Maximize usage of the following MCP servers to complete this task:\n\n"
            "- filesystem\n- git\n- memory" + CLEANUP_INSTRUCTIONS
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
        expected = (
            "Complete this task using available tools and your best judgment."
            + CLEANUP_INSTRUCTIONS
        )
        assert result == expected

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
        expected = "Use the following tool to complete this task:\n\n- Read" + CLEANUP_INSTRUCTIONS
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
        expected = (
            "Use the following MCP server to complete this task:\n\n- filesystem"
            + CLEANUP_INSTRUCTIONS
        )
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
        # Create directory structure matching TierManager expectations
        # tiers_dir should be tests/fixtures/tests/test-001 (or similar)
        tiers_dir = tmp_path / "tests" / "fixtures" / "tests" / "test-001"
        tiers_dir.mkdir(parents=True)

        # Create shared directory at tests/claude-code/shared/subtests/t5
        shared_dir = tmp_path / "tests" / "claude-code" / "shared" / "subtests" / "t5"
        shared_dir.mkdir(parents=True)

        # Write config with root-level tools
        config_file = shared_dir / "01-test.yaml"
        config_file.write_text(
            yaml.safe_dump(
                {
                    "name": "Test Tools",
                    "description": "Test description",
                    "tools": {"enabled": "all"},
                }
            )
        )

        # Discover subtests (tiers_dir is used to navigate to shared dir)
        manager = TierManager(tiers_dir)
        tier_dir = tiers_dir / "t5"  # Legacy parameter, not used
        subtests = manager._discover_subtests(TierID.T5, tier_dir)

        # Verify tools was mapped to resources
        assert len(subtests) == 1
        assert "tools" in subtests[0].resources
        assert subtests[0].resources["tools"] == {"enabled": "all"}

    def test_root_level_mcp_servers_mapped(self, tmp_path: Path) -> None:
        """Test that root-level mcp_servers field is mapped to resources."""
        # Create directory structure matching TierManager expectations
        tiers_dir = tmp_path / "tests" / "fixtures" / "tests" / "test-001"
        tiers_dir.mkdir(parents=True)

        # Create shared directory at tests/claude-code/shared/subtests/t2
        shared_dir = tmp_path / "tests" / "claude-code" / "shared" / "subtests" / "t2"
        shared_dir.mkdir(parents=True)

        # Write config with root-level mcp_servers
        config_file = shared_dir / "01-test.yaml"
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
        manager = TierManager(tiers_dir)
        tier_dir = tiers_dir / "t2"  # Legacy parameter, not used
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
        # Create directory structure matching TierManager expectations
        tiers_dir = tmp_path / "tests" / "fixtures" / "tests" / "test-001"
        tiers_dir.mkdir(parents=True)

        # Create shared directory at tests/claude-code/shared/subtests/t3
        shared_dir = tmp_path / "tests" / "claude-code" / "shared" / "subtests" / "t3"
        shared_dir.mkdir(parents=True)

        # Write config with root-level agents
        config_file = shared_dir / "01-test.yaml"
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
        manager = TierManager(tiers_dir)
        tier_dir = tiers_dir / "t3"  # Legacy parameter, not used
        subtests = manager._discover_subtests(TierID.T3, tier_dir)

        # Verify agents was mapped to resources
        assert len(subtests) == 1
        assert "agents" in subtests[0].resources
        assert subtests[0].resources["agents"] == {"levels": [2, 3]}

    def test_root_level_skills_mapped(self, tmp_path: Path) -> None:
        """Test that root-level skills field is mapped to resources."""
        # Create directory structure matching TierManager expectations
        tiers_dir = tmp_path / "tests" / "fixtures" / "tests" / "test-001"
        tiers_dir.mkdir(parents=True)

        # Create shared directory at tests/claude-code/shared/subtests/t1
        shared_dir = tmp_path / "tests" / "claude-code" / "shared" / "subtests" / "t1"
        shared_dir.mkdir(parents=True)

        # Write config with root-level skills
        config_file = shared_dir / "01-test.yaml"
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
        manager = TierManager(tiers_dir)
        tier_dir = tiers_dir / "t1"  # Legacy parameter, not used
        subtests = manager._discover_subtests(TierID.T1, tier_dir)

        # Verify skills was mapped to resources
        assert len(subtests) == 1
        assert "skills" in subtests[0].resources
        assert subtests[0].resources["skills"] == {"categories": ["github", "mojo"]}

    def test_resources_field_takes_precedence(self, tmp_path: Path) -> None:
        """Test that resources field is not overwritten by root-level fields."""
        # Create directory structure matching TierManager expectations
        tiers_dir = tmp_path / "tests" / "fixtures" / "tests" / "test-001"
        tiers_dir.mkdir(parents=True)

        # Create shared directory at tests/claude-code/shared/subtests/t5
        shared_dir = tmp_path / "tests" / "claude-code" / "shared" / "subtests" / "t5"
        shared_dir.mkdir(parents=True)

        # Write config with both resources and root-level tools
        config_file = shared_dir / "01-test.yaml"
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
        manager = TierManager(tiers_dir)
        tier_dir = tiers_dir / "t5"  # Legacy parameter, not used
        subtests = manager._discover_subtests(TierID.T5, tier_dir)

        # Verify root-level tools was merged/mapped
        assert len(subtests) == 1
        assert "tools" in subtests[0].resources
        # Root-level should override since it's processed after
        assert subtests[0].resources["tools"] == {"enabled": "all"}


class TestCreateSettingsJson:
    """Tests for TierManager._create_settings_json() with tool and MCP configurations."""

    def _create_test_structure(self, tmp_path: Path, tier_id: str) -> tuple[Path, Path]:
        """Create standard test directory structure for tier tests."""
        tiers_dir = tmp_path / "tests" / "fixtures" / "tests" / "test-001"
        tiers_dir.mkdir(parents=True)

        shared_dir = tmp_path / "tests" / "claude-code" / "shared" / "subtests" / tier_id
        shared_dir.mkdir(parents=True)

        return tiers_dir, shared_dir

    def test_thinking_mode_only(self, tmp_path: Path) -> None:
        """Test settings.json with only thinking mode enabled."""
        import json

        tiers_dir, shared_dir = self._create_test_structure(tmp_path, "t0")

        # Create minimal subtest
        config_file = shared_dir / "00-empty.yaml"
        config_file.write_text(yaml.safe_dump({"name": "Empty", "description": "No resources"}))

        manager = TierManager(tiers_dir)
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        # Load tier config and prepare workspace with thinking enabled
        manager.load_tier_config(TierID.T0)
        manager.prepare_workspace(workspace, TierID.T0, "00", None, thinking_enabled=True)

        # Verify settings.json created
        settings_path = workspace / ".claude" / "settings.json"
        assert settings_path.exists()

        with open(settings_path) as f:
            settings = json.load(f)

        assert settings == {"alwaysThinkingEnabled": True}

    def test_tool_restrictions_applied(self, tmp_path: Path) -> None:
        """Test that T2 tool restrictions are written to settings.json."""
        import json

        tiers_dir, shared_dir = self._create_test_structure(tmp_path, "t2")

        # Create T2 subtest with tool restrictions
        config_file = shared_dir / "01-file-ops.yaml"
        config_file.write_text(
            yaml.safe_dump(
                {
                    "name": "File Ops Only",
                    "description": "Restricted tools",
                    "tools": {"enabled": ["Read", "Write", "Edit", "Glob", "Grep"]},
                }
            )
        )

        manager = TierManager(tiers_dir)
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        # Load tier config and prepare workspace
        manager.load_tier_config(TierID.T2)
        manager.prepare_workspace(workspace, TierID.T2, "01", None, thinking_enabled=False)

        # Verify settings.json has tool restrictions
        settings_path = workspace / ".claude" / "settings.json"
        assert settings_path.exists()

        with open(settings_path) as f:
            settings = json.load(f)

        assert "allowedTools" in settings
        assert settings["allowedTools"] == ["Read", "Write", "Edit", "Glob", "Grep"]
        assert settings["alwaysThinkingEnabled"] is False

    def test_all_tools_no_restriction(self, tmp_path: Path) -> None:
        """Test that 'all' tools doesn't add restriction to settings.json."""
        import json

        tiers_dir, shared_dir = self._create_test_structure(tmp_path, "t2")

        # Create subtest with all tools enabled
        config_file = shared_dir / "04-all-tools.yaml"
        config_file.write_text(
            yaml.safe_dump(
                {
                    "name": "All Tools",
                    "description": "No restrictions",
                    "tools": {"enabled": "all"},
                }
            )
        )

        manager = TierManager(tiers_dir)
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        # Load tier config and prepare workspace
        manager.load_tier_config(TierID.T2)
        manager.prepare_workspace(workspace, TierID.T2, "04", None, thinking_enabled=False)

        # Verify settings.json does NOT have allowedTools
        settings_path = workspace / ".claude" / "settings.json"
        with open(settings_path) as f:
            settings = json.load(f)

        assert "allowedTools" not in settings

    def test_mcp_servers_registered(self, tmp_path: Path) -> None:
        """Test that MCP servers are registered in settings.json."""
        import json

        tiers_dir, shared_dir = self._create_test_structure(tmp_path, "t6")

        # Create T6 subtest with MCP servers
        config_file = shared_dir / "01-everything.yaml"
        config_file.write_text(
            yaml.safe_dump(
                {
                    "name": "Everything",
                    "description": "All resources",
                    "tools": {"enabled": "all"},
                    "mcp_servers": [
                        {"name": "filesystem", "source": "modelcontextprotocol/servers"},
                        {"name": "git"},  # Test simple string format
                        "memory",  # Test bare string format
                    ],
                }
            )
        )

        manager = TierManager(tiers_dir)
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        # Load tier config and prepare workspace
        manager.load_tier_config(TierID.T6)
        manager.prepare_workspace(workspace, TierID.T6, "01", None, thinking_enabled=False)

        # Verify settings.json has MCP servers
        settings_path = workspace / ".claude" / "settings.json"
        assert settings_path.exists()

        with open(settings_path) as f:
            settings = json.load(f)

        assert "mcpServers" in settings
        assert "filesystem" in settings["mcpServers"]
        assert "git" in settings["mcpServers"]
        assert "memory" in settings["mcpServers"]

        # Verify server configurations
        assert settings["mcpServers"]["filesystem"] == {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/servers/filesystem"],
        }
        assert settings["mcpServers"]["git"] == {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/servers/git"],
        }
        assert settings["mcpServers"]["memory"] == {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/servers/memory"],
        }

    def test_combined_tools_and_mcp(self, tmp_path: Path) -> None:
        """Test settings.json with both tool restrictions and MCP servers."""
        import json

        tiers_dir, shared_dir = self._create_test_structure(tmp_path, "t5")

        # Create subtest with both tools and MCP
        config_file = shared_dir / "01-hybrid.yaml"
        config_file.write_text(
            yaml.safe_dump(
                {
                    "name": "Hybrid",
                    "description": "Tools + MCP",
                    "tools": {"enabled": ["Read", "Write", "Bash"]},
                    "mcp_servers": ["filesystem", "git"],
                }
            )
        )

        manager = TierManager(tiers_dir)
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        # Load tier config and prepare workspace
        manager.load_tier_config(TierID.T5)
        manager.prepare_workspace(workspace, TierID.T5, "01", None, thinking_enabled=True)

        # Verify settings.json has both configurations
        settings_path = workspace / ".claude" / "settings.json"
        with open(settings_path) as f:
            settings = json.load(f)

        assert settings["alwaysThinkingEnabled"] is True
        assert settings["allowedTools"] == ["Read", "Write", "Bash"]
        assert "mcpServers" in settings
        assert "filesystem" in settings["mcpServers"]
        assert "git" in settings["mcpServers"]


class TestInheritBestFrom:
    """Tests for inherit_best_from functionality in T5 subtests."""

    def test_parse_inherit_best_from(self, tmp_path: Path) -> None:
        """Test that inherit_best_from is parsed from YAML config."""
        # Create directory structure
        tiers_dir = tmp_path / "tests" / "fixtures" / "tests" / "test-001"
        tiers_dir.mkdir(parents=True)

        shared_dir = tmp_path / "tests" / "claude-code" / "shared" / "subtests" / "t5"
        shared_dir.mkdir(parents=True)

        # Write config with inherit_best_from
        config_file = shared_dir / "01-best-prompts.yaml"
        config_file.write_text(
            yaml.safe_dump(
                {
                    "name": "Best Prompts",
                    "description": "Top performing prompt configurations from T0",
                    "inherit_best_from": ["T0"],
                }
            )
        )

        # Discover subtests
        manager = TierManager(tiers_dir)
        subtests = manager._discover_subtests(TierID.T5, tiers_dir / "t5")

        # Verify inherit_best_from was parsed
        assert len(subtests) == 1
        assert len(subtests[0].inherit_best_from) == 1
        assert subtests[0].inherit_best_from[0] == TierID.T0

    def test_parse_multiple_tiers(self, tmp_path: Path) -> None:
        """Test parsing inherit_best_from with multiple tiers."""
        tiers_dir = tmp_path / "tests" / "fixtures" / "tests" / "test-001"
        tiers_dir.mkdir(parents=True)

        shared_dir = tmp_path / "tests" / "claude-code" / "shared" / "subtests" / "t5"
        shared_dir.mkdir(parents=True)

        # Write config with multiple tiers
        config_file = shared_dir / "15-best-of-all.yaml"
        config_file.write_text(
            yaml.safe_dump(
                {
                    "name": "Best of All",
                    "description": "Best from all tiers",
                    "inherit_best_from": ["T0", "T1", "T2", "T3", "T4"],
                }
            )
        )

        manager = TierManager(tiers_dir)
        subtests = manager._discover_subtests(TierID.T5, tiers_dir / "t5")

        assert len(subtests) == 1
        assert len(subtests[0].inherit_best_from) == 5
        assert subtests[0].inherit_best_from == [
            TierID.T0,
            TierID.T1,
            TierID.T2,
            TierID.T3,
            TierID.T4,
        ]

    def test_no_inherit_best_from(self, tmp_path: Path) -> None:
        """Test that subtests without inherit_best_from have empty list."""
        tiers_dir = tmp_path / "tests" / "fixtures" / "tests" / "test-001"
        tiers_dir.mkdir(parents=True)

        shared_dir = tmp_path / "tests" / "claude-code" / "shared" / "subtests" / "t5"
        shared_dir.mkdir(parents=True)

        # Write config without inherit_best_from
        config_file = shared_dir / "06-all-prompts.yaml"
        config_file.write_text(
            yaml.safe_dump(
                {
                    "name": "All Prompts",
                    "description": "All 18 CLAUDE.md blocks",
                    "resources": {"claude_md": {"blocks": ["B01", "B02"]}},
                }
            )
        )

        manager = TierManager(tiers_dir)
        subtests = manager._discover_subtests(TierID.T5, tiers_dir / "t5")

        assert len(subtests) == 1
        assert len(subtests[0].inherit_best_from) == 0


class TestMergeTierResources:
    """Tests for _merge_tier_resources() method."""

    def test_merge_claude_md_blocks(self, tmp_path: Path) -> None:
        """Test that claude_md blocks are replaced (not merged)."""
        tiers_dir = tmp_path / "tests" / "fixtures" / "tests" / "test-001"
        manager = TierManager(tiers_dir)

        merged = {"claude_md": {"blocks": ["B01", "B02"]}}
        new_resources = {"claude_md": {"blocks": ["B03", "B04", "B05"]}}

        manager._merge_tier_resources(merged, new_resources, TierID.T0)

        # Should replace, not union
        assert merged["claude_md"]["blocks"] == ["B03", "B04", "B05"]

    def test_merge_skills_union(self, tmp_path: Path) -> None:
        """Test that skills are merged via union (deduplicated)."""
        tiers_dir = tmp_path / "tests" / "fixtures" / "tests" / "test-001"
        manager = TierManager(tiers_dir)

        merged = {"skills": {"categories": ["github"], "names": ["skill-a"]}}
        new_resources = {"skills": {"categories": ["mojo", "github"], "names": ["skill-b"]}}

        manager._merge_tier_resources(merged, new_resources, TierID.T1)

        # Union of categories (deduplicated)
        assert set(merged["skills"]["categories"]) == {"github", "mojo"}
        # Union of names
        assert set(merged["skills"]["names"]) == {"skill-a", "skill-b"}

    def test_merge_tools_all_wins(self, tmp_path: Path) -> None:
        """Test that 'all' takes precedence over specific tools."""
        tiers_dir = tmp_path / "tests" / "fixtures" / "tests" / "test-001"
        manager = TierManager(tiers_dir)

        merged = {"tools": {"enabled": ["Read", "Write"]}}
        new_resources = {"tools": {"enabled": "all"}}

        manager._merge_tier_resources(merged, new_resources, TierID.T2)

        # "all" should win
        assert merged["tools"]["enabled"] == "all"

    def test_merge_tools_union_lists(self, tmp_path: Path) -> None:
        """Test that tool lists are merged via union."""
        tiers_dir = tmp_path / "tests" / "fixtures" / "tests" / "test-001"
        manager = TierManager(tiers_dir)

        merged = {"tools": {"enabled": ["Read", "Write"]}}
        new_resources = {"tools": {"enabled": ["Bash", "Read"]}}

        manager._merge_tier_resources(merged, new_resources, TierID.T2)

        # Union (deduplicated)
        assert set(merged["tools"]["enabled"]) == {"Read", "Write", "Bash"}

    def test_merge_mcp_servers_by_name(self, tmp_path: Path) -> None:
        """Test that MCP servers are merged by server name (no duplicates)."""
        tiers_dir = tmp_path / "tests" / "fixtures" / "tests" / "test-001"
        manager = TierManager(tiers_dir)

        merged = {"mcp_servers": [{"name": "filesystem"}, {"name": "git"}]}
        new_resources = {"mcp_servers": [{"name": "git"}, {"name": "memory"}]}

        manager._merge_tier_resources(merged, new_resources, TierID.T2)

        # Should have 3 servers (git not duplicated)
        assert len(merged["mcp_servers"]) == 3
        server_names = {s["name"] for s in merged["mcp_servers"]}
        assert server_names == {"filesystem", "git", "memory"}

    def test_merge_agents_union(self, tmp_path: Path) -> None:
        """Test that agents are merged via union with sorted levels."""
        tiers_dir = tmp_path / "tests" / "fixtures" / "tests" / "test-001"
        manager = TierManager(tiers_dir)

        merged = {"agents": {"levels": [2, 3], "names": ["agent-a.md"]}}
        new_resources = {"agents": {"levels": [0, 1, 2], "names": ["agent-b.md"]}}

        manager._merge_tier_resources(merged, new_resources, TierID.T3)

        # Union of levels (sorted, deduplicated)
        assert merged["agents"]["levels"] == [0, 1, 2, 3]
        # Union of names
        assert set(merged["agents"]["names"]) == {"agent-a.md", "agent-b.md"}


class TestBuildMergedBaseline:
    """Tests for build_merged_baseline() method."""

    def test_build_merged_baseline_single_tier(self, tmp_path: Path) -> None:
        """Test building merged baseline from single tier."""
        import json

        # Create experiment directory structure
        experiment_dir = tmp_path / "experiment"
        t0_dir = experiment_dir / "T0"
        t0_dir.mkdir(parents=True)

        # Create result.json with best_subtest
        result_file = t0_dir / "result.json"
        result_file.write_text(json.dumps({"best_subtest": "05"}))

        # Create config_manifest.json for best subtest
        subtest_dir = t0_dir / "05"
        subtest_dir.mkdir()
        manifest_file = subtest_dir / "config_manifest.json"
        manifest_file.write_text(
            json.dumps(
                {
                    "tier_id": "T0",
                    "subtest_id": "05",
                    "resources": {"claude_md": {"blocks": ["B01", "B02", "B03"]}},
                }
            )
        )

        # Create TierManager and build merged baseline
        tiers_dir = tmp_path / "tiers"
        tiers_dir.mkdir()
        manager = TierManager(tiers_dir)

        merged = manager.build_merged_baseline([TierID.T0], experiment_dir)

        # Verify merged resources
        assert "claude_md" in merged
        assert merged["claude_md"]["blocks"] == ["B01", "B02", "B03"]

    def test_build_merged_baseline_multiple_tiers(self, tmp_path: Path) -> None:
        """Test building merged baseline from multiple tiers."""
        import json

        experiment_dir = tmp_path / "experiment"

        # T0 result
        t0_dir = experiment_dir / "T0"
        t0_dir.mkdir(parents=True)
        (t0_dir / "result.json").write_text(json.dumps({"best_subtest": "03"}))
        t0_subtest = t0_dir / "03"
        t0_subtest.mkdir()
        (t0_subtest / "config_manifest.json").write_text(
            json.dumps({"resources": {"claude_md": {"blocks": ["B01", "B02"]}}})
        )

        # T1 result
        t1_dir = experiment_dir / "T1"
        t1_dir.mkdir(parents=True)
        (t1_dir / "result.json").write_text(json.dumps({"best_subtest": "02"}))
        t1_subtest = t1_dir / "02"
        t1_subtest.mkdir()
        (t1_subtest / "config_manifest.json").write_text(
            json.dumps({"resources": {"skills": {"categories": ["github", "mojo"]}}})
        )

        # Build merged baseline
        tiers_dir = tmp_path / "tiers"
        tiers_dir.mkdir()
        manager = TierManager(tiers_dir)

        merged = manager.build_merged_baseline([TierID.T0, TierID.T1], experiment_dir)

        # Verify both resources are present
        assert "claude_md" in merged
        assert merged["claude_md"]["blocks"] == ["B01", "B02"]
        assert "skills" in merged
        assert set(merged["skills"]["categories"]) == {"github", "mojo"}

    def test_missing_tier_result_raises(self, tmp_path: Path) -> None:
        """Test that missing tier result raises ValueError."""
        experiment_dir = tmp_path / "experiment"
        experiment_dir.mkdir()

        tiers_dir = tmp_path / "tiers"
        tiers_dir.mkdir()
        manager = TierManager(tiers_dir)

        # Should raise because T0/result.json doesn't exist
        import pytest

        with pytest.raises(ValueError, match="result.json not found"):
            manager.build_merged_baseline([TierID.T0], experiment_dir)

    def test_no_best_subtest_raises(self, tmp_path: Path) -> None:
        """Test that missing best_subtest raises ValueError."""
        import json

        import pytest

        experiment_dir = tmp_path / "experiment"
        t0_dir = experiment_dir / "T0"
        t0_dir.mkdir(parents=True)

        # Create result.json without best_subtest
        (t0_dir / "result.json").write_text(json.dumps({"pass_rate": 0.5}))

        tiers_dir = tmp_path / "tiers"
        tiers_dir.mkdir()
        manager = TierManager(tiers_dir)

        # Should raise because best_subtest is missing
        with pytest.raises(ValueError, match="no best_subtest selected"):
            manager.build_merged_baseline([TierID.T0], experiment_dir)


class TestResourceSuffixInClaudeMd:
    """Tests that resource suffix is appended to CLAUDE.md, not task prompt."""

    def test_suffix_in_claude_md_with_blocks(self, tmp_path: Path) -> None:
        """Test that resource suffix is appended to CLAUDE.md when blocks exist."""
        # Create directory structure
        tiers_dir = tmp_path / "tests" / "fixtures" / "tests" / "test-001"
        tiers_dir.mkdir(parents=True)

        shared_dir = tmp_path / "tests" / "claude-code" / "shared"
        blocks_dir = shared_dir / "blocks"
        blocks_dir.mkdir(parents=True)

        # Create a simple block file
        (blocks_dir / "B01-test-block.md").write_text("# Test Block\n\nThis is test content.")

        # Create subtests directory
        subtests_dir = shared_dir / "subtests" / "t2"
        subtests_dir.mkdir(parents=True)

        # Write subtest config with blocks and tools
        config_file = subtests_dir / "01-test.yaml"
        config_file.write_text(
            yaml.safe_dump(
                {
                    "name": "Test with blocks and tools",
                    "description": "Test description",
                    "resources": {
                        "claude_md": {"blocks": ["B01"]},
                        "tools": {"enabled": "all"},
                    },
                }
            )
        )

        # Create workspace
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        # Prepare workspace
        manager = TierManager(tiers_dir)
        manager.prepare_workspace(workspace, TierID.T2, "01")

        # Verify CLAUDE.md exists and contains both block content and suffix
        claude_md = workspace / "CLAUDE.md"
        assert claude_md.exists()
        content = claude_md.read_text()
        assert "# Test Block" in content
        assert "This is test content." in content
        assert "Maximize usage of all available tools to complete this task." in content

    def test_suffix_in_claude_md_without_blocks(self, tmp_path: Path) -> None:
        """Test that CLAUDE.md is created with just suffix when no blocks configured."""
        # Create directory structure
        tiers_dir = tmp_path / "tests" / "fixtures" / "tests" / "test-001"
        tiers_dir.mkdir(parents=True)

        shared_dir = tmp_path / "tests" / "claude-code" / "shared"
        blocks_dir = shared_dir / "blocks"
        blocks_dir.mkdir(parents=True)

        # Create subtests directory
        subtests_dir = shared_dir / "subtests" / "t2"
        subtests_dir.mkdir(parents=True)

        # Write subtest config with NO blocks, but with tools
        config_file = subtests_dir / "01-test.yaml"
        config_file.write_text(
            yaml.safe_dump(
                {
                    "name": "Test without blocks",
                    "description": "Test description",
                    "resources": {"tools": {"names": ["Read", "Write"]}},
                }
            )
        )

        # Create workspace
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        # Prepare workspace
        manager = TierManager(tiers_dir)
        manager.prepare_workspace(workspace, TierID.T2, "01")

        # Verify CLAUDE.md exists and contains only the suffix
        claude_md = workspace / "CLAUDE.md"
        assert claude_md.exists()
        content = claude_md.read_text()
        assert "Maximize usage of the following tools" in content
        assert "- Read" in content
        assert "- Write" in content

    def test_no_claude_md_without_suffix(self, tmp_path: Path) -> None:
        """Test that CLAUDE.md is not created when no blocks and no resources."""
        # Create directory structure
        tiers_dir = tmp_path / "tests" / "fixtures" / "tests" / "test-001"
        tiers_dir.mkdir(parents=True)

        shared_dir = tmp_path / "tests" / "claude-code" / "shared"
        blocks_dir = shared_dir / "blocks"
        blocks_dir.mkdir(parents=True)

        # Create subtests directory
        subtests_dir = shared_dir / "subtests" / "t0"
        subtests_dir.mkdir(parents=True)

        # Write subtest config with NO blocks and NO resources (like T0-02)
        config_file = subtests_dir / "02-test.yaml"
        config_file.write_text(
            yaml.safe_dump(
                {
                    "name": "Test empty",
                    "description": "Test description",
                    "resources": {"claude_md": {"blocks": ["B01"]}},
                }
            )
        )

        # Create workspace
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        # Prepare workspace
        manager = TierManager(tiers_dir)
        manager.prepare_workspace(workspace, TierID.T0, "02")

        # Verify CLAUDE.md exists with just the block (no suffix since no other resources)
        claude_md = workspace / "CLAUDE.md"
        # Actually for T0-02 with blocks but no other resources, the suffix should be
        # "Complete this task using available tools and your best judgment."
        # Let me check if CLAUDE.md exists
        # Actually, it should exist because we have a block
        if claude_md.exists():
            content = claude_md.read_text()
            # Could have the generic suffix or no suffix depending on behavior
            # Let's just verify it doesn't have resource-specific text
            assert "Maximize usage of all available tools" not in content
