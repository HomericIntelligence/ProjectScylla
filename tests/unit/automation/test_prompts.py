"""Tests for automation prompts."""

from scylla.automation.prompts import (
    get_advise_prompt,
    get_follow_up_prompt,
    get_implementation_prompt,
    get_plan_prompt,
    get_pr_description,
)


def test_get_implementation_prompt():
    """Test implementation prompt generation."""
    prompt = get_implementation_prompt(123)
    assert "123" in prompt
    assert "pytest" in prompt
    assert "type hint" in prompt.lower()


def test_get_plan_prompt():
    """Test plan prompt generation."""
    prompt = get_plan_prompt(456)
    assert "456" in prompt
    assert "Objective" in prompt
    assert "Implementation Order" in prompt
    # Verify it references advise findings
    assert "Prior Learnings" in prompt or "knowledge base" in prompt


def test_get_advise_prompt():
    """Test advise prompt generation."""
    prompt = get_advise_prompt(
        issue_number=789,
        issue_title="Add feature X",
        issue_body="We need to implement feature X",
        marketplace_path="/path/to/marketplace.json",
    )

    assert "789" in prompt
    assert "Add feature X" in prompt
    assert "We need to implement feature X" in prompt
    assert "/path/to/marketplace.json" in prompt
    assert "Related Skills" in prompt
    assert "What Worked" in prompt
    assert "What Failed" in prompt


def test_get_follow_up_prompt():
    """Test follow-up prompt generation."""
    prompt = get_follow_up_prompt(789)
    assert "789" in prompt
    assert "JSON" in prompt
    assert "title" in prompt
    assert "body" in prompt
    assert "labels" in prompt
    assert "enhancement" in prompt
    assert "bug" in prompt
    assert "test" in prompt


def test_get_pr_description():
    """Test PR description generation."""
    desc = get_pr_description(
        issue_number=123,
        summary="Implemented feature X",
        changes="- Added module Y\n- Updated module Z",
        testing="- Added unit tests\n- Verified manually",
    )

    assert "123" in desc
    assert "Implemented feature X" in desc
    assert "Added module Y" in desc
    assert "Added unit tests" in desc
    assert "Closes #123" in desc
    assert "Claude Code" in desc
