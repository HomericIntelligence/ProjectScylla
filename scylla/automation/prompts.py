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
5. Ensure all tests pass before committing
6. Follow the commit message format in CLAUDE.md

**Testing:**
- Write unit tests for new functionality
- Ensure existing tests still pass
- Use pytest fixtures and parametrize where appropriate

**Code Quality:**
- Type hint all function signatures
- Write docstrings for public APIs
- Follow PEP 8 style guidelines
- Keep solutions simple and focused

When you're done:
1. Run the test suite
2. Create a commit following the conventional commits format
3. Push the changes
4. Create a PR that closes the issue
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

**Guidelines:**
- Be specific about file paths and function names
- Reference existing patterns in scylla/ to follow
- Include test file creation in the plan
- Consider dependencies and integration points
- Keep the plan focused on the issue requirements

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
