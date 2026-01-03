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

