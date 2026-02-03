# GitHub Issue Workflow

This document defines the standard workflow for reading from and writing to GitHub issues.
All agents should follow these patterns for issue-based documentation.

## Reading from GitHub Issues

### Get Issue Details

```bash
# Get issue description and metadata
gh issue view <number>

# Get issue with all comments (implementation history)
gh issue view <number> --comments

# Get structured JSON for parsing
gh issue view <number> --json title,body,comments,labels,assignees,milestone,state

# Get specific fields only
gh issue view <number> --json body --jq '.body'
```

### Check Related Items

```bash
# Get linked PRs
gh pr list --search "issue:<number>"

# Get issue timeline (events, references)
gh api repos/{owner}/{repo}/issues/<number>/timeline

# Search for related issues
gh issue list --search "in:body #<number>"
```

### Before Starting Work

1. Run `gh issue view <number>` to understand requirements
2. Run `gh issue view <number> --comments` for prior context and decisions
3. Check linked PRs: `gh pr list --search "issue:<number>"`
4. Note any blockers or dependencies mentioned in comments

## Writing to GitHub Issues

### Status Updates

```bash
# Short status update
gh issue comment <number> --body "Status: Evaluation in progress - 3/5 tiers complete"

# Progress checkpoint
gh issue comment <number> --body "Checkpoint: Completed T0-T2 benchmarks, starting T3 evaluation"
```

### Evaluation Results

```bash
gh issue comment <number> --body "$(cat <<'EOF'
## Evaluation Results

### Summary
Completed tier comparison study for Task-X across T0-T3.

### Results

| Tier | Pass-Rate | CoP ($) | Latency (s) | n |
|------|-----------|---------|-------------|---|
| T0   | 0.23      | 4.35    | 12.3        | 50 |
| T1   | 0.45      | 2.22    | 15.7        | 50 |
| T2   | 0.67      | 1.49    | 18.2        | 50 |
| T3   | 0.78      | 1.28    | 22.1        | 50 |

### Statistical Significance
- T1 vs T0: p < 0.001 (significant)
- T2 vs T1: p < 0.01 (significant)
- T3 vs T2: p = 0.08 (not significant at alpha=0.05)

### Key Findings
1. Diminishing returns observed beyond T2
2. T3 adds latency without proportional quality gain
3. Recommended tier for this task: T2 (best CoP)

### Next Steps
- Extend evaluation to T4-T6
- Increase sample size for marginal comparisons
EOF
)"
```

### Implementation Complete

```bash
gh issue comment <number> --body "$(cat <<'EOF'
## Implementation Complete

**PR**: #<pr-number>

### Summary
[Brief description of what was implemented]

### Files Changed
- `scylla/metrics/cop.py` - Cost-of-Pass calculation
- `tests/test_cop.py` - Unit tests

### Testing
- All tests pass
- Coverage: 95%

### Verification
- [x] `pytest tests/` passes
- [x] `ruff check .` passes
- [x] Manual validation complete
EOF
)"
```

## Referencing Issues

### In Commits

```bash
# Reference issue in commit message
git commit -m "feat(metrics): Add Cost-of-Pass calculation

Implements CoP metric as total_cost / pass_rate.

Refs #123"

# Close issue via commit
git commit -m "fix(evaluation): Correct token counting

Closes #456"
```

### In Pull Requests

```bash
# Create PR linked to issue
gh pr create --title "feat: Add Cost-of-Pass metric" --body "Closes #123"

# Reference multiple issues
gh pr create --title "feat: Add tier comparison" --body "
## Summary
Added T0-T3 comparison framework.

Closes #123
Refs #124, #125
"
```

### In Documentation

```markdown
For methodology details, see [Issue #123](https://github.com/owner/repo/issues/123).

Related issues:
- #124 - Metrics implementation
- #125 - Statistical analysis
```

## Templates

### New Evaluation

```markdown
## Evaluation Started

**Issue**: #<number>
**Branch**: `<branch-name>`

### Approach
[Brief description of evaluation methodology]

### Tiers to Evaluate
- [ ] T0 (Vanilla)
- [ ] T1 (Prompted)
- [ ] T2 (Skills)

### Metrics to Collect
- [ ] Pass-Rate
- [ ] Cost-of-Pass
- [ ] Latency

### Estimated Sample Size
- n=50 per tier
```

### Benchmark Results

```markdown
## Benchmark Complete

### Configuration
- Task: [Task name]
- Tiers: T0-T3
- Samples per tier: 50
- Date: YYYY-MM-DD

### Results
[Include table with results]

### Analysis
[Key findings and recommendations]
```

## Best Practices

1. **Be Concise**: Keep updates focused and actionable
2. **Use Tables**: Present benchmark results in tables
3. **Include Statistics**: Always report confidence intervals and p-values
4. **Link Related Items**: Reference other issues, PRs, and commits
5. **Update Regularly**: Post progress updates, don't wait until completion
6. **Document Methodology**: Future readers should understand how results were obtained
