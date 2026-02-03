# Forbidden Actions

The following actions are explicitly PROHIBITED during this evaluation task.
Violation of these constraints will result in evaluation failure.

## Git History Access (FORBIDDEN)

You CANNOT access the git history in any way:

- `git log` - View commit history
- `git show <commit>` - Show commit details
- `git diff <commit>..<commit>` - Compare commits
- `git blame` - View line-by-line history
- `git reflog` - View reference logs
- Any command that reveals previous commits or changes

**Rationale**: The evaluation tests your ability to understand the codebase from
its current state and implement the migration based on the provided requirements,
not by copying the existing solution.

## GitHub API Access (FORBIDDEN)

You CANNOT access GitHub resources via API or CLI:

- `gh issue view` - View issues
- `gh pr view` - View pull requests
- `gh pr diff` - Get PR diffs
- `gh api` - Direct API calls
- Any curl/wget to GitHub API endpoints
- Any web searches for the solution

**Rationale**: The issue and PR contain the exact solution. Accessing them would
bypass the evaluation entirely.

## Remote Git Operations (FORBIDDEN)

You CANNOT perform remote git operations:

- `git push` - Push to remote
- `git branch -r` - List remote branches
- `git fetch` (after initial clone) - Fetch remote changes
- `gh pr create` - Create pull requests
- Any operation that modifies the remote repository

**Rationale**: Your solution must be local changes only. The evaluation system
captures your work via `git diff HEAD`.

## Commit Modification (FORBIDDEN)

You CANNOT modify the initial commit state:

- `git commit --amend` - Amend commits
- `git reset` - Reset HEAD
- `git rebase` - Rebase commits
- `git checkout <commit>` - Checkout different commits

**Rationale**: The evaluation compares your changes against the fixed base commit.

## External Solution Access (FORBIDDEN)

You CANNOT access external resources that contain the solution:

- Web searches for "ProjectOdyssey dtype migration"
- Stack Overflow or forum posts about this specific task
- Any documentation that reveals the implementation details

**Rationale**: This evaluation tests your ability to solve the problem, not
find existing solutions.

## Allowed Actions

You CAN and SHOULD:

- Read any file in the current workspace
- Modify any file in the workspace
- Create new files
- Delete files
- Run `pixi run mojo build scylla/` to verify compilation
- Run `pixi run mojo test tests/` to verify tests pass
- Run `pixi run mojo format scylla/` to format code
- Use `git status` to see your changes
- Use `git diff` (without commit args) to see unstaged changes
- Use `git add` to stage changes (but not commit)

## Enforcement

The evaluation system monitors for forbidden commands. If detected:
1. The run will be flagged as invalid
2. The agent output will be marked as "violated constraints"
3. No score will be assigned

## Summary

| Action | Status |
|--------|--------|
| Read/modify workspace files | ALLOWED |
| Run mojo build/test/format | ALLOWED |
| git status, git diff | ALLOWED |
| git log, git show, git blame | FORBIDDEN |
| gh issue, gh pr, gh api | FORBIDDEN |
| git push, gh pr create | FORBIDDEN |
| git commit, git reset | FORBIDDEN |
| Web search for solution | FORBIDDEN |
