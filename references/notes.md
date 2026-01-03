# Prompt Ablation Framework - Raw Notes

## Session Details

- **Date**: 2024-12-30
- **Duration**: Extended session with context continuation
- **Model**: Claude Opus 4.5 (claude-opus-4-5-20251101)
- **Working Directory**: /home/mvillmow/ProjectOdysseyManual
- **Target Repository**: /tmp/ProjectScylla

## Initial Request

> "Use ultrathink and analyze CLAUDE.md, agents, sub-agents, skills, and the agent test plan
> from ProjectScylla here: https://github.com/HomericIntelligence/ProjectScylla I need to split
> up all of the claude, agents, and sub-agents to match the testing hierarchy"

## Clarifications Received

1. **Not integration** - User wanted categorization and testing plan, not code integration
2. **Tier comparison with sub-tiers** - Structure as `<tool>/<model>/<tier>/<sub-tier>/<test_results>`
3. **Scope limitation** - Only structure and composition scripts, not running actual tests

## Files Created

### Scripts (3 files)

```
scripts/
├── extract_blocks.py      # Extract CLAUDE.md blocks by line range
├── organize_agents.py     # Organize agents by YAML frontmatter level
└── organize_skills.py     # Organize skills by prefix/category
```

### Composition Scripts (4 files)

```
tests/claude-code/shared/compose/
├── compose_claude_md.py   # 6,745 bytes - Block composition with presets
├── compose_agents.py      # 6,563 bytes - Agent selection by level/pattern
├── compose_skills.py      # 7,802 bytes - Skill selection by category
└── generate_subtiers.py   # 16,899 bytes - Full sub-tier generator
```

### CLAUDE.md Blocks (18 files)

```
tests/claude-code/shared/blocks/
├── B01-project-overview.md       # Lines 1-11 (11 lines)
├── B02-critical-rules.md         # Lines 13-67 (55 lines) [CRITICAL]
├── B03-quick-links.md            # Lines 69-85 (17 lines)
├── B04-agent-hierarchy-intro.md  # Lines 87-109 (23 lines)
├── B05-skill-delegation.md       # Lines 110-178 (69 lines) [CRITICAL]
├── B06-dev-principles.md         # Lines 181-209 (29 lines)
├── B07-language-preference.md    # Lines 211-258 (48 lines) [CRITICAL]
├── B08-extended-thinking.md      # Lines 260-326 (67 lines)
├── B09-skills-vs-subagents.md    # Lines 327-395 (69 lines) [CRITICAL]
├── B10-hooks-best-practices.md   # Lines 397-462 (66 lines)
├── B11-output-style.md           # Lines 464-611 (148 lines)
├── B12-tool-use-optimization.md  # Lines 612-714 (103 lines) [CRITICAL]
├── B13-agentic-loops.md          # Lines 716-831 (116 lines)
├── B14-delegation-mojo.md        # Lines 833-880 (48 lines)
├── B15-common-commands.md        # Lines 882-1099 (218 lines)
├── B16-repo-architecture.md      # Lines 1101-1234 (134 lines) [CRITICAL]
├── B17-testing-strategy.md       # Lines 1236-1347 (112 lines)
└── B18-github-git-workflow.md    # Lines 1349-1787 (438 lines) [CRITICAL]
```

### Agents by Level (44 files)

```
tests/claude-code/shared/agents/
├── L0/ (1 agent)
│   └── chief-architect.md
├── L1/ (6 agents)
│   ├── agentic-workflows-orchestrator.md
│   ├── cicd-orchestrator.md
│   ├── foundation-orchestrator.md
│   ├── papers-orchestrator.md
│   ├── shared-library-orchestrator.md
│   └── tooling-orchestrator.md
├── L2/ (4 agents)
│   ├── architecture-design.md
│   ├── code-review-orchestrator.md
│   ├── integration-design.md
│   └── security-design.md
├── L3/ (24 agents)
│   ├── algorithm-review-specialist.md
│   ├── architecture-review-specialist.md
│   ├── blog-writer-specialist.md
│   ├── ci-failure-analyzer.md
│   ├── data-engineering-review-specialist.md
│   ├── dependency-review-specialist.md
│   ├── documentation-review-specialist.md
│   ├── documentation-specialist.md
│   ├── implementation-review-specialist.md
│   ├── implementation-specialist.md
│   ├── mojo-language-review-specialist.md
│   ├── mojo-syntax-validator.md
│   ├── numerical-stability-specialist.md
│   ├── paper-review-specialist.md
│   ├── performance-review-specialist.md
│   ├── performance-specialist.md
│   ├── pr-cleanup-specialist.md
│   ├── research-review-specialist.md
│   ├── safety-review-specialist.md
│   ├── security-review-specialist.md
│   ├── security-specialist.md
│   ├── test-flakiness-specialist.md
│   ├── test-review-specialist.md
│   └── test-specialist.md
├── L4/ (6 agents)
│   ├── documentation-engineer.md
│   ├── implementation-engineer.md
│   ├── log-analyzer.md
│   ├── performance-engineer.md
│   ├── senior-implementation-engineer.md
│   └── test-engineer.md
└── L5/ (3 agents)
    ├── junior-documentation-engineer.md
    ├── junior-implementation-engineer.md
    └── junior-test-engineer.md
```

### Skills by Category (62 directories)

```
tests/claude-code/shared/skills/
├── github/ (10 skills)
│   ├── gh-batch-merge-by-labels/
│   ├── gh-check-ci-status/
│   ├── gh-create-pr-linked/
│   ├── gh-fix-pr-feedback/
│   ├── gh-get-review-comments/
│   ├── gh-implement-issue/
│   ├── gh-post-issue-update/
│   ├── gh-read-issue-context/
│   ├── gh-reply-review-comment/
│   └── gh-review-pr/
├── mojo/ (10 skills)
│   ├── analyze-simd-usage/
│   ├── check-memory-safety/
│   ├── mojo-build-package/
│   ├── mojo-format/
│   ├── mojo-lint-syntax/
│   ├── mojo-memory-check/
│   ├── mojo-simd-optimize/
│   ├── mojo-test-runner/
│   ├── mojo-type-safety/
│   └── validate-mojo-patterns/
├── workflow/ (5 skills)
│   ├── phase-cleanup/
│   ├── phase-implement/
│   ├── phase-package/
│   ├── phase-plan-generate/
│   └── phase-test-tdd/
├── quality/ (5 skills)
│   ├── quality-complexity-check/
│   ├── quality-coverage-report/
│   ├── quality-fix-formatting/
│   ├── quality-run-linters/
│   └── quality-security-scan/
├── worktree/ (4 skills)
│   ├── worktree-cleanup/
│   ├── worktree-create/
│   ├── worktree-switch/
│   └── worktree-sync/
├── documentation/ (4 skills)
│   ├── doc-generate-adr/
│   ├── doc-issue-readme/
│   ├── doc-update-blog/
│   └── doc-validate-markdown/
├── agent/ (5 skills)
│   ├── agent-coverage-check/
│   ├── agent-hierarchy-diagram/
│   ├── agent-run-orchestrator/
│   ├── agent-test-delegation/
│   └── agent-validate-config/
├── cicd/ (8 skills)
│   ├── analyze-ci-failure-logs/
│   ├── build-run-local/
│   ├── fix-ci-failures/
│   ├── install-workflow/
│   ├── run-precommit/
│   ├── validate-workflow/
│   └── verify-pr-ready/
└── other/ (11+ skills)
    ├── create-review-checklist/
    ├── extract-test-failures/
    ├── generate-fix-suggestions/
    ├── plan-create-component/
    ├── plan-regenerate-issues/
    ├── plan-validate-structure/
    ├── review-pr-changes/
    ├── test-diff-analyzer/
    ├── tier-1/
    ├── tier-2/
    └── track-implementation-progress/
```

## Sub-Tier Definitions

### T0-vanilla (1 config)
- `00-baseline`: No CLAUDE.md, no agents, no skills

### T1-prompted (4 configs)
- `01-critical-rules-only`: B02 only (~55 lines)
- `02-minimal-viable`: B02+B07+B18 (~260 lines)
- `03-core-seven`: 7 critical blocks (~400 lines)
- `04-no-examples`: All blocks, code stripped (~900 lines)

### T2-skills (5 configs)
- `01-github-skills-only`: minimal + 10 github skills
- `02-mojo-skills-only`: minimal + 10 mojo skills
- `03-workflow-skills-only`: minimal + 5 workflow skills
- `04-all-skills-minimal-md`: minimal + all 62 skills
- `05-critical-skills-only`: minimal + top 10 skills

### T3-agents (5 configs)
- `01-junior-only`: minimal + L5 (3 agents)
- `02-engineers-only`: minimal + L4+L5 (9 agents)
- `03-specialists-only`: minimal + L3 (24 agents)
- `04-orchestrators-only`: minimal + L0+L1 (7 agents)
- `05-review-agents-only`: minimal + review specialists (13 agents)

### T4-delegation (4 configs)
- `01-flat-no-hierarchy`: minimal + all 44 agents (no delegation)
- `02-two-level`: minimal + L0→L4 only
- `03-three-level`: minimal + L0→L2→L4
- `04-skills-plus-agents`: minimal + all agents + all skills

### T5-hierarchy (4 configs)
- `01-full-six-level`: core-seven + full hierarchy + all skills
- `02-no-juniors`: core-seven + L0-L4 (41 agents) + all skills
- `03-minimal-hierarchy`: core-seven + L0+L3+L5 + dev-workflow skills
- `04-orchestrators-plus-juniors`: core-seven + L0+L1+L5 + github+mojo skills

### T6-hybrid (3 configs)
- `01-full-system`: full CLAUDE.md + all agents + all skills
- `02-optimized-core`: core-seven + L0+L1+L3 + critical skills
- `03-domain-optimized`: core-seven + implementation agents + mojo skills

## Git Operations

### Commit 1 (main branch)
```
4285c45 - feat(tests): add claude-code testing framework from ProjectOdyssey
191 files changed, 19439 insertions(+)
```

### Branch Created
```
skill/tooling/prompt-ablation-framework
```

## Tool Usage Patterns

### Successful Patterns
- `gh repo clone` for private repos
- Separate mkdir commands instead of brace expansion
- Python scripts for complex file operations
- `--list` flags for verification before generation

### Failed Patterns
- WebFetch for private GitHub URLs
- Bash brace expansion `{a,b,c}`
- Complex shell variable substitution in loops

## Evaluation Metrics (Proposed)

| Metric | Description | Target |
|--------|-------------|--------|
| Pass Rate | Task completion rate | >0.8 |
| Impl Rate | Requirement satisfaction | >0.85 |
| R_Prog | Fine-grained progress | Continuous |
| CoP | Cost of Pass (tokens/$) | Minimize |
| Latency | Time to completion | <5min |
| Consistency | Output stability | >0.9 |

## Open Questions

1. What task types should be used for evaluation?
2. How many runs per configuration for statistical significance?
3. Should evaluation include human review or purely automated?
4. How to handle non-deterministic model outputs?
5. What's the minimum sample size per configuration?

---

## Skill: deduplicate-test-fixtures (2026-01-02)

### Session Details

- **Date**: 2026-01-02
- **Model**: Claude Opus 4.5 (claude-opus-4-5-20251101)
- **Working Directory**: /home/mvillmow/ProjectOdyssey/build/ProjectScylla
- **Branch**: feat/odyssey-benchmark-tests → skill/testing/deduplicate-test-fixtures

### Initial Request

> "There are lots of files that are duplicated over and over and over again. For example,
> implementation-review-specialist.md is duplicated 66 times. Instead of duplicating the files,
> I want to modify the testing system for the test to specify where the file is taken from,
> or how it is generated, and at test time, to setup the .github repo correctly by grabbing
> the file from the correct location."

### Key Findings

1. **Actual duplication was different than reported**:
   - User mentioned `implementation-review-specialist.md` duplicated 66 times
   - Analysis revealed only 1 copy exists at `tests/claude-code/shared/agents/L3/implementation-review-specialist.md`
   - Real duplication was 1034 CLAUDE.md files in T0 tier directories

2. **Existing infrastructure existed but wasn't used**:
   - `tier_manager.py` already had `_compose_claude_md()` method
   - Prior commit (d7dfeb9) added the infrastructure but never ran migration
   - T1-T6 were already migrated, only T0 remained

3. **Block-based composition pattern**:
   - 18 shared blocks (B01-B18) in `tests/claude-code/shared/blocks/`
   - Directory naming pattern maps to block composition (e.g., `06-B01` → `[B01]`)

### Commands Used

```bash
# Find duplicated files by hash
find tests -type f -name "*.md" | xargs md5sum | awk '{print $1}' | sort | uniq -c | sort -rn | head -20

# Count CLAUDE.md files in T0
find tests/fixtures/tests -name "CLAUDE.md" -path "*/t0/*" | wc -l

# Dry-run migration
python scripts/migrate_t0_to_blocks.py tests/fixtures/tests/ --dry-run

# Execute migration
python scripts/migrate_t0_to_blocks.py tests/fixtures/tests/

# Verify
du -sh tests/fixtures/
```

### Results

| Metric | Before | After |
|--------|--------|-------|
| CLAUDE.md files in T0 | 1034 | 0 |
| Fixture size | 56MB | 47MB |
| Lines removed | 0 | 239,888 |
| Config files updated | 0 | 1128 |

### Files Created/Modified

1. `scripts/migrate_t0_to_blocks.py` - Migration script (created)
2. `tests/fixtures/tests/test-*/t0/*/config.yaml` - 1128 files updated with `resources.claude_md.blocks`
3. `tests/fixtures/tests/test-*/t0/*/CLAUDE.md` - 1034 files deleted

---

## Skill: centralize-subtest-configs (2026-01-03)

### Session Details

- **Date**: 2026-01-03
- **Model**: Claude Opus 4.5 (claude-opus-4-5-20251101)
- **Working Directory**: /home/mvillmow/ProjectOdyssey/build/ProjectScylla
- **Branch**: feat/odyssey-benchmark-tests

### Initial Request

> "There are still lots of code duplication that needs to be removed. Looking at filelist.txt,
> there are 120 files that are duplicated more than once... config.yaml duplicated 47 times...
> Lets come up with a plan for reducing this duplication and instead having it be generated
> or linked dynamically at runtime. Ideally each test has a single json that documents its
> configuration, and that configuration knows which tiers and sub-tests to run from."

### Key Findings

1. **Scale of duplication**:
   - 5361 config.yaml files across 47 tests
   - 5355 (99.9%) were duplicates
   - 119 unique subtest configs repeated 47 times each
   - Example: `t1/04-github/config.yaml` identical across all tests

2. **Root cause**: Subtest configs are test-independent - they define tier components, not test-specific settings

3. **Solution**: Centralize configs in `tests/claude-code/shared/subtests/` and modify `tier_manager.py` to load from there

### Commands Used

```bash
# Find duplicated files by hash
find tests/fixtures/tests -type f -name "config.yaml" | xargs md5sum | awk '{print $1}' | sort | uniq -c | sort -rn | head -30

# Count total duplicates
find tests/fixtures/tests -type f -name "config.yaml" | xargs md5sum | awk '{print $1}' | sort | uniq -c | awk '$1 > 1 {sum += $1; count++} END {print "Duplicated file groups:", count; print "Total duplicated files:", sum}'

# Create shared subtests structure
mkdir -p tests/claude-code/shared/subtests/t{0,1,2,3,4,5,6}

# Copy configs from test-001 to shared
for tier in t0 t1 t2 t3 t4 t5 t6; do
  for dir in tests/fixtures/tests/test-001/$tier/*/; do
    subtest=$(basename "$dir")
    if [ -f "$dir/config.yaml" ]; then
      cp "$dir/config.yaml" "tests/claude-code/shared/subtests/$tier/$subtest.yaml"
    fi
  done
done

# Dry-run migration
python scripts/migrate_subtests_to_shared.py tests/fixtures/tests/ --dry-run

# Execute migration
python scripts/migrate_subtests_to_shared.py tests/fixtures/tests/
```

### Results

| Metric | Before | After |
|--------|--------|-------|
| config.yaml files | 5361 | 47 (test-level) + 113 (shared) |
| Fixture size | 47MB | 1.4MB |
| Tier directories per test | 7 | 0 |
| Subtest directories | 5361 | 0 (now YAML files in shared) |

### Files Created/Modified

1. `tests/claude-code/shared/subtests/t{0-6}/*.yaml` - 113 centralized subtest configs
2. `scripts/migrate_subtests_to_shared.py` - Migration script
3. `src/scylla/e2e/tier_manager.py` - Added `_load_shared_subtests()` and `_overlay_test_specific()` methods
4. `tests/fixtures/tests/test-*/t{0-6}/` - 329 directories deleted (5361 files)
