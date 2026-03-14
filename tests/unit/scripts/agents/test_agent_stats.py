"""Tests for scripts/agents/agent_stats.py."""

from __future__ import annotations

import json
from pathlib import Path

from agents.agent_stats import AgentAnalyzer

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

AGENT_CONTENT_L1 = """\
---
name: test-orchestrator
description: Orchestrates test runs
tools: Read, Write, Bash
model: sonnet
---

## Role

Level 1 orchestrator for evaluation.

See [specialist](./specialist-agent.md) for delegation.
"""

AGENT_CONTENT_L3 = """\
---
name: test-specialist
description: Specialist agent
tools: Read, Grep
model: haiku
---

## Role

Level 3 specialist for metrics.

Uses `metrics-calc` skill for computation.
"""


def _create_agent_dir(tmp_path: Path) -> Path:
    """Create a tmp agents dir with two agent files."""
    d = tmp_path / "agents"
    d.mkdir()
    (d / "orchestrator.md").write_text(AGENT_CONTENT_L1, encoding="utf-8")
    (d / "specialist.md").write_text(AGENT_CONTENT_L3, encoding="utf-8")
    return d


# ---------------------------------------------------------------------------
# TestParseAgentFile
# ---------------------------------------------------------------------------


class TestParseAgentFile:
    """Tests for AgentAnalyzer._parse_agent_file()."""

    def test_valid_file_returns_dict(self, tmp_path: Path) -> None:
        """Valid agent file is parsed into a dict with expected fields."""
        p = tmp_path / "agent.md"
        p.write_text(AGENT_CONTENT_L1, encoding="utf-8")
        analyzer = AgentAnalyzer(tmp_path)
        result = analyzer._parse_agent_file(p)
        assert result is not None
        assert result["name"] == "agent"
        assert result["level"] == 1
        assert "Read" in result["tools"]

    def test_file_with_no_frontmatter(self, tmp_path: Path) -> None:
        """File without frontmatter yields empty frontmatter dict and inferred level."""
        p = tmp_path / "bare.md"
        p.write_text("# Just content\n\nLevel 2 stuff.", encoding="utf-8")
        analyzer = AgentAnalyzer(tmp_path)
        result = analyzer._parse_agent_file(p)
        assert result is not None
        assert result["frontmatter"] == {}
        assert result["level"] == 2

    def test_extracts_delegations(self, tmp_path: Path) -> None:
        """Delegation links in agent body are extracted into the delegations list."""
        p = tmp_path / "agent.md"
        p.write_text(AGENT_CONTENT_L1, encoding="utf-8")
        analyzer = AgentAnalyzer(tmp_path)
        result = analyzer._parse_agent_file(p)
        assert result is not None
        assert len(result["delegations"]) == 1
        assert result["delegations"][0][1] == "specialist-agent.md"

    def test_extracts_skills(self, tmp_path: Path) -> None:
        """Skill references in backtick notation are extracted into the skills list."""
        p = tmp_path / "agent.md"
        p.write_text(AGENT_CONTENT_L3, encoding="utf-8")
        analyzer = AgentAnalyzer(tmp_path)
        result = analyzer._parse_agent_file(p)
        assert result is not None
        assert "metrics-calc" in result["skills"]


# ---------------------------------------------------------------------------
# TestLoadAndAnalyze
# ---------------------------------------------------------------------------


class TestLoadAndAnalyze:
    """Tests for load_agents() + analyze()."""

    def test_loads_agents_from_directory(self, tmp_path: Path) -> None:
        """All markdown files in the agents directory are loaded as agents."""
        agents_dir = _create_agent_dir(tmp_path)
        analyzer = AgentAnalyzer(agents_dir)
        analyzer.load_agents()
        assert len(analyzer.agents) == 2

    def test_empty_directory_loads_nothing(self, tmp_path: Path) -> None:
        """An empty directory results in zero agents loaded."""
        d = tmp_path / "empty"
        d.mkdir()
        analyzer = AgentAnalyzer(d)
        analyzer.load_agents()
        assert len(analyzer.agents) == 0

    def test_analyze_populates_stats(self, tmp_path: Path) -> None:
        """analyze() populates total_agents and by_level stats from loaded agents."""
        agents_dir = _create_agent_dir(tmp_path)
        analyzer = AgentAnalyzer(agents_dir)
        analyzer.load_agents()
        analyzer.analyze()
        assert analyzer.stats["total_agents"] == 2
        assert 1 in analyzer.stats["by_level"]
        assert 3 in analyzer.stats["by_level"]

    def test_analyze_counts_tools(self, tmp_path: Path) -> None:
        """Tool frequency counts reflect how many agents declare each tool."""
        agents_dir = _create_agent_dir(tmp_path)
        analyzer = AgentAnalyzer(agents_dir)
        analyzer.load_agents()
        analyzer.analyze()
        # "Read" appears in both agents
        assert analyzer.stats["tool_frequency"]["Read"] == 2


# ---------------------------------------------------------------------------
# TestFormatters
# ---------------------------------------------------------------------------


class TestFormatText:
    """Tests for format_text()."""

    def test_contains_report_header(self, tmp_path: Path) -> None:
        """Plain-text report contains a header and the total agent count."""
        agents_dir = _create_agent_dir(tmp_path)
        analyzer = AgentAnalyzer(agents_dir)
        analyzer.load_agents()
        analyzer.analyze()
        text = analyzer.format_text()
        assert "Agent System Statistics Report" in text
        assert "Total Agents: 2" in text


class TestFormatMarkdown:
    """Tests for format_markdown()."""

    def test_contains_markdown_header(self, tmp_path: Path) -> None:
        """Markdown report contains an H1 heading for the statistics report."""
        agents_dir = _create_agent_dir(tmp_path)
        analyzer = AgentAnalyzer(agents_dir)
        analyzer.load_agents()
        analyzer.analyze()
        md = analyzer.format_markdown()
        assert "# Agent System Statistics Report" in md


class TestFormatJson:
    """Tests for format_json()."""

    def test_returns_valid_json(self, tmp_path: Path) -> None:
        """JSON output is valid and includes the total_agents count."""
        agents_dir = _create_agent_dir(tmp_path)
        analyzer = AgentAnalyzer(agents_dir)
        analyzer.load_agents()
        analyzer.analyze()
        data = json.loads(analyzer.format_json())
        assert data["total_agents"] == 2

    def test_verbose_includes_extra_keys(self, tmp_path: Path) -> None:
        """Verbose mode JSON includes by_tool and by_skill breakdown keys."""
        agents_dir = _create_agent_dir(tmp_path)
        analyzer = AgentAnalyzer(agents_dir, verbose=True)
        analyzer.load_agents()
        analyzer.analyze()
        data = json.loads(analyzer.format_json())
        assert "by_tool" in data
        assert "by_skill" in data

    def test_non_verbose_excludes_extra_keys(self, tmp_path: Path) -> None:
        """Non-verbose mode JSON omits the by_tool and by_skill breakdown keys."""
        agents_dir = _create_agent_dir(tmp_path)
        analyzer = AgentAnalyzer(agents_dir, verbose=False)
        analyzer.load_agents()
        analyzer.analyze()
        data = json.loads(analyzer.format_json())
        assert "by_tool" not in data
