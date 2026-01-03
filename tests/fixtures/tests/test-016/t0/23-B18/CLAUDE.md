## GitHub Issue Structure

All planning is done through GitHub issues with clear structure:

### Issue Body Format

```markdown
## Objective
Brief description (2-3 sentences)

## Deliverables
- [ ] Deliverable 1
- [ ] Deliverable 2

## Success Criteria
- [ ] Criterion 1
- [ ] Criterion 2

## Dependencies
- Depends on #<parent-issue>
- Related: #<sibling-issue>

## Notes
Additional context
```

### Issue Labels

- `planning` - Design phase
- `testing` - Test development
- `implementation` - Code implementation
- `packaging` - Distribution packages
- `cleanup` - Finalization

### Linking Issues

- Reference in body: `Depends on #123`
- Reference in commits: `Implements #123`
- Close via PR: `Closes #123`

## Working with GitHub Issues

All planning and documentation is managed through GitHub issues directly.

### Creating New Work Items

1. Create a GitHub issue with clear description and acceptance criteria
2. Use appropriate labels (planning, testing, implementation, packaging, cleanup)
3. Link related issues using `#<number>` references

### Tracking Implementation

1. Read issue context: `gh issue view <number> --comments`
2. Post progress updates as issue comments
3. Link PRs to issues: `gh pr create --body "Closes #<number>"`

### Documentation Workflow

1. **Read context first**: `gh issue view <number> --comments`
2. **Post updates**: `gh issue comment <number> --body "..."`
3. **Reference in commits**: "Implements #<number>" or "Closes #<number>"

See `.claude/shared/github-issue-workflow.md` for complete workflow patterns.

### File Locations

- **Scripts**: `scripts/*.py`
- **Logs**: `logs/*.log`
- **Tracked Docs**: `docs/dev/`, `agents/` (reference these in commits)
- **Issue Docs**: GitHub issue comments (not local files)

## Git Workflow

### Branch Naming

- `main` - Production branch (protected, requires PR)
- `<issue-number>-<description>` - Feature/fix branches (e.g., `1928-consolidate-test-assertions`)

### Development Workflow

**IMPORTANT:** The `main` branch is protected. All changes must go through a pull request.

#### Creating a PR (Standard Workflow)

1. **Create a feature branch:**

   ```bash
   git checkout -b <issue-number>-<description>
   ```

1. **Make your changes and commit:**

   ```bash
   git add <files>
   git commit -m "$(cat <<'EOF'
   type(scope): Brief description

   Detailed explanation of changes.

   🤖 Generated with [Claude Code](<https://claude.com/claude-code>)

   Co-Authored-By: Claude <noreply@anthropic.com>
   EOF
   )"
   ```

1. **Push the feature branch:**

   ```bash
   git push -u origin <branch-name>
   ```

1. **Create pull request:**

   ```bash
   gh pr create \
     --title "[Type] Brief description" \
     --body "Closes #<issue-number>" \
     --label "appropriate-label"
   ```

1. **Enable auto-merge:**

   ```bash
   gh pr merge --auto --rebase
   ```

   **Always enable auto-merge** so PRs merge automatically once CI passes.

### 🚫 Never Push Directly to Main

**⚠️ CRITICAL:** See [CRITICAL RULES section](#️-critical-rules---read-first) at the top of this document.

**This rule has NO EXCEPTIONS - not even for emergencies.**

❌ **ABSOLUTELY PROHIBITED:**

```bash
git checkout main
git add <files>
git commit -m "changes"
git push origin main  # Will be rejected - main is protected
```

**Even These Are WRONG:**

```bash
# ❌ WRONG - Bypassing with force push
git push --force origin main

# ❌ WRONG - Directly committing on main
git checkout main && git commit -am "quick fix"

# ❌ WRONG - Emergency fix without PR
git checkout main && git cherry-pick <commit> && git push
```

✅ **CORRECT - ALWAYS Use Pull Requests:**

```bash
# 1. Create feature branch from main
git checkout main
git pull origin main
git checkout -b <issue-number>-description

# 2. Make changes and commit
git add <files>
git commit -m "type(scope): description"

# 3. Push feature branch
git push -u origin <issue-number>-description

# 4. Create and auto-merge PR
gh pr create \
  --title "Brief description" \
  --body "Closes #<issue-number>" \
  --label "appropriate-label"
gh pr merge --auto --rebase
```

**Why This Rule Exists:**

1. **Code Review** - All changes must be reviewed
2. **CI Validation** - All changes must pass automated tests
3. **Audit Trail** - Track what changed, why, and who approved it
4. **Prevent Breakage** - Catch issues before they hit production
5. **Branch Protection** - GitHub enforces this rule automatically

**What If CI Is Already Broken?**

- Still create a PR to fix it
- PR description should explain the emergency
- Enable auto-merge so it merges immediately when CI passes
- Example: PR #2689 (cleanup) followed emergency fix commit 4446eba2

## Commit Message Format

Follow conventional commits:

```text
feat(section): Add new component
fix(scripts): Correct parsing issue
docs(readme): Update instructions
refactor(plans): Standardize to Template 1
```

### Worktree and PR Discipline

**One PR per Issue:**

- Each GitHub issue should have exactly ONE pull request
- Do not combine multiple issues into a single PR
- Branch naming: `<issue-number>-<description>`

**Worktree Directory:**

- Create all worktrees in the `worktrees/` subdirectory within the repo
- Naming convention: `<issue-number>-<description>`
- Example: `git worktree add worktrees/123-fix-bug 123-fix-bug`

**Post-Merge Cleanup:**

After a PR is merged/rebased to main:

1. Remove the worktree: `git worktree remove worktrees/<issue-number>-<description>`
2. Delete local branch: `git branch -d <branch-name>`
3. Delete remote branch: `git push origin --delete <branch-name>`
4. Prune stale references: `git worktree prune`

## Labels

Standard labels automatically created by scripts:

- `planning` - Design phase (light purple: #d4c5f9)
- `documentation` - Documentation work (blue: #0075ca)
- `testing` - Testing phase (yellow: #fbca04)
- `tdd` - Test-driven development (yellow: #fbca04)
- `implementation` - Implementation phase (dark blue: #1d76db)
- `packaging` - Integration/packaging (light green: #c2e0c6)
- `integration` - Integration tasks (light green: #c2e0c6)
- `cleanup` - Cleanup/finalization (red: #d93f0b)

## Python Coding Standards

```python

#!/usr/bin/env python3

"""
Script description

Usage:
    python scripts/script_name.py [options]
"""

# Standard imports first

import sys
import re
from pathlib import Path
from typing import List, Dict, Optional

def function_name(param: str) -> bool:
    """Clear docstring with purpose, params, returns."""
    pass
```

### Requirements

- Python 3.7+
- Type hints required for all functions
- Clear docstrings for public functions
- Comprehensive error handling
- Logging for important operations

## Markdown Standards

All markdown files must follow these standards to pass `markdownlint-cli2` linting:

### Code Blocks (MD031, MD040)

**Rule**: Fenced code blocks must be:

1. Surrounded by blank lines (before and after)
1. Have a language specified on the opening backticks
1. Don't put anything on the closing backticks

### Language Examples

- Python: ` ```python `
- Bash: ` ```bash `
- Text/plain: ` ```text `
- Mojo: ` ```mojo `
- YAML: ` ```yaml `
- JSON: ` ```json `
- Markdown: ` ```markdown `

### Lists (MD032)

**Rule**: Lists must be surrounded by blank lines (before and after)

### Correct

```markdown
Some text before.

- Item 1
- Item 2
- Item 3

Some text after.
```

### Incorrect

```markdown
Some text before.
- Item 1
- Item 2
Some text after.
```

### Headings (MD022)

**Rule**: Headings must be surrounded by blank lines (one blank line before and after)

### Correct

```markdown
Some content here.

## Section Heading

More content here.
```

### Incorrect

```markdown
Some content here.
## Section Heading
More content here.
```

### Line Length (MD013)

**Rule**: Lines should not exceed 120 characters

### Guidelines

- Break long lines at 120 characters
- Break at natural boundaries (clauses, lists, etc.)
- Code in code blocks is exempt
- URLs in links are exempt

### Example

```markdown
This is a very long sentence that exceeds the 120 character limit
and should be broken into multiple lines at a natural boundary point
for better readability.
```

### Best Practices

1. **Always add blank lines around code blocks and lists** - This is the #1 cause of linting failures
1. **Always specify language for code blocks** - Use appropriate language tags
1. **Check headings have surrounding blank lines** - Especially after subheadings
1. **Use reference-style links for long URLs** - Helps avoid line length issues

### Quick Checklist for New Content

Before committing markdown files:

- [ ] All code blocks have a language specified (` ```python ` not ` ``` `)
- [ ] All code blocks have blank lines before and after
- [ ] All lists have blank lines before and after
- [ ] All headings have blank lines before and after
- [ ] No lines exceed 120 characters
- [ ] File ends with newline (enforced by pre-commit)
- [ ] No trailing whitespace (enforced by pre-commit)

### Running Markdown Linting Locally

```bash
# Check specific file
pixi run npx markdownlint-cli2 path/to/file.md

# Check all markdown files
zust pre-commit-all

# View detailed errors
pixi run npx markdownlint-cli2 path/to/file.md 2>&1
```

## Debugging

### Check Logs

```bash
# View script logs
tail -100 logs/*.log

# View specific log
cat logs/<script>_*.log
```

## Troubleshooting

### GitHub CLI Issues

```bash
# Check authentication
gh auth status

# If missing scopes, refresh authentication
gh auth refresh -h github.com
```

### Issue Access Problems

- Check GitHub CLI auth: `gh auth status`
- Verify repository access: `gh repo view`
- Test issue access: `gh issue list`

### Script Errors

- Verify Python version: `python3 --version` (requires 3.7+)
- Check file permissions
- Review error logs in `logs/` directory

## Important Files

- `.clinerules` - Comprehensive Claude Code conventions
- `docs/dev/` - Developer documentation (Mojo patterns, skills architecture)
- `scripts/README.md` - Complete scripts documentation
- `README.md` - Main project documentation
- `.claude/shared/github-issue-workflow.md` - GitHub issue read/write patterns
