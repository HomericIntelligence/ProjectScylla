"""Tests for scripts/agents/test_agent_loading.py."""

from __future__ import annotations

from pathlib import Path

import agents.test_agent_loading as _src

# Use the AgentInfo class from the same import chain as test_agent_loading
# to avoid double-import isinstance failures between agents.agent_utils
# and agent_utils (bare import via sys.path).
AgentInfo = _src.AgentInfo
check_for_duplicates = _src.check_for_duplicates
load_agent = _src.load_agent

# Alias to avoid pytest collecting this as a bare test function.
_discover = _src.test_agent_discovery


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_AGENT = """\
---
name: test-agent
description: A test agent
tools: Read, Write
model: sonnet
---

## Role

Test agent.
"""

MISSING_MODEL_AGENT = """\
---
name: test-agent
description: A test agent
tools: Read, Write
---

## Role

Missing model field.
"""


# ---------------------------------------------------------------------------
# TestLoadAgent
# ---------------------------------------------------------------------------


class TestLoadAgent:
    """Tests for load_agent()."""

    def test_valid_file_returns_agent_info(self, tmp_path: Path) -> None:
        """Valid agent file is parsed and returned as an AgentInfo instance."""
        p = tmp_path / "agent.md"
        p.write_text(VALID_AGENT, encoding="utf-8")
        result = load_agent(p)
        assert result is not None
        assert isinstance(result, AgentInfo)

    def test_no_frontmatter_returns_none(self, tmp_path: Path) -> None:
        """File with no YAML frontmatter returns None from load_agent."""
        p = tmp_path / "bare.md"
        p.write_text("# No frontmatter\n\nJust text.\n", encoding="utf-8")
        result = load_agent(p)
        assert result is None

    def test_missing_required_field_returns_none(self, tmp_path: Path) -> None:
        """Agent file missing a required frontmatter field returns None."""
        p = tmp_path / "agent.md"
        p.write_text(MISSING_MODEL_AGENT, encoding="utf-8")
        result = load_agent(p)
        assert result is None

    def test_nonexistent_file_returns_none(self, tmp_path: Path) -> None:
        """A path that does not exist on disk returns None from load_agent."""
        p = tmp_path / "does_not_exist.md"
        result = load_agent(p)
        assert result is None


# ---------------------------------------------------------------------------
# TestCheckForDuplicates
# ---------------------------------------------------------------------------


class TestCheckForDuplicates:
    """Tests for check_for_duplicates()."""

    def test_no_duplicates_returns_empty(self, tmp_path: Path) -> None:
        """Agents with unique names produce an empty duplicate list."""
        agents = [
            AgentInfo(
                tmp_path / "a.md",
                {"name": "agent-a", "description": "A", "tools": "Read", "model": "sonnet"},
            ),
            AgentInfo(
                tmp_path / "b.md",
                {"name": "agent-b", "description": "B", "tools": "Read", "model": "sonnet"},
            ),
        ]
        assert check_for_duplicates(agents) == []

    def test_duplicates_detected(self, tmp_path: Path) -> None:
        """Agents sharing the same name are returned as a duplicate group."""
        agents = [
            AgentInfo(
                tmp_path / "a.md",
                {"name": "same-name", "description": "A", "tools": "Read", "model": "sonnet"},
            ),
            AgentInfo(
                tmp_path / "b.md",
                {"name": "same-name", "description": "B", "tools": "Read", "model": "sonnet"},
            ),
        ]
        dups = check_for_duplicates(agents)
        assert len(dups) == 1
        assert dups[0][0] == "same-name"
        assert len(dups[0][1]) == 2

    def test_empty_list_returns_empty(self) -> None:
        """An empty agent list produces no duplicates."""
        assert check_for_duplicates([]) == []


# ---------------------------------------------------------------------------
# TestAgentDiscovery
# ---------------------------------------------------------------------------


class TestAgentDiscovery:
    """Tests for _discover()."""

    def test_valid_directory(self, tmp_path: Path) -> None:
        """Directory with one valid agent file yields one agent and no errors."""
        (tmp_path / "agent1.md").write_text(VALID_AGENT, encoding="utf-8")
        agents, errors = _discover(tmp_path)
        assert len(agents) == 1
        assert errors == []

    def test_empty_directory(self, tmp_path: Path) -> None:
        """Empty directory yields no agents and at least one error."""
        agents, errors = _discover(tmp_path)
        assert agents == []
        assert len(errors) > 0

    def test_mixed_valid_and_invalid(self, tmp_path: Path) -> None:
        """Mix of valid and invalid files yields one agent and one parse error."""
        (tmp_path / "good.md").write_text(VALID_AGENT, encoding="utf-8")
        (tmp_path / "bad.md").write_text("# No frontmatter\n", encoding="utf-8")
        agents, errors = _discover(tmp_path)
        assert len(agents) == 1
        assert len(errors) == 1
