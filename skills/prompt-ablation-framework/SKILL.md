# Prompt Ablation Framework

| Field | Value |
|-------|-------|
| **Date** | 2024-12-30 |
| **Category** | tooling |
| **Objective** | Create a testing framework to evaluate which components of a prompting system are essential vs. optional |
| **Outcome** | Success - 191 files, 78 test configurations across 3 models |
| **Source** | ProjectOdyssey (1787-line CLAUDE.md, 44 agents, 62 skills) |
| **Target** | ProjectScylla (T0-T6 tier methodology) |

## When to Use

Use this skill when you need to:

- **Evaluate prompt effectiveness**: Determine which parts of a CLAUDE.md file are essential
- **Test agent configurations**: Compare different agent hierarchy levels
- **Optimize skill sets**: Find the minimal skill set needed for specific tasks
- **Benchmark model performance**: Compare sonnet/opus/haiku across configurations
- **Reduce token overhead**: Identify which prompt components can be removed

## Verified Workflow

### Step 1: Decompose CLAUDE.md into Blocks

Extract logical sections from the monolithic CLAUDE.md file:

```bash
# Extract blocks with line ranges
python scripts/extract_blocks.py /path/to/CLAUDE.md /output/blocks/
```

**Block Structure** (18 blocks from ProjectOdyssey):

| Block | Lines | Priority | Purpose |
|-------|-------|----------|---------|
| B02 | 55 | Critical | Safety rules |
| B05 | 69 | Critical | Skill delegation patterns |
| B07 | 48 | Critical | Language preference |
| B09 | 69 | Critical | Skills vs sub-agents |
| B12 | 103 | Critical | Tool use optimization |
| B16 | 134 | Critical | Repository architecture |
| B18 | 438 | Critical | GitHub/Git workflow |
| B06-B08, B10-B11, B13-B14 | ~500 | Important | Extended guidance |
| B01, B03-B04, B15, B17 | ~380 | Optional | Context/reference |

### Step 2: Organize Agents by Level

Copy agents to level-based directories:

```bash
python scripts/organize_agents.py
```

**Hierarchy Levels**:

- L0: Chief Architect (1 agent) - Strategic decisions
- L1: Orchestrators (6 agents) - Domain coordination
- L2: Design (4 agents) - Module design
- L3: Specialists (24 agents) - Specialized execution
- L4: Engineers (6 agents) - Implementation
- L5: Junior Engineers (3 agents) - Simple tasks

### Step 3: Organize Skills by Category

Copy skills to category-based directories:

```bash
python scripts/organize_skills.py
```

**Categories** (62 total skills):

- github (10): PR, issue, review operations
- mojo (10): Language-specific tools
- workflow (5): Phase management
- quality (5): Linting, formatting
- worktree (4): Git worktree management
- documentation (4): ADRs, markdown
- agent (5): Agent system tools
- cicd (8): CI/CD operations
- other (11): Miscellaneous

### Step 4: Create Composition Scripts

Four scripts enable flexible configuration generation:

```bash
# Compose CLAUDE.md from blocks
python compose_claude_md.py --preset minimal --output config/CLAUDE.md

# Compose agents by level
python compose_agents.py --preset engineers-only --output config/agents/

# Compose skills by category
python compose_skills.py --preset critical --output config/skills/

# Generate all sub-tier configurations
python generate_subtiers.py --model sonnet --dry-run
```

### Step 5: Define Test Tiers (T0-T6)

| Tier | Focus | Sub-tiers | Description |
|------|-------|-----------|-------------|
| T0 | Baseline | 1 | Vanilla Claude, no prompting |
| T1 | Prompted | 4 | CLAUDE.md variations (55-1787 lines) |
| T2 | Skills | 5 | Skill category combinations |
| T3 | Agents | 5 | Agent level variations |
| T4 | Delegation | 4 | Hierarchy pattern variations |
| T5 | Hierarchy | 4 | Full hierarchy variations |
| T6 | Hybrid | 3 | Complete system variations |

**Total**: 26 configurations × 3 models = 78 test cases

## Failed Attempts

### 1. WebFetch for Private Repos

**What didn't work**: Using `WebFetch` tool to access private GitHub repo

```
WebFetch("https://github.com/HomericIntelligence/ProjectScylla") → 404
```

**Why it failed**: WebFetch cannot authenticate to private repositories

**Solution**: Use `gh repo clone` with authenticated GitHub CLI

```bash
gh repo clone HomericIntelligence/ProjectScylla /tmp/ProjectScylla
```

### 2. Bash Brace Expansion in Tool

**What didn't work**: Creating multiple directories with brace expansion

```bash
mkdir -p tests/claude-code/shared/{blocks,agents,skills,compose}
# Created literal directory named "{blocks,agents,skills,compose}"
```

**Why it failed**: The Bash tool escapes special characters, preventing shell expansion

**Solution**: Run separate mkdir commands for each directory

```bash
mkdir -p tests/claude-code/shared/blocks
mkdir -p tests/claude-code/shared/agents
mkdir -p tests/claude-code/shared/skills
mkdir -p tests/claude-code/shared/compose
```

### 3. Shell Variable Substitution in Loops

**What didn't work**: Complex bash loops with command substitution

```bash
for l in 0 1 2 3 4 5; do
  count=$(ls dir/L$l/ | wc -l)  # $l gets escaped
  echo "L$l: $count"
done
```

**Why it failed**: Variables in complex constructs get escaped by the tool

**Solution**: Use simpler commands or Python scripts for complex logic

## Results & Parameters

### Directory Structure

```
tests/claude-code/
├── shared/
│   ├── blocks/          # 18 CLAUDE.md block files
│   ├── agents/L0-L5/    # 44 agents by level
│   ├── skills/{9 cats}/ # 62 skills by category
│   └── compose/         # 4 composition scripts
├── sonnet/T0-T6/        # Tier directories
├── opus/T0-T6/
└── haiku/T0-T6/
```

### Preset Configurations

**CLAUDE.md Presets** (compose_claude_md.py):

| Preset | Blocks | Lines | Use Case |
|--------|--------|-------|----------|
| critical-only | B02 | ~55 | Minimal safety |
| minimal | B02, B07, B18 | ~260 | Minimum viable |
| core-seven | B02, B05, B07, B09, B12, B16, B18 | ~400 | Recommended |
| no-examples | All, stripped | ~900 | Prose only |
| full | All 18 | 1787 | Reference |

**Agent Presets** (compose_agents.py):

| Preset | Levels | Count | Use Case |
|--------|--------|-------|----------|
| junior-only | L5 | 3 | Simple tasks |
| engineers-only | L4+L5 | 9 | Implementation |
| specialists-only | L3 | 24 | Specialized work |
| orchestrators | L0+L1 | 7 | Coordination |
| full | L0-L5 | 44 | Complete hierarchy |

**Skill Presets** (compose_skills.py):

| Preset | Categories | Count | Use Case |
|--------|------------|-------|----------|
| github-only | github | 10 | PR/issue ops |
| mojo-only | mojo | 10 | Mojo development |
| critical | top 10 | 10 | Essential tools |
| dev-workflow | github, worktree, quality, cicd | 27 | Full dev flow |
| full | all | 62 | Complete set |

### Metrics

| Metric | Value |
|--------|-------|
| Files created | 191 |
| Lines added | 19,439 |
| CLAUDE.md blocks | 18 |
| Agents organized | 44 |
| Skills organized | 62 |
| Test configurations | 26 |
| Total test cases | 78 |

## Next Steps

1. **Run baseline tests**: Generate T0 configurations and establish baselines
2. **Implement test runner**: Create automation for running tests across configurations
3. **Define evaluation metrics**: Pass rate, implementation rate, token efficiency
4. **Analyze results**: Identify minimum viable configurations per task type
5. **Create optimization recommendations**: Document which components are essential

## Related Skills

- `gh-create-pr-linked` - For creating PRs with issue links
- `run-precommit` - For validation before commits
- `mojo-format` - For Mojo code formatting

## References

- [ProjectScylla T0-T6 Methodology](https://github.com/HomericIntelligence/ProjectScylla)
- [ProjectOdyssey Agent Hierarchy](/agents/hierarchy.md)
- [CLAUDE.md Best Practices](/.claude/shared/)
