"""Prompt templates for Claude Code automation.

Contains templates for:
- Issue implementation guidance
- Planning guidance
- PR descriptions
"""

IMPLEMENTATION_PROMPT = """
Implement GitHub issue #{issue_number}.

Follow the project's Python conventions and type hint all function signatures.

**Critical Requirements:**
1. Read the issue description and any existing plan carefully
2. Follow existing code patterns in scylla/
3. Write tests in tests/ using pytest
4. Run tests with: pixi run python -m pytest tests/ -v
5. Ensure all tests pass before finishing
6. Follow the code quality guidelines in CLAUDE.md

**Testing:**
- Write unit tests for new functionality
- Ensure existing tests still pass
- Use pytest fixtures and parametrize where appropriate

**Code Quality:**
- Type hint all function signatures
- Write docstrings for public APIs
- Follow PEP 8 style guidelines
- Keep solutions simple and focused

**IMPORTANT:**
- DO NOT create git commits - the automation will handle that
- DO NOT push changes - the automation will handle that
- DO NOT create PRs - the automation will handle that
- ONLY implement the code and run tests to verify it works

When you're done, just let me know the implementation is complete.
"""

PLAN_PROMPT = """
Create an implementation plan for GitHub issue #{issue_number}.

**Your plan should include:**
1. **Objective** - Brief description of what needs to be done
2. **Approach** - High-level strategy and key decisions
3. **Files to Create** - New files needed with descriptions
4. **Files to Modify** - Existing files to change with specific changes
5. **Implementation Order** - Numbered sequence of steps
6. **Verification** - How to test and verify the implementation
7. **Skills Used** - List skills invoked during planning AND any team
   knowledge base skills referenced in the Prior Learnings section above

**Guidelines:**
- Be specific about file paths and function names
- Reference existing patterns in scylla/ to follow
- Include test file creation in the plan
- Consider dependencies and integration points
- Keep the plan focused on the issue requirements
- In the Skills Used section, include both skills you invoked directly
  and any team knowledge base skills provided in the Prior Learnings
- Document which skills you used during planning so implementers know what context was gathered

**Format:**
Use markdown with clear sections and bullet points.
"""

ADVISE_PROMPT = """
Search the team knowledge base for relevant prior learnings before planning this issue.

**Issue:** #{issue_number}: {issue_title}

{issue_body}

---

**Your task:**
1. Read the skills marketplace: {marketplace_path}
2. Search for plugins matching this issue's topic by:
   - Keywords in plugin names and descriptions
   - Tags and categories
   - Similar problem domains
3. For each relevant plugin, read its SKILL.md file to understand:
   - What worked (successful approaches)
   - What failed (common pitfalls)
   - Recommended parameters and configurations
   - Related patterns and conventions

**Output format:**
## Related Skills
| Plugin | Category | Relevance |
|--------|----------|-----------|
| plugin-name | category | Why it's relevant |

## What Worked
- Successful approach 1
- Successful approach 2

## What Failed
- Common pitfall 1 (from plugin X)
- Common pitfall 2 (from plugin Y)

## Recommended Parameters
- Parameter/configuration 1
- Parameter/configuration 2

If no relevant skills are found, output:
## Related Skills
None found

**Important:** Only return findings from the actual marketplace. Do not speculate or invent skills.
"""

FOLLOW_UP_PROMPT = """
Review your work on issue #{issue_number} and identify any follow-up tasks,
enhancements, or edge cases discovered during implementation.

**Output format:**
Return a JSON array of follow-up items (max 5). Each item must have:
- `title`: Brief, specific title (under 70 characters)
- `body`: Detailed description of the follow-up work
- `labels`: Array of relevant labels from:
  ["enhancement", "bug", "test", "docs", "refactor", "research"]

If there are no follow-up items, return an empty array: `[]`

**Example:**
```json
[
  {{
    "title": "Add edge case handling for empty input",
    "body": "During implementation, discovered that empty input returns
misleading error. Should add validation and specific error message.",
    "labels": ["enhancement", "bug"]
  }},
  {{
    "title": "Add integration tests for new feature",
    "body": "Current tests only cover unit level. Need integration tests
to verify end-to-end behavior with real GitHub API.",
    "labels": ["test"]
  }}
]
```

**Guidelines:**
- Only include concrete, actionable items discovered during this implementation
- Don't include speculative future features
- Keep descriptions concise but specific enough for another developer
- Max 5 items - prioritize the most important
- Return `[]` if no follow-ups needed
"""


def get_implementation_prompt(issue_number: int) -> str:
    """Get the implementation prompt for an issue."""
    return IMPLEMENTATION_PROMPT.format(issue_number=issue_number)


def get_plan_prompt(issue_number: int) -> str:
    """Get the planning prompt for an issue."""
    return PLAN_PROMPT.format(issue_number=issue_number)


def get_advise_prompt(
    issue_number: int,
    issue_title: str,
    issue_body: str,
    marketplace_path: str,
) -> str:
    """Get the advise prompt for searching team knowledge.

    Args:
        issue_number: GitHub issue number
        issue_title: Issue title
        issue_body: Issue body/description
        marketplace_path: Path to marketplace.json

    Returns:
        Formatted advise prompt

    """
    return ADVISE_PROMPT.format(
        issue_number=issue_number,
        issue_title=issue_title,
        issue_body=issue_body,
        marketplace_path=marketplace_path,
    )


def get_follow_up_prompt(issue_number: int) -> str:
    """Get the follow-up prompt for identifying future work.

    Args:
        issue_number: GitHub issue number

    Returns:
        Formatted follow-up prompt

    """
    return FOLLOW_UP_PROMPT.format(issue_number=issue_number)


def get_pr_description(
    issue_number: int,
    summary: str,
    changes: str,
    testing: str,
) -> str:
    """Generate a PR description.

    Args:
        issue_number: GitHub issue number
        summary: Brief summary of changes
        changes: Detailed list of changes
        testing: Testing information

    Returns:
        Formatted PR description

    """
    # Use f-string construction instead of .format() to avoid KeyError on curly braces in content
    return f"""## Summary
{summary}

## Changes
{changes}

## Testing
{testing}

## Closes
Closes #{issue_number}

🤖 Generated with [Claude Code](https://claude.com/claude-code)
"""
