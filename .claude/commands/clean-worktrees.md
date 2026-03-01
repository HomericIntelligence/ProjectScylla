Scan all git worktrees and branches for stale/done entries and clean them up. Follow these steps precisely:

## Step 1: Enumerate worktrees

Run `git worktree list` and collect all non-main worktrees.

## Step 2: Classify each worktree

For each non-main worktree, determine its branch name and check status:

```bash
# Extract branch from worktree list output
git worktree list --porcelain
```

For each worktree branch:
- If the branch name matches `issue-<N>` or `<N>-*`: check `gh issue view <N> --json state` — if `state == "CLOSED"`, mark as DONE
- If the branch name matches an agent worktree pattern (e.g. `worktree-agent-*`): mark as DONE (these are always stale)
- Check if a PR exists: `gh pr list --head <branch> --state merged --json number` — if any result, mark as DONE
- Otherwise: mark as NOT DONE (keep)

## Step 3: Print classification report

Print a table showing each worktree path, branch, status (DONE/KEEP), and reason.

## Step 4: Remove DONE worktrees

**Process nested worktrees first, then top-level.**

For each DONE worktree:
1. Check if dirty: `git -C <path> status --short`
2. If clean: `git worktree remove <path>`
3. If dirty but DONE (issue closed or PR merged): report it and ask user to confirm before using `--force`

## Step 5: Delete corresponding local branches

For each removed worktree's branch:
```bash
git branch -d <branch>  # prefer -d; only use -D if confirmed merged
```

For all local branches tracking `[gone]` remotes:
```bash
git branch -vv | grep ': gone]'
# For each: verify merged via gh pr list --head <branch> --state merged
# Then git branch -d <branch>
```

## Step 6: Delete stale remote branches

For each remote branch (excluding main) that has a closed issue or merged/closed PR:
```bash
# Use gh api to bypass local pre-push hooks:
gh api --method DELETE "repos/{owner}/{repo}/git/refs/heads/<branch>"
```

Get owner/repo from: `gh repo view --json nameWithOwner -q .nameWithOwner`

## Step 7: Prune

```bash
git worktree prune
git remote prune origin
```

## Step 8: Summary report

Print final counts:
- Worktrees removed
- Local branches deleted
- Remote branches deleted
- Worktrees kept (open issues)
