# Plan Review Interview - Raw Session Notes

## Session Context

- **Project**: ProjectScylla - Agent testing framework
- **Date**: 2025-12-30
- **Preceding work**: Created Epic #2, Issues #3-38, initial plan documents

## Conversation Flow

### Initial State

- 38 GitHub issues existed (Epic #2, Issues #3-38)
- Plan documented in `docs/plan.md` and `.claude/plans/swift-skipping-creek.md`
- First test case defined in `tests/001-justfile-to-makefile/`
- Multiple open questions about execution model, tier system, judge behavior

### User Request

> "I don't want to begin with implementation, instead I want a prompt to do a thorough review and interview me for things that are not clear"

### Interview Batches Conducted

**Batch 1: Core Execution Model**
- How are API keys passed to containers? -> Environment variables
- What if Docker unavailable? -> Fail with error
- Container isolation model? -> Separate containers for agent and judge

**Batch 2: Configuration**
- Runs per tier? -> 9 runs (changed from 10)
- What does T0 (Vanilla) mean? -> Tool default behavior
- Are tiers cumulative? -> No, independent

**Batch 3: Judge System**
- Where does judge run? -> Separate container
- How handle disagreement? -> Run additional passes until consensus
- How access workspace? -> Read-only volume mount

**Batch 4: Scope**
- Report audience? -> Researchers/Engineers
- First test adapter scope? -> Claude Code only
- Test focus? -> Both tiers AND models

## GitHub Operations Performed

### Issues Updated with Comments

```bash
gh issue comment 4 --body "Decision: runs_per_tier=9, API keys via env vars"
gh issue comment 8 --body "Decision: 9 runs, test tiers+models, judge in separate container"
gh issue comment 11 --body "Decision: T0=tool defaults, tiers independent"
gh issue comment 18 --body "Decision: Judge in separate container, retry on disagreement"
gh issue comment 35 --body "Decision: Docker required, API keys via env vars"
gh issue comment 36 --body "Decision: Independent tiers, T0=tool defaults"
```

### New Issues Created

```bash
gh issue create --title "[Infra] Dockerfile specification for scylla-runner:latest" --label "infrastructure"
# Created #40

gh issue create --title "[Core] Judge container orchestration" --label "core"
# Created #41

gh issue create --title "[Config] Create tier prompt template files" --label "config"
# Created #42

gh issue create --title "[Core] Judge consensus with retry logic" --label "core"
# Created #43
```

## File Changes

### docs/plan.md

- Added decisions summary table at top
- Changed "10 runs" -> "9 runs" throughout
- Added "tiers AND models" testing scope
- Updated issue references (#23, #33 titles)

### docs/clarifying_prompt.md

Transformed from interview prompt to decisions document:
- Added "Status: COMPLETE"
- Added decisions summary table
- Converted questions to "Resolved Questions" with decisions
- Added "New Issues Created" section (#40-43)
- Added "Completed Actions" section

## Lessons Learned

1. **Batch questions by topic** - Don't overwhelm with 30+ questions at once
2. **Reference issue numbers** - Every question should link to affected issues
3. **Use comments not edits** - `gh issue comment` preserves history better than `gh issue edit`
4. **Transform prompts to docs** - Review prompts become decision documents
5. **Track new issues** - Gaps discovered during review become new issues

## Statistics

| Metric | Count |
|--------|-------|
| Total questions batches | 4 |
| Decisions captured | 11 |
| Existing issues updated | 6 |
| New issues created | 4 |
| Plan files updated | 2 |
| Lines added to docs | ~300 |

## Key Configuration Values

```yaml
# From decisions
runs_per_tier: 9
test_focus: "tiers_and_models"
t0_baseline: "tool_defaults"
tier_relationship: "independent"
docker_required: true
api_key_method: "environment_variables"
judge_container: "separate"
judge_disagreement: "retry_with_passes"
timeout_handling: "include_as_failures"
report_audience: "researchers_engineers"
first_test_adapter: "claude_code_only"
```

## Open Items (Still TBD)

From interview, explicitly deferred to implementation:
- Container resource limits (CPU, memory, disk)
- Internet access handling for containers
- CI/CD integration details
- Storage management strategy
- Visualization (charts/graphs vs tables only)
