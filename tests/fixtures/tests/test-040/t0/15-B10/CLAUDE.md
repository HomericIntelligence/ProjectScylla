### Hooks Best Practices

Hooks enable proactive automation and safety checks. Use hooks for guardrails and background tasks.

**Safety Hooks** - Prevent errors before they happen:

```yaml
# Example: Prevent direct pushes to main branch
- trigger: "on_git_push"
  condition: "branch == 'main' && !is_pr"
  action: "block"
  message: "Direct pushes to main are not allowed. Create a PR instead."

# Example: Enforce zero-warnings policy
- trigger: "on_mojo_compile"
  condition: "warnings_count > 0"
  action: "fail"
  message: "Mojo code must compile without warnings. Fix warnings before committing."

# Example: Require issue link in PR description
- trigger: "on_pr_create"
  condition: "!body.includes('Closes #')"
  action: "block"
  message: "PR must reference an issue: add 'Closes #<number>' to description."
```

**Automation Hooks** - Background tasks that run automatically:

```yaml
# Example: Auto-format Mojo code on save
- trigger: "on_file_save"
  condition: "file.endsWith('.mojo')"
  action: "run_skill"
  skill: "mojo-format"

# Example: Run pixi run pre-commit hooks before commit
- trigger: "on_git_commit"
  action: "run_skill"
  skill: "run-precommit"

# Example: Auto-assign reviewers based on changed files
- trigger: "on_pr_create"
  condition: "changed_files.includes('shared/core/')"
  action: "add_reviewers"
  reviewers: ["core-team"]
```

**Hook Design Principles**:

1. **Fail fast** - Catch errors early in the development cycle
2. **Clear messages** - Explain WHY the hook triggered and HOW to fix
3. **Strict enforcement** - NEVER use `--no-verify`. Fix hook failures instead of bypassing.
4. **Idempotent** - Hooks should be safe to run multiple times

**Common Hooks for ML Odyssey**:

| Hook Type | Trigger | Purpose | Implementation |
|-----------|---------|---------|----------------|
| **Safety** | compile | Zero-warnings | Fail on warnings |
| **Safety** | pr_create | Issue link | Block if missing |
| **Safety** | git_push | Block main | Fail if direct |
| **Automation** | file_save | Auto-format | Run pixi run mojo format |
| **Automation** | git_commit | Pre-commit | Execute hooks |
| **Automation** | pr_merge | Cleanup | Remove worktree |

See `.claude/shared/error-handling.md` for retry strategies and timeout handling in hooks.
