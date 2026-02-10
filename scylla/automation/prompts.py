"""Prompt templates for Claude Code automation.

Contains templates for:
- Issue implementation guidance
- Commit message generation
- CI failure fixes
- Work summary generation
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

COMMIT_PROMPT = """
Create a git commit for the changes you just made.

**Requirements:**
1. Use conventional commits format: type(scope): description
2. Keep the first line under 70 characters
3. Add "Closes #{issue_number}" in the commit body
4. Add co-author line: Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>

**Example:**
```
feat(automation): Add bulk issue planner

Implements parallel planning of GitHub issues with rate limit handling.

Closes #{issue_number}

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```
"""

CI_FIX_PROMPT = """
The CI checks failed on your PR. Please fix the issues and push again.

**Common CI failures:**
1. Test failures - Run: pixi run python -m pytest tests/ -v
2. Type checking - Run: pre-commit run mypy --all-files
3. Linting - Run: pre-commit run ruff --all-files
4. Formatting - Run: pre-commit run black --all-files

**Steps:**
1. Review the CI failure logs
2. Fix the issues locally
3. Re-run the tests and checks
4. Commit the fixes
5. Push to update the PR

Do NOT skip pre-commit hooks with --no-verify.
"""

SUMMARY_PROMPT = """
Provide a brief summary of the work completed for issue #{issue_number}.

**Include:**
1. What was implemented
2. Key files changed
3. Test coverage added
4. Any notable decisions or trade-offs

**Format:**
Keep it concise (3-5 sentences). Focus on what was done, not how long it took.
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

PR_DESCRIPTION_TEMPLATE = """
## Summary
{summary}

## Changes
{changes}

## Testing
{testing}

## Closes
Closes #{issue_number}

🤖 Generated with [Claude Code](https://claude.com/claude-code)
"""


def get_implementation_prompt(issue_number: int) -> str:
    """Get the implementation prompt for an issue."""
    return IMPLEMENTATION_PROMPT.format(issue_number=issue_number)


def get_commit_prompt(issue_number: int) -> str:
    """Get the commit prompt for an issue."""
    return COMMIT_PROMPT.format(issue_number=issue_number)


def get_ci_fix_prompt() -> str:
    """Get the CI fix prompt."""
    return CI_FIX_PROMPT


def get_summary_prompt(issue_number: int) -> str:
    """Get the summary prompt for an issue."""
    return SUMMARY_PROMPT.format(issue_number=issue_number)


def get_plan_prompt(issue_number: int) -> str:
    """Get the planning prompt for an issue."""
    return PLAN_PROMPT.format(issue_number=issue_number)


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
    return PR_DESCRIPTION_TEMPLATE.format(
        issue_number=issue_number,
        summary=summary,
        changes=changes,
        testing=testing,
    )
