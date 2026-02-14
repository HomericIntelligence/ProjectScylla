# Judge Evaluation Context

Judge prompts are generated dynamically per run using:

- **System Prompt**: `config/judge/system_prompt.md` (via --system-prompt-file)
- **Task Prompt**: Generated via `scylla.judge.prompts.build_task_prompt()`

## Task Prompt References

- Agent Task: `/home/mvillmow/fullruns/test001-dryrun/2026-01-20T06-13-07-test-001/prompt.md`
- Success Criteria: `/home/mvillmow/fullruns/test001-dryrun/2026-01-20T06-13-07-test-001/criteria.md`
- Rubric: `/home/mvillmow/fullruns/test001-dryrun/2026-01-20T06-13-07-test-001/rubric.yaml`

## Per-Run Context (Generated Dynamically)

- Agent Output: `<run_dir>/output.txt`
- Workspace: `<subtest_dir>/workspace/`
- Patchfile: Git diff of workspace changes
- Pipeline Results: Build/lint/test output
