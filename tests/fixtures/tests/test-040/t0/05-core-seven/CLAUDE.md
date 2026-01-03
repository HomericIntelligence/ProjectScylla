## ⚠️ CRITICAL RULES - READ FIRST

### 🚫 NEVER Push Directly to Main

**The `main` branch is protected. ALL changes MUST go through a pull request.**

❌ **ABSOLUTELY PROHIBITED:**

```bash
git checkout main
git add <files>
git commit -m "changes"
git push origin main  # ❌ BLOCKED - Will be rejected by GitHub
```

**Why this is prohibited:**

- Bypasses code review and CI checks
- Can break production immediately
- Violates GitHub branch protection rules
- Makes it impossible to track changes properly

✅ **CORRECT WORKFLOW (Always Use PRs):**

```bash
# 1. Create feature branch
git checkout -b <issue-number>-description

# 2. Make changes and commit
git add <files>
git commit -m "type(scope): description"

# 3. Push feature branch
git push -u origin <issue-number>-description

# 4. Create pull request
gh pr create \
  --title "Brief description" \
  --body "Closes #<issue-number>" \
  --label "appropriate-label"

# 5. Enable auto-merge
gh pr merge --auto --rebase
```

**Emergency Situations:**

- Even for critical CI fixes, CREATE A PR
- Even for one-line changes, CREATE A PR
- Even if you're fixing your own mistake, CREATE A PR
- NO EXCEPTIONS - Always use the PR workflow

**See Also:**

- PR Best Practices: [PR Workflow](/.claude/shared/pr-workflow.md)
### Skill Delegation Patterns

Agents delegate to skills for automation using five standard patterns:

**Pattern 1: Direct Delegation** - Agent needs specific automation

```markdown
Use the `skill-name` skill to [action]:
- **Invoke when**: [trigger condition]
- **The skill handles**: [specific automation]
```

**Pattern 2: Conditional Delegation** - Agent decides based on conditions

```markdown
If [condition]:
  - Use the `skill-name` skill to [action]
Otherwise:
  - [alternative approach]
```

**Pattern 3: Multi-Skill Workflow** - Agent orchestrates multiple skills

```markdown
To accomplish [goal]:
1. Use the `skill-1` skill to [step 1]
2. Use the `skill-2` skill to [step 2]
3. Review results and [decision]
```

**Pattern 4: Skill Selection** - Orchestrator chooses skill based on analysis

```markdown
Analyze [context]:
- If [scenario A]: Use `skill-A`
- If [scenario B]: Use `skill-B`
```

**Pattern 5: Background vs Foreground** - Distinguishing automatic vs explicit invocation

```markdown
Background automation: `run-precommit` (runs automatically)
Foreground tasks: `gh-create-pr-linked` (invoke explicitly)
```

**Available Skills** (82 total across 11 categories):

- **GitHub**: gh-review-pr, gh-fix-pr-feedback, gh-create-pr-linked, gh-check-ci-status,
  gh-implement-issue, gh-reply-review-comment, gh-get-review-comments, gh-batch-merge-by-labels,
  verify-pr-ready
- **Worktree**: worktree-create, worktree-cleanup, worktree-switch, worktree-sync
- **Phase Workflow**: phase-plan-generate, phase-test-tdd, phase-implement, phase-package,
  phase-cleanup
- **Mojo**: mojo-format, mojo-test-runner, mojo-build-package, mojo-simd-optimize,
  mojo-memory-check, mojo-type-safety, mojo-lint-syntax, validate-mojo-patterns,
  check-memory-safety, analyze-simd-usage
- **Agent System**: agent-validate-config, agent-test-delegation, agent-run-orchestrator,
  agent-coverage-check, agent-hierarchy-diagram
- **Documentation**: doc-generate-adr, doc-issue-readme, doc-validate-markdown,
  doc-update-blog
- **CI/CD**: run-precommit, validate-workflow, fix-ci-failures, install-workflow,
  analyze-ci-failure-logs, build-run-local
- **Plan**: plan-regenerate-issues, plan-validate-structure, plan-create-component
- **Quality**: quality-run-linters, quality-fix-formatting, quality-security-scan,
  quality-coverage-report, quality-complexity-check
- **Testing & Analysis**: test-diff-analyzer, extract-test-failures, generate-fix-suggestions,
  track-implementation-progress
- **Review**: review-pr-changes, create-review-checklist

### Language Preference

#### Mojo First - With Pragmatic Exceptions

**Default to Mojo** for ALL ML/AI implementations:

- ✅ Neural network implementations (forward/backward passes, layers)
- ✅ Training loops and optimization algorithms
- ✅ Tensor operations and SIMD kernels
- ✅ Performance-critical data processing
- ✅ Type-safe model components
- ✅ Gradient computation and backpropagation
- ✅ Model inference engines

**Use Python for Automation** when technical limitations require it:

- ✅ Subprocess output capture (Mojo v0.26.1 limitation - cannot capture stdout/stderr)
- ✅ Regex-heavy text processing (no Mojo regex support in stdlib)
- ✅ GitHub API interaction via Python libraries (`gh` CLI, REST API)
- ⚠️ **MUST document justification** (see ADR-001 for header template)

**Rule of Thumb** (Decision Tree):

1. **ML/AI implementation?** → Mojo (required)
1. **Automation needing subprocess output?** → Python (allowed, document why)
1. **Automation needing regex?** → Python (allowed, document why)
1. **Interface with Python-only libraries?** → Python (allowed, document why)
1. **Everything else?** → Mojo (default)

### Why Mojo for ML/AI

- Performance: Faster for ML workloads
- Type safety: Catch errors at compile time
- Memory safety: Built-in ownership and borrow checking
- SIMD optimization: Parallel tensor operations
- Future-proof: Designed for AI/ML from the ground up

### Why Python for Automation

- Mojo's subprocess API lacks exit code access (causes silent failures)
- Regex support not production-ready (mojo-regex is alpha stage)
- Python is the right tool for automation - not a temporary workaround

**See**: [ADR-001: Language Selection for Tooling](docs/adr/ADR-001-language-selection-tooling.md)
for complete language selection strategy, technical evidence (test results), and justification
requirements

See `/agents/README.md` for complete agent documentation and `/agents/hierarchy.md` for visual hierarchy.
### Agent Skills vs Sub-Agents

**Decision Tree**: Choose between skills and sub-agents based on task characteristics:

```text
Is the task well-defined with predictable steps?
├─ YES → Use an Agent Skill
│   ├─ Is it a GitHub operation? → Use gh-* skills
│   ├─ Is it a Mojo operation? → Use mojo-* skills
│   ├─ Is it a CI/CD task? → Use ci-* skills
│   └─ Is it a documentation task? → Use doc-* skills
│
└─ NO → Use a Sub-Agent
    ├─ Does it require exploration/discovery? → Use sub-agent
    ├─ Does it need adaptive decision-making? → Use sub-agent
    ├─ Is the workflow dynamic/context-dependent? → Use sub-agent
    └─ Does it need extended thinking? → Use sub-agent
```

**Agent Skills** - Use for automation with predictable workflows:

- **Characteristics**: Declarative YAML, fixed steps, composable, fast
- **Best for**: GitHub API calls, running tests, formatting code, CI workflows
- **Examples**: `gh-create-pr-linked`, `mojo-format`, `run-precommit`

**Sub-Agents** - Use for tasks requiring reasoning and adaptation:

- **Characteristics**: Full Claude instance, extended thinking, exploratory, slower
- **Best for**: Architecture decisions, debugging, code review, complex refactoring
- **Examples**: Documentation Engineer, Implementation Specialist, Review Engineer

**Example - When to Use a Skill**:

```markdown
Task: Create PR linked to issue #2549, run pixi run pre-commit hooks, enable auto-merge

✅ Use Agent Skills:
1. Use `gh-create-pr-linked` skill (predictable GitHub API workflow)
2. Use `run-precommit` skill (fixed command sequence)
3. Use `gh-check-ci-status` skill (polling with clear success/failure states)

Why skills work: Every step is well-defined, no exploration needed
```

**Example - When to Use a Sub-Agent**:

```markdown
Task: Review PR #2549 and suggest improvements to new Claude 4 documentation

✅ Use Sub-Agent (Review Engineer):
- Needs to read and understand the new documentation
- Compare against Claude's official documentation
- Evaluate clarity, completeness, and accuracy
- Provide actionable feedback with examples

Why sub-agent needed: Requires comprehension, judgment, adaptive reasoning
```

**Hybrid Approach** - Sub-agents can delegate to skills:

```markdown
Sub-Agent: Documentation Engineer implementing issue #2549

Workflow:
1. [Sub-agent] Read Claude 4 docs, analyze requirements, draft section
2. [Sub-agent] Use `doc-validate-markdown` skill to check formatting
3. [Sub-agent] Use `gh-create-pr-linked` skill to create PR
4. [Sub-agent] Use `ci-check-status` skill to verify CI passes
```
### Tool Use Optimization

Efficient tool use reduces latency and token consumption. Follow these patterns:

#### Parallel Tool Calls

**DO**: Make independent tool calls in parallel:

```python
# ✅ GOOD - Parallel reads
read_file_1 = Read("/path/to/file1.mojo")
read_file_2 = Read("/path/to/file2.mojo")
read_file_3 = Read("/path/to/file3.mojo")
# All three reads happen concurrently

# ❌ BAD - Sequential reads
read_file_1 = Read("/path/to/file1.mojo")
# Wait for result...
read_file_2 = Read("/path/to/file2.mojo")
# Wait for result...
read_file_3 = Read("/path/to/file3.mojo")
```

**DO**: Group related grep searches:

```python
# ✅ GOOD - Parallel greps
grep_functions = Grep(pattern="fn .*", glob="*.mojo")
grep_structs = Grep(pattern="struct .*", glob="*.mojo")
grep_tests = Grep(pattern="test_.*", glob="test_*.mojo")
# All searches run in parallel

# ❌ BAD - Sequential greps with waiting
grep_functions = Grep(pattern="fn .*", glob="*.mojo")
# Process results, then...
grep_structs = Grep(pattern="struct .*", glob="*.mojo")
```

#### Bash Command Patterns

**DO**: Use absolute paths in bash commands (cwd resets between calls):

```bash
# ✅ GOOD - Absolute paths
cd /home/user/ProjectOdyssey && pixi run mojo test tests/shared/core/test_tensor.mojo

# ❌ BAD - Relative paths (cwd not guaranteed)
cd ProjectOdyssey && pixi run mojo test tests/shared/core/test_tensor.mojo
```

**DO**: Combine related commands with && for atomicity:

```bash
# ✅ GOOD - Atomic operation
cd /home/user/ProjectOdyssey && \
  git checkout -b 2549-claude-md && \
  git add CLAUDE.md && \
  git commit -m "docs: add Claude 4 optimization guidance"

# ❌ BAD - Multiple separate bash calls (cwd resets)
cd /home/user/ProjectOdyssey
git checkout -b 2549-claude-md  # Might run in different directory!
git add CLAUDE.md
```

**DO**: Capture output explicitly when needed:

```bash
# ✅ GOOD - Capture and parse output
cd /home/user/ProjectOdyssey && \
  pixi run mojo test tests/ 2>&1 | tee test_output.log && \
  grep -c PASSED test_output.log

# ❌ BAD - Output lost between calls
cd /home/user/ProjectOdyssey && pixi run mojo test tests/
# Output is gone, can't analyze it
```

#### Tool Selection

Use the right tool for the job:

| Task | Tool | Rationale |
|------|------|-----------|
| Read file | Read | Fast, includes lines |
| Search pattern | Grep | Optimized regex |
| Find files | Glob | Fast discovery |
| Run commands | Bash | Execute shell |
| Edit lines | Edit | Precise replace |
| Write file | Write | Create/overwrite |

**DO**: Use the most specific tool:

```python
# ✅ GOOD - Use Glob to find files, then Read them
files = Glob(pattern="**/test_*.mojo")
for file in files:
    content = Read(file)

# ❌ BAD - Use Bash for file discovery
result = Bash("find . -name 'test_*.mojo'")
# Now have to parse shell output
```
## Repository Architecture

### Project Structure

```text
ProjectOdyssey/
├── agents/                      # Team documentation
│   ├── README.md                # Quick start guide
│   ├── hierarchy.md             # Visual hierarchy diagram
│   ├── agent-hierarchy.md       # Agent specifications
│   ├── delegation-rules.md      # Coordination patterns
│   └── templates/               # Agent configuration templates
├── notes/
│   └── review/                  # Comprehensive specs & decisions
│       ├── agent-architecture-review.md
│       ├── skills-design.md
│       └── orchestration-patterns.md
├── scripts/                     # Python automation scripts
├── logs/                        # Execution logs and state files
└── .clinerules                 # Claude Code conventions
```

### Planning Hierarchy

**4 Levels** (managed through GitHub issues):

1. **Section** (e.g., 01-foundation) - Major area of work
1. **Subsection** (e.g., 01-directory-structure) - Logical grouping
1. **Component** (e.g., 01-create-papers-dir) - Specific deliverable
1. **Subcomponent** (e.g., 01-create-base-dir) - Atomic task

All planning documentation is tracked in GitHub issues. Use `gh issue view <number>` to read plans.

### Documentation Organization

The repository uses three separate locations for documentation to avoid duplication:

#### 1. Team Documentation (`/agents/`)

**Purpose**: Quick start guides, visual references, and templates for team onboarding.

### Contents

- Quick start guides (README.md)
- Visual diagrams (hierarchy.md)
- Quick reference cards (delegation-rules.md)
- Configuration templates (templates/)

**When to Use**: Creating new documentation for team onboarding or quick reference.

#### 2. Developer Documentation (`/docs/dev/`)

**Purpose**: Detailed architectural decisions, comprehensive specifications, and design documents.

### Contents

- Mojo patterns and error handling (mojo-test-failure-patterns.md)
- Skills architecture (skills-design.md, skills-architecture.md)
- Orchestration patterns (orchestration-patterns.md)
- Backward pass catalog (backward-pass-catalog.md)

**When to Use**: Writing detailed specifications, architectural decisions, or comprehensive guides.

#### 3. Issue-Specific Documentation (GitHub Issue Comments)

**Purpose**: Implementation notes, findings, and decisions specific to a single GitHub issue.

**Location**: Post directly to the GitHub issue as comments using `gh issue comment`.

**Reading Issue Context**:

```bash
# Get issue details and body
gh issue view <number>

# Get all comments (implementation history)
gh issue view <number> --comments

# Get structured data
gh issue view <number> --json title,body,comments,labels,state
```

**Writing to Issues**:

```bash
# Post implementation notes
gh issue comment <number> --body "$(cat <<'EOF'
## Implementation Notes

### Summary
[What was implemented]

### Files Changed
- path/to/file.mojo

### Verification
- [x] Tests pass
EOF
)"
```

### Important Rules

- ✅ DO: Post issue-specific findings and decisions as comments
- ✅ DO: Link to comprehensive docs in `/agents/` and `/docs/dev/`
- ✅ DO: Reference related issues with `#<number>` format
- ❌ DON'T: Duplicate comprehensive documentation
- ❌ DON'T: Create local files for issue tracking

### 5-Phase Development Workflow

Every component follows a hierarchical workflow with clear dependencies:

**Workflow**: Plan → [Test | Implementation | Package] → Cleanup

1. **Plan** - Design and documentation (MUST complete first)
1. **Test** - Write tests following TDD (parallel after Plan)
1. **Implementation** - Build the functionality (parallel after Plan)
1. **Package** - Create distributable packages (parallel after Plan)
   - Build binary packages (`.mojopkg` files for Mojo modules)
   - Create distribution archives (`.tar.gz`, `.zip` for tooling/docs)
   - Configure package metadata and installation procedures
   - Add components to existing packages
   - Test package installation in clean environments
   - Create CI/CD packaging workflows
   - **NOT just documenting** - must create actual distributable artifacts
1. **Cleanup** - Refactor and finalize (runs after parallel phases complete)

### Key Points

- Plan phase produces specifications for all other phases
- Test/Implementation/Package can run in parallel after Plan completes
- Cleanup collects issues discovered during the parallel phases
- Each phase has a separate GitHub issue with detailed instructions
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
