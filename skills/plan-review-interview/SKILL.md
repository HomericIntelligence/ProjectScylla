# Plan Review Interview Skill

## Overview

| Field | Value |
|-------|-------|
| **Date** | 2025-12-30 |
| **Objective** | Review implementation plan, identify gaps, interview stakeholder for decisions |
| **Outcome** | SUCCESS - 11 key decisions captured, 4 new issues created, 6 existing issues updated |
| **Context** | ProjectScylla agent testing framework planning phase |

## When to Use

Use this skill when:

- You have a draft implementation plan that needs stakeholder validation
- There are ambiguous requirements or multiple valid approaches
- GitHub issues exist but lack key decision details
- You need to systematically identify gaps before implementation begins
- You want to document decisions alongside the issues they affect

## Verified Workflow

### Phase 1: Prepare Context Files

1. Read all existing plan documents
2. List all GitHub issues with `gh issue list --limit 50`
3. Group issues by phase/category
4. Create a review prompt document with:
   - Links to context files
   - Issue numbers organized by phase
   - Categorized clarifying questions
   - Reference issue numbers for each question category

### Phase 2: Conduct Structured Interview

1. **Batch questions by topic** (3-4 questions per batch)
   - Core execution model
   - Tier/configuration specifics
   - Judge/evaluation system
   - Scope and audience

2. **For each question**:
   - State the gap clearly
   - Reference affected GitHub issues
   - Propose 2-3 solutions
   - Record user's decision

3. **Use AskUserQuestion tool** with multiple related questions per batch

### Phase 3: Update Artifacts

1. **Update plan document** with decisions table at top
2. **Add comments to GitHub issues** with relevant decisions:
   ```bash
   gh issue comment <number> --body "## Decision Update\n\n- Key decision: ..."
   ```
3. **Create new issues** for gaps discovered during interview:
   ```bash
   gh issue create --title "[Category] Title" --body "..." --label "category"
   ```
4. **Transform review prompt** into decisions document (update status, add decisions summary)

### Phase 4: Commit and Document

1. Create feature branch: `git checkout -b skill/<category>/<name>`
2. Commit all updated files
3. Create PR with summary of decisions made

## Key Patterns

### Decision Table Format

```markdown
## Decisions Summary

| Question | Decision |
|----------|----------|
| API Key Handling | Environment Variables (docker -e flags) |
| Runs per Tier | **9 runs** (standardized) |
| Docker Fallback | **Fail with error** (Docker is required) |
```

### Issue Reference Pattern

```markdown
### 1. Test Execution Model

**Reference Issues**: #7, #8, #9, #35

| Question | Decision |
|----------|----------|
| How are API keys passed? | **Environment variables** via docker -e flags |
```

### Batched Interview Questions

Group related questions to avoid overwhelming the user:

```
Batch 1: Core Execution (API keys, Docker, runs per tier)
Batch 2: Tier System (T0 definition, tier relationships)
Batch 3: Judge System (location, disagreement handling)
Batch 4: Scope (audience, first test scope)
```

## Failed Attempts

### 1. Asking All Questions at Once

**What happened**: Initially tried to present all 30+ questions in one prompt.

**Why it failed**: Overwhelming for the user; decisions weren't properly linked to issues.

**Solution**: Batch questions by topic (3-4 per batch), reference specific issue numbers.

### 2. Updating Issues Without Comments

**What happened**: Tried to use `gh issue edit --body` to update issue descriptions directly.

**Why it failed**: Lost original issue context; hard to track what changed.

**Solution**: Use `gh issue comment` to add decision updates as comments, preserving history.

### 3. Generic Review Prompt

**What happened**: First review prompt didn't reference specific GitHub issue numbers.

**Why it failed**: Hard to trace which decisions affected which implementation tasks.

**Solution**: Organize questions by phase with explicit issue references (e.g., "Reference Issues: #7, #8, #9").

## Results & Parameters

### Session Statistics

| Metric | Value |
|--------|-------|
| Questions asked | 11 batched topics |
| Decisions captured | 11 key decisions |
| Issues updated | 6 (#4, #8, #11, #18, #35, #36) |
| New issues created | 4 (#40, #41, #42, #43) |
| Documents updated | 2 (plan.md, clarifying_prompt.md) |

### Key Decisions Made

| Decision | Choice | Rationale |
|----------|--------|-----------|
| API Key Handling | Environment variables | Security via docker -e flags |
| Runs per Tier | 9 runs | Statistical validity |
| Test Focus | Tiers AND models | Cross-model comparison |
| T0 Baseline | Tool defaults | Clean baseline without prompt injection |
| Judge Location | Separate container | Isolation from agent |
| Tier Prompts | Independent | Self-contained, easier to maintain |
| Docker Fallback | Fail with error | Docker is required infrastructure |
| Timeout Handling | Include as failures | Don't hide failures in statistics |
| Report Audience | Researchers/Engineers | Detailed technical analysis |
| Judge Disagreement | Retry with passes | Consensus through iteration |
| First Test Scope | Claude Code only | Incremental adapter development |

### Files Produced

```
docs/plan.md                  # Updated with decisions table
docs/clarifying_prompt.md     # Transformed to decisions document
```

## Commands Reference

```bash
# Read issue with comments
gh issue view <number> --comments

# Add decision comment to issue
gh issue comment <number> --body "## Decision Update

- **Key decision**: value
- **Rationale**: reason
- **Affects**: list of components"

# Create new issue for discovered gap
gh issue create \
  --title "[Category] Brief description" \
  --body "## Objective\n\n..." \
  --label "category"

# List all issues for review
gh issue list --limit 50 --state all
```

## Related Skills

- `/advise` - Search team knowledge before starting
- `/commit` - Commit changes with proper format
- `/review-pr` - Review pull request changes
