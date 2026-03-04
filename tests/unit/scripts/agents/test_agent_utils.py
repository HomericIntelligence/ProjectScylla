"""Tests for scripts/agents/agent_utils.py."""

from __future__ import annotations

from pathlib import Path

from agents.agent_utils import (
    AgentInfo,
    extract_frontmatter_full,
    extract_frontmatter_parsed,
    extract_frontmatter_raw,
    extract_frontmatter_with_lines,
    find_agent_files,
    load_agent,
    load_all_agents,
    validate_frontmatter_structure,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_FRONTMATTER_CONTENT = """\
---
name: test-agent
description: A test agent
tools: Read, Write
model: sonnet
---

## Role

Test agent for unit tests.
"""

NO_FRONTMATTER_CONTENT = """\
# No Frontmatter

Just a regular markdown file.
"""

INVALID_YAML_CONTENT = """\
---
name: [unclosed bracket
---

## Content
"""


# ---------------------------------------------------------------------------
# extract_frontmatter_raw
# ---------------------------------------------------------------------------


class TestExtractFrontmatterRaw:
    """Tests for extract_frontmatter_raw()."""

    def test_extracts_raw_text_from_valid_content(self) -> None:
        """Returns raw frontmatter text for valid content."""
        result = extract_frontmatter_raw(VALID_FRONTMATTER_CONTENT)
        assert result is not None
        assert "name: test-agent" in result

    def test_returns_none_when_no_frontmatter(self) -> None:
        """Returns None when no frontmatter is present."""
        result = extract_frontmatter_raw(NO_FRONTMATTER_CONTENT)
        assert result is None

    def test_returns_none_for_empty_string(self) -> None:
        """Returns None for empty string."""
        assert extract_frontmatter_raw("") is None

    def test_returns_none_without_closing_delimiter(self) -> None:
        """Returns None when opening --- has no closing ---."""
        content = "---\nname: test\n"
        assert extract_frontmatter_raw(content) is None


# ---------------------------------------------------------------------------
# extract_frontmatter_with_lines
# ---------------------------------------------------------------------------


class TestExtractFrontmatterWithLines:
    """Tests for extract_frontmatter_with_lines()."""

    def test_returns_tuple_on_valid_content(self) -> None:
        """Returns (text, start_line, end_line) tuple for valid content."""
        result = extract_frontmatter_with_lines(VALID_FRONTMATTER_CONTENT)
        assert result is not None
        text, start, end = result
        assert isinstance(text, str)
        assert start == 1
        assert end > start

    def test_returns_none_without_frontmatter(self) -> None:
        """Returns None when no frontmatter found."""
        assert extract_frontmatter_with_lines(NO_FRONTMATTER_CONTENT) is None

    def test_start_line_is_one(self) -> None:
        """Start line is always 1 (opening delimiter is first line)."""
        result = extract_frontmatter_with_lines(VALID_FRONTMATTER_CONTENT)
        assert result is not None
        _, start, _ = result
        assert start == 1


# ---------------------------------------------------------------------------
# extract_frontmatter_parsed
# ---------------------------------------------------------------------------


class TestExtractFrontmatterParsed:
    """Tests for extract_frontmatter_parsed()."""

    def test_returns_parsed_dict(self) -> None:
        """Returns (text, dict) tuple with parsed YAML."""
        result = extract_frontmatter_parsed(VALID_FRONTMATTER_CONTENT)
        assert result is not None
        _text, data = result
        assert data["name"] == "test-agent"
        assert data["model"] == "sonnet"

    def test_returns_none_without_frontmatter(self) -> None:
        """Returns None when no frontmatter found."""
        assert extract_frontmatter_parsed(NO_FRONTMATTER_CONTENT) is None

    def test_returns_none_for_invalid_yaml(self) -> None:
        """Returns None when YAML is malformed."""
        result = extract_frontmatter_parsed(INVALID_YAML_CONTENT)
        assert result is None


# ---------------------------------------------------------------------------
# extract_frontmatter_full
# ---------------------------------------------------------------------------


class TestExtractFrontmatterFull:
    """Tests for extract_frontmatter_full()."""

    def test_returns_all_four_fields(self) -> None:
        """Returns (text, dict, start_line, end_line) for valid content."""
        result = extract_frontmatter_full(VALID_FRONTMATTER_CONTENT)
        assert result is not None
        text, data, start, end = result
        assert isinstance(text, str)
        assert isinstance(data, dict)
        assert start == 1
        assert end > start

    def test_returns_none_without_frontmatter(self) -> None:
        """Returns None when no frontmatter found."""
        assert extract_frontmatter_full(NO_FRONTMATTER_CONTENT) is None


# ---------------------------------------------------------------------------
# AgentInfo
# ---------------------------------------------------------------------------


class TestAgentInfo:
    """Tests for AgentInfo class."""

    def make_agent(self, **overrides: object) -> AgentInfo:
        """Create an AgentInfo with default fields."""
        frontmatter = {
            "name": "test-agent",
            "description": "Test agent",
            "tools": "Read, Write",
            "model": "sonnet",
            **overrides,
        }
        return AgentInfo(Path("test.md"), frontmatter)

    def test_name_from_frontmatter(self) -> None:
        """AgentInfo.name comes from frontmatter."""
        agent = self.make_agent(name="my-agent")
        assert agent.name == "my-agent"

    def test_tools_list_split_correctly(self) -> None:
        """get_tools_list() splits tools string into list."""
        agent = self.make_agent(tools="Read, Write, Edit")
        tools = agent.get_tools_list()
        assert tools == ["Read", "Write", "Edit"]

    def test_empty_tools_returns_empty_list(self) -> None:
        """Empty tools string returns empty list."""
        agent = self.make_agent(tools="")
        assert agent.get_tools_list() == []

    def test_level_from_explicit_field(self) -> None:
        """Level is taken directly when 'level' is in frontmatter."""
        agent = self.make_agent(level=2)
        assert agent.level == 2

    def test_level_inferred_chief_evaluator(self) -> None:
        """Chief-evaluator name infers level 0."""
        agent = self.make_agent(name="chief-evaluator")
        assert agent.level == 0

    def test_level_inferred_orchestrator(self) -> None:
        """Orchestrator name infers level 1."""
        agent = self.make_agent(name="evaluation-orchestrator")
        assert agent.level == 1

    def test_level_inferred_engineer(self) -> None:
        """Engineer name infers level 4."""
        agent = self.make_agent(name="implementation-engineer")
        assert agent.level == 4

    def test_repr_contains_name_and_level(self) -> None:
        """__repr__ includes name and level."""
        agent = self.make_agent(name="test-agent", level=3)
        r = repr(agent)
        assert "test-agent" in r
        assert "3" in r


# ---------------------------------------------------------------------------
# find_agent_files
# ---------------------------------------------------------------------------


class TestFindAgentFiles:
    """Tests for find_agent_files()."""

    def test_finds_md_files(self, tmp_path: Path) -> None:
        """Returns sorted list of .md files in directory."""
        (tmp_path / "agent1.md").write_text("# A1")
        (tmp_path / "agent2.md").write_text("# A2")
        result = find_agent_files(tmp_path)
        assert len(result) == 2

    def test_ignores_non_md_files(self, tmp_path: Path) -> None:
        """Non-.md files are not returned."""
        (tmp_path / "config.yaml").write_text("key: value")
        (tmp_path / "agent.md").write_text("# Agent")
        result = find_agent_files(tmp_path)
        assert len(result) == 1

    def test_empty_directory(self, tmp_path: Path) -> None:
        """Empty directory returns empty list."""
        assert find_agent_files(tmp_path) == []


# ---------------------------------------------------------------------------
# load_agent
# ---------------------------------------------------------------------------


class TestLoadAgent:
    """Tests for load_agent()."""

    def test_loads_valid_agent_file(self, tmp_path: Path) -> None:
        """Returns AgentInfo for valid agent markdown file."""
        f = tmp_path / "agent.md"
        f.write_text(VALID_FRONTMATTER_CONTENT)
        result = load_agent(f)
        assert result is not None
        assert result.name == "test-agent"

    def test_returns_none_for_missing_file(self, tmp_path: Path) -> None:
        """Returns None when file does not exist."""
        missing = tmp_path / "nonexistent.md"
        assert load_agent(missing) is None

    def test_returns_none_for_file_without_frontmatter(self, tmp_path: Path) -> None:
        """Returns None when markdown has no frontmatter."""
        f = tmp_path / "no_fm.md"
        f.write_text(NO_FRONTMATTER_CONTENT)
        assert load_agent(f) is None


# ---------------------------------------------------------------------------
# load_all_agents
# ---------------------------------------------------------------------------


class TestLoadAllAgents:
    """Tests for load_all_agents()."""

    def test_loads_multiple_agents(self, tmp_path: Path) -> None:
        """Loads all valid agent files from directory."""
        (tmp_path / "agent1.md").write_text(VALID_FRONTMATTER_CONTENT)
        (tmp_path / "agent2.md").write_text(
            VALID_FRONTMATTER_CONTENT.replace("test-agent", "agent2")
        )
        result = load_all_agents(tmp_path)
        assert len(result) == 2

    def test_skips_invalid_files(self, tmp_path: Path) -> None:
        """Invalid agent files are skipped."""
        (tmp_path / "good.md").write_text(VALID_FRONTMATTER_CONTENT)
        (tmp_path / "bad.md").write_text(NO_FRONTMATTER_CONTENT)
        result = load_all_agents(tmp_path)
        assert len(result) == 1

    def test_empty_directory(self, tmp_path: Path) -> None:
        """Empty directory returns empty list."""
        assert load_all_agents(tmp_path) == []


# ---------------------------------------------------------------------------
# validate_frontmatter_structure
# ---------------------------------------------------------------------------


class TestValidateFrontmatterStructure:
    """Tests for validate_frontmatter_structure()."""

    def test_no_errors_for_valid_frontmatter(self) -> None:
        """Valid frontmatter with all required fields returns no errors."""
        fm = {"name": "test-agent", "description": "Test", "tools": "Read", "model": "sonnet"}
        errors = validate_frontmatter_structure(fm)
        assert errors == []

    def test_error_for_missing_required_field(self) -> None:
        """Missing required field produces an error."""
        fm = {"description": "Test", "tools": "Read", "model": "sonnet"}
        errors = validate_frontmatter_structure(fm)
        assert any("name" in e for e in errors)

    def test_error_for_wrong_type(self) -> None:
        """Wrong type for a required field produces an error."""
        fm = {"name": 123, "description": "Test", "tools": "Read", "model": "sonnet"}
        errors = validate_frontmatter_structure(fm)
        assert any("name" in e for e in errors)

    def test_error_for_optional_field_wrong_type(self) -> None:
        """Wrong type for an optional field (when present) produces an error."""
        fm = {
            "name": "test-agent",
            "description": "Test",
            "tools": "Read",
            "model": "sonnet",
            "level": "not-an-int",  # should be int
        }
        errors = validate_frontmatter_structure(fm)
        assert any("level" in e for e in errors)

    def test_custom_required_fields(self) -> None:
        """Custom required_fields override the defaults."""
        fm = {"custom_field": "value"}
        errors = validate_frontmatter_structure(fm, required_fields={"custom_field": str})
        assert errors == []
