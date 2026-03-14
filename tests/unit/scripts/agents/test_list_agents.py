"""Tests for scripts/agents/list_agents.py."""

from __future__ import annotations

from pathlib import Path

from agents.agent_utils import AgentInfo
from agents.list_agents import format_description, group_by_level


def make_agent(name: str, level: int, description: str = "A test agent.") -> AgentInfo:
    """Create an AgentInfo fixture with minimal required frontmatter."""
    return AgentInfo(
        Path("/tmp/test.md"),
        {
            "name": name,
            "description": description,
            "tools": "Read, Write",
            "model": "sonnet",
            "level": level,
        },
    )


class TestGroupByLevel:
    """Tests for group_by_level()."""

    def test_empty_list_returns_empty_dict(self) -> None:
        """Empty agent list yields an empty grouping dict."""
        result = group_by_level([])
        assert result == {}

    def test_single_agent_grouped_correctly(self) -> None:
        """Single agent appears under its level key."""
        agent = make_agent("alpha", 1)
        result = group_by_level([agent])
        assert list(result.keys()) == [1]
        assert result[1] == [agent]

    def test_multiple_agents_at_same_level_grouped_together(self) -> None:
        """Two agents at the same level are placed in one group."""
        a1 = make_agent("alpha", 2)
        a2 = make_agent("beta", 2)
        result = group_by_level([a1, a2])
        assert list(result.keys()) == [2]
        assert len(result[2]) == 2

    def test_agents_sorted_by_name_within_level(self) -> None:
        """Agents within each level are sorted alphabetically by name."""
        z = make_agent("zebra", 3)
        a = make_agent("ant", 3)
        m = make_agent("monkey", 3)
        result = group_by_level([z, a, m])
        names = [ag.name for ag in result[3]]
        assert names == ["ant", "monkey", "zebra"]

    def test_agents_at_different_levels_in_separate_groups(self) -> None:
        """Agents at distinct levels appear under separate keys."""
        l0 = make_agent("chief", 0)
        l1 = make_agent("orchestrator", 1)
        l4 = make_agent("engineer", 4)
        result = group_by_level([l0, l1, l4])
        assert set(result.keys()) == {0, 1, 4}
        assert result[0] == [l0]
        assert result[1] == [l1]
        assert result[4] == [l4]


class TestFormatDescription:
    """Tests for format_description()."""

    def test_short_text_under_max_width_returned_as_is(self) -> None:
        """Text shorter than max_width is returned unchanged."""
        text = "Short description."
        result = format_description(text, max_width=60)
        assert result == text

    def test_long_text_wraps_at_word_boundaries(self) -> None:
        """Long text is wrapped so each line fits within max_width."""
        words = ["word"] * 20
        text = " ".join(words)
        result = format_description(text, max_width=20)
        for line in result.split("\n"):
            assert len(line) <= 20

    def test_single_long_word_exceeds_max_width(self) -> None:
        """A single word longer than max_width is not split."""
        long_word = "superlongwordthatexceedsthemax"
        result = format_description(long_word, max_width=10)
        assert result == long_word

    def test_empty_string_returns_empty(self) -> None:
        """Empty input produces empty output."""
        result = format_description("")
        assert result == ""

    def test_custom_indent_applied_to_wrapped_lines(self) -> None:
        """Wrapped continuation lines are indented by the specified amount."""
        words = ["word"] * 20
        text = " ".join(words)
        indent = 4
        result = format_description(text, max_width=20, indent=indent)
        lines = result.split("\n")
        # First line has no indent; subsequent lines should start with spaces
        assert len(lines) > 1
        for line in lines[1:]:
            assert line.startswith(" " * indent)
