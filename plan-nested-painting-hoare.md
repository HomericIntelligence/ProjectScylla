# E2E Testing Framework Enhancements

## Summary

Four enhancements to ProjectScylla's E2E testing framework:

1. **Named Branch Worktrees** - Replace `--detach` with named branches (`T0_01`, `T1_05` format)
2. **Timestamped Phase Logging** - Add structured stdout logging for worktree/agent/judge phases
3. **Context-Aware Prompt Suffixes** - Append resource hints (skills, agents, MCP, tools) to prompts
4. **Report Formatting** - Bold/italicize best scores instead of separate "Best" column

---

## Files to Modify

| File | Changes |
|------|---------|
| `src/scylla/e2e/workspace_manager.py` | Add tier/subtest params, use `-b` instead of `--detach` |
| `src/scylla/e2e/subtest_executor.py` | Named branches, phase logging, save worktree script |
| `src/scylla/e2e/tier_manager.py` | Add `build_resource_suffix()` method |
| `src/scylla/e2e/run_report.py` | Remove "Best" column, bold/italic best entries |

---

## Feature 1: Named Branch Worktrees

### workspace_manager.py (lines 130-173)

**Current**:
```python
worktree_cmd = [
    "git", "-C", str(self.base_repo),
    "worktree", "add", "--detach",
    str(workspace_path),
]
```

**Change to**:
```python
def create_worktree(
    self,
    workspace_path: Path,
    tier_id: str | None = None,
    subtest_id: str | None = None,
) -> tuple[list[str], str]:
    """Create worktree with named branch."""
    # Generate branch name
    if tier_id and subtest_id:
        branch_name = f"{tier_id}_{subtest_id}"
    else:
        self._worktree_count += 1
        branch_name = f"worktree-{self._worktree_count}"

    worktree_cmd = [
        "git", "-C", str(self.base_repo),
        "worktree", "add", "-b", branch_name,
        str(workspace_path),
    ]
    # ...
    return worktree_cmd, branch_name
```

### subtest_executor.py (lines 507-555)

**Changes**:
1. Update `_setup_workspace()` signature to accept `tier_id` and `subtest_id`
2. Replace `--detach` with `-b {tier_id}_{subtest_id}`
3. Add clear error message for branch conflicts
4. Save worktree creation script to `T#/##/worktree_create.sh`:
```python
# Create worktree with named branch
worktree_cmd = [
    "git", "-C", str(self.workspace_manager.base_repo),
    "worktree", "add", "-b", branch_name,
    str(workspace_abs),
]

result = subprocess.run(worktree_cmd, capture_output=True, text=True, timeout=60)

if result.returncode != 0:
    if "already exists" in result.stderr:
        raise RuntimeError(
            f"Branch {branch_name} already exists. "
            f"Run `git branch -D {branch_name}` to delete it, "
            f"or clean up old worktrees with `git worktree prune`."
        )
    raise RuntimeError(f"Failed to create worktree: {result.stderr}")

# Save worktree creation command (create only, no cleanup)
subtest_dir = workspace.parent
worktree_script = subtest_dir / "worktree_create.sh"
worktree_script.write_text(
    f"#!/bin/bash\n# Worktree: {branch_name} @ {workspace_abs}\n"
    + " ".join(shlex.quote(arg) for arg in worktree_cmd) + "\n"
)
worktree_script.chmod(0o755)
```

---

## Feature 2: Timestamped Phase Logging

### Add helper in subtest_executor.py (after line 47):
```python
def _phase_log(phase: str, message: str) -> None:
    """Log phase message with timestamp and prefix."""
    from datetime import datetime, UTC
    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    logger.info(f"{timestamp} [{phase}] - {message}")
```

### Add logging calls:

**In `_setup_workspace()`**:
```python
_phase_log("WORKTREE", f"Creating worktree [{branch_name}] @ [{workspace_abs}]")
```

**In `_execute_single_run()` before agent execution (around line 392)**:
```python
_phase_log("AGENT", f"Running agent with model[{self.config.models[0]}] with prompt[{prompt_file}]")
```

**In `_run_judge()` before judge execution (around line 577)**:
```python
_phase_log("JUDGE", f"Running judge with model[{self.config.judge_model}] with prompt[{run_dir / 'judge_prompt.md'}]")
```

---

## Feature 3: Context-Aware Prompt Suffixes

### Add to tier_manager.py (after line 411):
```python
def build_resource_suffix(self, subtest: SubTestConfig) -> str:
    """Build prompt suffix based on configured resources.

    Uses bullet list format for resources:
    - skill1
    - skill2

    If no resources configured, returns generic hint.
    """
    suffixes = []
    resources = subtest.resources or {}
    has_any_resources = False

    # Sub-agents
    if "agents" in resources:
        agents_spec = resources["agents"]
        agent_names = []
        for level in agents_spec.get("levels", []):
            level_dir = self._get_shared_dir() / "agents" / f"L{level}"
            if level_dir.exists():
                for f in level_dir.glob("*.md"):
                    agent_names.append(f.stem)
        agent_names.extend(n.replace(".md", "") for n in agents_spec.get("names", []))
        if agent_names:
            has_any_resources = True
            bullet_list = "\n".join(f"- {name}" for name in sorted(set(agent_names)))
            suffixes.append(f"Use the following sub-agents to solve this task:\n{bullet_list}")

    # Skills
    if "skills" in resources:
        skills_spec = resources["skills"]
        skill_names = []
        for cat in skills_spec.get("categories", []):
            cat_dir = self._get_shared_dir() / "skills" / cat
            if cat_dir.exists():
                skill_names.extend(d.name for d in cat_dir.iterdir() if d.is_dir())
        skill_names.extend(skills_spec.get("names", []))
        if skill_names:
            has_any_resources = True
            bullet_list = "\n".join(f"- {name}" for name in sorted(set(skill_names)))
            suffixes.append(f"Use the following skills to complete this task:\n{bullet_list}")

    # MCP servers
    if "mcp_servers" in resources:
        mcp_names = [m.get("name", m) if isinstance(m, dict) else m for m in resources["mcp_servers"]]
        if mcp_names:
            has_any_resources = True
            bullet_list = "\n".join(f"- {name}" for name in sorted(set(mcp_names)))
            suffixes.append(f"Use the following MCP servers to complete this task:\n{bullet_list}")

    # Tools
    if "tools" in resources:
        tool_names = resources["tools"].get("names", [])
        if tool_names:
            has_any_resources = True
            bullet_list = "\n".join(f"- {name}" for name in sorted(tool_names))
            suffixes.append(f"Use the following tools to complete this task:\n{bullet_list}")

    # If no resources configured, add generic hint
    if not has_any_resources:
        return "Complete this task using available tools and your best judgment."

    return "\n\n".join(suffixes)
```

### Update _discover_subtests() (around line 138):
```python
# Also capture mcp_servers into resources for prompt suffixes
mcp_servers = config_data.get("mcp_servers", [])
if mcp_servers:
    resources["mcp_servers"] = mcp_servers
```

### Inject suffix in _execute_single_run() (around line 376):
```python
# Build context-aware resource suffix
resource_suffix = self.tier_manager.build_resource_suffix(subtest)
if resource_suffix:
    task_prompt = f"{task_prompt}\n\n{resource_suffix}"
```

---

## Feature 4: Report Formatting - Bold/Italic Best Scores

### Update run_report.py (lines 508-550, 684-728, 874-918)

**Replace "Best" column pattern with inline bold/italic**:

```python
# Build header WITHOUT "Best" column
header = "| Criterion |"
separator = "|-----------|"
for run in result.runs:
    header += f" Run {run.run_number:02d} |"
    separator += "--------|"
md_lines.extend([header, separator])

# Add rows with best values bolded/italicized
for criterion in sorted(all_criteria):
    row = f"| {criterion} |"
    scores = []
    score_cells = []

    for run in result.runs:
        if run.criteria_scores and criterion in run.criteria_scores:
            score_data = run.criteria_scores[criterion]
            score = score_data.get("score") if isinstance(score_data, dict) else score_data
            if isinstance(score, (int, float)):
                scores.append((score, len(score_cells)))
                score_cells.append(f"{score:.2f}")
            else:
                score_cells.append(f"{score}" if score else "-")
        else:
            score_cells.append("-")

    # Bold/italicize best scores (***text*** = bold+italic)
    if scores:
        max_score = max(s[0] for s in scores)
        best_indices = {s[1] for s in scores if s[0] == max_score}
        for idx, cell in enumerate(score_cells):
            if idx in best_indices and cell != "-":
                row += f" ***{cell}*** |"
            else:
                row += f" {cell} |"
    else:
        row += "".join(f" {cell} |" for cell in score_cells)

    md_lines.append(row)
```

Apply same pattern to:
- `save_subtest_report()` (lines 508-550)
- `save_tier_report()` (lines 684-728)
- `save_experiment_report()` (lines 874-918)

---

## Implementation Order

1. **Phase 1**: Named Branch Worktrees
   - Modify `workspace_manager.py` (independent)
   - Update `subtest_executor.py` for tier/subtest IDs
   - Add worktree script saving

2. **Phase 2**: Timestamped Logging (parallel with Phase 1)
   - Add `_phase_log()` helper
   - Add logging calls in subtest_executor.py

3. **Phase 3**: Context-Aware Prompt Suffixes (after Phase 1)
   - Add `build_resource_suffix()` to tier_manager.py
   - Update `_discover_subtests()` for mcp_servers
   - Inject suffix in `_execute_single_run()`

4. **Phase 4**: Report Formatting (independent)
   - Update all three report functions in run_report.py

---

## Edge Cases (User Decisions)

1. **Branch conflicts**: If branch `T0_01` already exists, **fail with clear error message** requiring manual cleanup of old branches. Add helpful error message: "Branch T0_01 already exists. Run `git branch -D T0_01` to delete it, or clean up old worktrees with `git worktree prune`."

2. **Empty resources**: When no resources configured, add **generic hint**: "Complete this task using available tools and your best judgment."

3. **Resource list format**: Use **bullet list** format:
   ```
   Use the following skills to complete this task:
   - skill1
   - skill2
   - skill3
   ```

4. **Worktree script**: **Create only** - just the worktree add command, no cleanup commands.

5. **MCP servers outside resources**: Config has `mcp_servers` at top level - merged into resources during discovery.

6. **Score ties**: All tied entries get bold/italic formatting.
