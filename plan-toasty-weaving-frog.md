# Plan: Create test-002 - Mojo Hello World Test

## Overview

Create a new test fixture `test-002` that evaluates an AI agent's ability to add a simple Mojo "Hello, World!" example to the Modular repository, following Mojo v0.26.1 best practices and integrating with the Bazel build system.

## Source Configuration

- **Repository**: https://github.com/modular/modular/tree/main
- **Commit**: `14df6466f35f2e1ee7afad3c3d9936e6da4f8cc6`
- **Task**: Add a Mojo hello world example that integrates with the repository structure

## Files to Create

### 1. Main Test Definition
**File**: `tests/fixtures/tests/test-002/test.yaml`

```yaml
id: "test-002"
name: "Mojo Hello World Task"
description: |
  Test AI agent's ability to add a Mojo example to the Modular repository.
  Agent must discover proper location, write Mojo v0.26.1 code, integrate
  with Bazel build system, and provide full documentation.

source:
  repo: "https://github.com/modular/modular"
  hash: "14df6466f35f2e1ee7afad3c3d9936e6da4f8cc6"

task:
  prompt_file: "prompt.md"
  timeout_seconds: 7200

validation:
  criteria_file: "expected/criteria.md"
  rubric_file: "expected/rubric.yaml"

tiers:
  - T0  # Prompts (24 sub-tests)
  - T1  # Skills (10 sub-tests)
  - T2  # Tooling (15 sub-tests)
  - T3  # Delegation (41 sub-tests)
  - T4  # Hierarchy (7 sub-tests)
  - T5  # Hybrid (15 sub-tests)
  - T6  # Super (1 sub-test)
```

### 2. Task Prompt
**File**: `tests/fixtures/tests/test-002/prompt.md`

```markdown
# Task: Add a Mojo Hello World Example

Add a simple Mojo "Hello, World!" example to this repository that follows
the project's patterns and conventions.

## Requirements

1. **Discover Location**: Explore the repository structure to find the
   appropriate location for Mojo examples
2. **Create Mojo File**: Write `hello.mojo` using Mojo v0.26.1 syntax
3. **Bazel Integration**: Add BUILD.bazel file if required by the project
4. **Output**: The program must print exactly: `Hello, world`
5. **Documentation**: Include module docstring, inline comments, and
   update any relevant README files

## Mojo v0.26.1 Requirements

- Use `fn main()` as entry point
- Use `print()` for output (NOT `print_string()`)
- Ensure code passes `mojo build` without errors or warnings
- Follow ownership patterns (`out self`, `mut self`, etc.)

## Expected Output

When running the example:
```
Hello, world
```

## Success Criteria

- Example discovered proper location in repository
- Code compiles with `mojo build` (zero errors/warnings)
- Code compiles with `bazel build` if Bazel is used
- Running the example prints "Hello, world"
- Exit code is 0
- Module docstring present
- README updated or created as appropriate
```

### 3. Evaluation Criteria
**File**: `tests/fixtures/tests/test-002/expected/criteria.md`

```markdown
# Evaluation Criteria for Mojo Hello World

## R001: Location Discovery (Weight: 1.0)
Agent must explore the repository and place the example in an appropriate
location that follows existing project conventions.

**Verification**: Check that file is placed in a sensible location (e.g.,
examples/, mojo/examples/, or similar directory with existing examples)

## R002: File Creation (Weight: 2.0)
Agent must create a `hello.mojo` file.

**Verification**: Check if a .mojo file exists with hello world functionality

## R003: Mojo Syntax Compliance (Weight: 2.5)
Code must follow Mojo v0.26.1 syntax standards:
- `fn main()` entry point
- `print()` function for output
- No deprecated patterns (inout, @value, DynamicVector)
- Proper constructor patterns if any structs used

**Verification**: Run `mojo build <file>` and check for zero errors/warnings

## R004: Correct Output (Weight: 2.0)
The program must print exactly "Hello, world" when executed.

**Verification**: Run compiled binary and check stdout matches "Hello, world"

## R005: Bazel Integration (Weight: 1.5)
If repository uses Bazel, agent must create/update BUILD.bazel.

**Verification**: Run `bazel build //<path>:hello` succeeds

## R006: Documentation - Module Docstring (Weight: 1.0)
Source file must include a module docstring explaining purpose.

**Verification**: Parse file for docstring at module level

## R007: Documentation - Inline Comments (Weight: 0.5)
Code should have appropriate inline comments for clarity.

**Verification**: Check for meaningful comments in source

## R008: Documentation - README (Weight: 1.0)
README should be updated or created to document the example.

**Verification**: Check for README.md mentioning the hello world example

## R009: Clean Exit (Weight: 0.5)
Program must exit with code 0.

**Verification**: Check exit code after execution

## R010: No Warnings (Weight: 1.0)
Compilation must produce zero warnings.

**Verification**: Capture stderr from mojo build, check empty

## R011: Memory Safety (Weight: 1.5)
Code must follow Mojo memory safety patterns:
- Proper ownership transfer with `^` operator
- No use-after-move patterns
- No uninitialized list/collection access
- Pointer safety if applicable

**Verification**: Run `check-memory-safety` skill validation
**Skill**: ProjectOdyssey/.claude/skills/check-memory-safety

## R012: Ownership Patterns (Weight: 1.0)
Code must follow correct ownership conventions:
- `out self` in constructors (not `mut self`)
- `mut self` in mutating methods
- No `inout` keyword anywhere
- `var` parameter for ownership transfer in function args

**Verification**: Run `validate-mojo-patterns` skill validation
**Skill**: ProjectOdyssey/.claude/skills/validate-mojo-patterns

## R013: No Deprecated Patterns (Weight: 1.0)
Code must not use deprecated Mojo patterns:
- No `@value` decorator (use `@fieldwise_init` + traits)
- No `DynamicVector` (use `List`)
- No `inout` keyword (use `mut`)
- Tuple return syntax `-> Tuple[T1, T2]` not `-> (T1, T2)`

**Verification**: Run `mojo-lint-syntax` skill validation
**Skill**: ProjectOdyssey/.claude/skills/mojo-lint-syntax
```

### 4. Rubric File
**File**: `tests/fixtures/tests/test-002/expected/rubric.yaml`

```yaml
requirements:
  # Core Functionality (Weight: 6.5)
  - id: "R001"
    description: "Location Discovery - Example placed in appropriate directory"
    weight: 1.0
    evaluation: "scaled"

  - id: "R002"
    description: "File Creation - hello.mojo exists"
    weight: 2.0
    evaluation: "binary"

  - id: "R003"
    description: "Mojo Syntax Compliance - v0.26.1 standards"
    weight: 2.5
    evaluation: "scaled"
    criteria:
      - "fn main() entry point"
      - "print() function used"
      - "No deprecated patterns (inout, @value, DynamicVector)"
      - "out self in constructors (if any)"
      - "mut self in mutating methods (if any)"
      - "Proper List literal syntax"
      - "Tuple return syntax correct"

  - id: "R004"
    description: "Correct Output - prints Hello, world"
    weight: 2.0
    evaluation: "binary"

  # Build Integration (Weight: 2.5)
  - id: "R005"
    description: "Bazel Integration - BUILD.bazel created/updated"
    weight: 1.5
    evaluation: "scaled"
    criteria:
      - "BUILD.bazel file exists or updated"
      - "mojo_binary or appropriate rule used"
      - "bazel build succeeds"

  - id: "R010"
    description: "Zero compilation warnings"
    weight: 1.0
    evaluation: "binary"

  # Documentation (Weight: 2.5)
  - id: "R006"
    description: "Module Docstring present"
    weight: 1.0
    evaluation: "binary"

  - id: "R007"
    description: "Inline Comments for clarity"
    weight: 0.5
    evaluation: "scaled"

  - id: "R008"
    description: "README documentation"
    weight: 1.0
    evaluation: "scaled"
    criteria:
      - "README exists or updated"
      - "Example documented"
      - "Build instructions included"

  # Execution (Weight: 0.5)
  - id: "R009"
    description: "Clean Exit (code 0)"
    weight: 0.5
    evaluation: "binary"

  # Memory Safety & Ownership (Weight: 2.5) - From ProjectOdyssey Skills
  - id: "R011"
    description: "Memory Safety - No ownership violations"
    weight: 1.5
    evaluation: "scaled"
    criteria:
      - "Proper ownership transfer with ^ operator"
      - "No use-after-move patterns"
      - "No uninitialized access"
      - "Pointer safety (if applicable)"
    skill_validation: "check-memory-safety"

  - id: "R012"
    description: "Ownership Patterns - Correct conventions"
    weight: 1.0
    evaluation: "scaled"
    criteria:
      - "out self in constructors (not mut self)"
      - "mut self in mutating methods"
      - "No inout keyword anywhere"
      - "var parameter for ownership transfer"
    skill_validation: "validate-mojo-patterns"

  # Deprecated Patterns (Weight: 1.0) - From ProjectOdyssey Skills
  - id: "R013"
    description: "No Deprecated Patterns"
    weight: 1.0
    evaluation: "binary"
    criteria:
      - "No @value decorator (use @fieldwise_init)"
      - "No DynamicVector (use List)"
      - "No inout keyword (use mut)"
      - "Tuple return syntax -> Tuple[T1, T2] not -> (T1, T2)"
    skill_validation: "mojo-lint-syntax"

grading:
  pass_threshold: 0.70
  grade_scale:
    A: 0.95
    B: 0.85
    C: 0.75
    D: 0.65
    F: 0.0

# Total weight: 15.0
# Functional (R001-R004): 7.5 (50%)
# Build/Compile (R005, R010): 2.5 (17%)
# Documentation (R006-R008): 2.5 (17%)
# Safety/Patterns (R009, R011-R013): 2.5 (17%)
```

### 5. Test Config
**File**: `tests/fixtures/tests/test-002/config.yaml`

```yaml
timeout_seconds: 7200
max_cost_usd: 10.0
```

### 6. Tier Sub-Test Directories

Copy the entire tier structure from test-001:
- `t0/` - 24 prompt ablation sub-tests (00-empty through 23-B18)
- `t1/` - 10 skills sub-tests (01-agent through 10-advise-plugin)
- `t2/` - 15 tooling sub-tests (01-file-ops-only through 15-custom-mcp)
- `t3/` - 41 delegation sub-tests (01-architecture-design through 41-all-L5)
- `t4/` - 7 hierarchy sub-tests (01-chief-architect through 07-tooling-orchestrator)
- `t5/` - 15 hybrid sub-tests
- `t6/` - 1 super sub-test

## Implementation Steps

1. **Create directory structure**:
   ```
   tests/fixtures/tests/test-002/
   ├── test.yaml
   ├── prompt.md
   ├── config.yaml
   ├── expected/
   │   ├── criteria.md
   │   └── rubric.yaml
   ├── t0/ (copy from test-001)
   ├── t1/ (copy from test-001)
   ├── t2/ (copy from test-001)
   ├── t3/ (copy from test-001)
   ├── t4/ (copy from test-001)
   ├── t5/ (copy from test-001)
   └── t6/ (copy from test-001)
   ```

2. **Create test-002 specific files** (test.yaml, prompt.md, criteria.md, rubric.yaml, config.yaml)

3. **Copy tier directories** from test-001 (they contain system prompt variations and skill configurations that are test-agnostic)

## Alignment with Judge System Prompt

The rubric aligns with `config/judge/system_prompt.md`:

| Judge Criterion | Test-002 Coverage |
|-----------------|-------------------|
| Correctness (50%) | R003 (syntax), R004 (output), R009 (exit), R011 (memory) |
| Completeness | R001 (location), R002 (file), R005 (Bazel) |
| Code Structure (30%) | R003 (patterns), R007 (comments), R012 (ownership) |
| Documentation | R006 (docstring), R007 (comments), R008 (README) |
| Linting Compliance | R003 (mojo build), R010 (warnings), R013 (deprecated) |
| Security/Safety (20%) | R011 (memory safety), R012 (ownership) |

## ProjectOdyssey Skills & Agents Integration

The test configuration must integrate Mojo-specific skills and agents from ProjectOdyssey:

### Skills to Include (T1 - Skills Tier)
Source: `https://github.com/mvillmow/ProjectOdyssey/tree/main/.claude/skills`

| Skill | Purpose | Rubric Alignment |
|-------|---------|------------------|
| `mojo-lint-syntax` | v0.26.1 syntax validation | R003, R010 |
| `validate-mojo-patterns` | Pattern checking (out self, mut, etc.) | R003, R012 |
| `check-memory-safety` | Ownership and memory safety | R011, R012 |
| `mojo-build-package` | Build and package compilation | R005 |
| `mojo-format` | Code formatting | R007 |
| `mojo-type-safety` | Type system verification | R003 |

### Agents to Include (T3 - Delegation Tier)
Source: `https://github.com/mvillmow/ProjectOdyssey/tree/main/.claude/agents`

| Agent | Level | Purpose |
|-------|-------|---------|
| `mojo-syntax-validator` | L3 | Validates v0.26.1 syntax patterns |
| `mojo-language-review-specialist` | L3 | Reviews Mojo idioms and conventions |

### New Tier Sub-Tests for T1 (Skills)

Create a new sub-test specifically for Mojo skills:
**File**: `tests/fixtures/tests/test-002/t1/11-mojo-skills/config.yaml`

```yaml
name: "Mojo Skills Bundle"
description: "All 7 Mojo-specific skills for development validation"
extends_previous: true
skills:
  - mojo-lint-syntax
  - validate-mojo-patterns
  - check-memory-safety
  - mojo-build-package
  - mojo-format
  - mojo-type-safety
  - mojo-test-runner
skills_source: "https://github.com/mvillmow/ProjectOdyssey/tree/main/.claude/skills"
```

### New Tier Sub-Tests for T3 (Delegation)

Add Mojo-specific agent delegations:
**File**: `tests/fixtures/tests/test-002/t3/42-mojo-syntax-validator/config.yaml`

```yaml
name: "Mojo Syntax Validator Agent"
description: "L3 specialist for validating Mojo v0.26.1 syntax"
extends_previous: true
agent: mojo-syntax-validator
agent_source: "https://github.com/mvillmow/ProjectOdyssey/tree/main/.claude/agents"
```

**File**: `tests/fixtures/tests/test-002/t3/43-mojo-language-review/config.yaml`

```yaml
name: "Mojo Language Review Specialist"
description: "L3 specialist for Mojo idioms and SIMD optimization"
extends_previous: true
agent: mojo-language-review-specialist
agent_source: "https://github.com/mvillmow/ProjectOdyssey/tree/main/.claude/agents"
```

### Updated Rubric with Memory Safety

Add these requirements to `expected/rubric.yaml`:

```yaml
  - id: "R011"
    description: "Memory Safety - No ownership violations"
    weight: 1.5
    evaluation: "scaled"
    criteria:
      - "Proper ownership transfer with ^"
      - "No use-after-move"
      - "No uninitialized access"
      - "Pointer safety (if applicable)"

  - id: "R012"
    description: "Ownership Patterns - Correct conventions"
    weight: 1.0
    evaluation: "scaled"
    criteria:
      - "out self in constructors"
      - "mut self in mutating methods"
      - "No inout keyword"
      - "var parameter for ownership transfer"

  - id: "R013"
    description: "No Deprecated Patterns"
    weight: 1.0
    evaluation: "binary"
    criteria:
      - "No @value decorator"
      - "No DynamicVector"
      - "No inout keyword"
      - "Tuple return syntax correct"
```

## Critical Files

- `/home/mvillmow/ProjectScylla/tests/fixtures/tests/test-001/` - Reference implementation
- `/home/mvillmow/ProjectScylla/config/judge/system_prompt.md` - Judge criteria
- `/home/mvillmow/ProjectScylla/.claude/shared/mojo-guidelines.md` - Mojo best practices
- `/home/mvillmow/ProjectScylla/.claude/shared/mojo-anti-patterns.md` - Common mistakes
- `https://github.com/mvillmow/ProjectOdyssey/.claude/skills/` - Mojo skills source
- `https://github.com/mvillmow/ProjectOdyssey/.claude/agents/` - Mojo agents source

## Mojo v0.26.1 Best Practices for Rubric

The rubric enforces these Mojo standards (from ProjectOdyssey skills/agents):

### Constructor & Method Patterns
1. `fn main()` as entry point (not `def main()`)
2. `out self` in constructors (NEVER `mut self` or `inout self`)
3. `mut self` in mutating methods
4. Implicit `read` for immutable access (no explicit `read self`)

### Ownership & Memory
5. `^` transfer operator for List/Dict/String returns
6. `var` parameter for ownership transfer in function args
7. No `ImplicitlyCopyable` with heap-allocated fields
8. Proper initialization before access (use `append()` not index assignment)

### Syntax & Types
9. `print()` for output (not `print_string()`)
10. List literals `[1, 2, 3]` not `List[Int](1, 2, 3)`
11. `Tuple[T1, T2]` return type not `-> (T1, T2)`
12. `@fieldwise_init` + traits instead of `@value`
13. `List` instead of `DynamicVector`

### Compilation
14. Zero compiler errors
15. Zero compiler warnings
16. `mojo build -I .` for executables
17. `mojo package` for library files

---

## Implementation Summary

### Files to Create
1. `tests/fixtures/tests/test-002/test.yaml` - Main test definition
2. `tests/fixtures/tests/test-002/prompt.md` - Task prompt
3. `tests/fixtures/tests/test-002/config.yaml` - Test configuration
4. `tests/fixtures/tests/test-002/expected/criteria.md` - 13 evaluation criteria
5. `tests/fixtures/tests/test-002/expected/rubric.yaml` - Weighted rubric

### Directories to Copy from test-001
- `t0/` through `t6/` - All tier sub-test configurations

### New Sub-Tests to Create
- `t1/11-mojo-skills/` - Mojo skills bundle (7 skills)
- `t3/42-mojo-syntax-validator/` - Mojo syntax validator agent
- `t3/43-mojo-language-review/` - Mojo language review specialist agent

### External Dependencies
- **Skills**: https://github.com/mvillmow/ProjectOdyssey/.claude/skills/
- **Agents**: https://github.com/mvillmow/ProjectOdyssey/.claude/agents/

### Test Coverage
- 13 requirements (R001-R013)
- Total weight: 15.0 points
- Pass threshold: 70%
- Integrates with existing judge system at `config/judge/system_prompt.md`
