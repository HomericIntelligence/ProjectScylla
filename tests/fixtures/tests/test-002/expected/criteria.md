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
- `out self` in constructors, `mut self` in mutating methods
- Proper List literal syntax
- Correct tuple return syntax `-> Tuple[T1, T2]`

**Verification**: Run `mojo build <file>` and check for zero errors/warnings

## R004: Correct Output (Weight: 2.0)

The program must print exactly "Hello, world" when executed.

**Verification**: Run compiled binary and check stdout matches "Hello, world"

## R005: Bazel Integration (Weight: 1.5)

If repository uses Bazel, agent must create/update BUILD.bazel.

- BUILD.bazel file exists or updated
- mojo_binary or appropriate rule used
- bazel build succeeds

**Verification**: Run `bazel build //<path>:hello` succeeds

## R006: Documentation - Module Docstring (Weight: 1.0)

Source file must include a module docstring explaining purpose.

**Verification**: Parse file for docstring at module level

## R007: Documentation - Inline Comments (Weight: 0.5)

Code should have appropriate inline comments for clarity.

**Verification**: Check for meaningful comments in source

## R008: Documentation - README (Weight: 1.0)

README should be updated or created to document the example.

- README exists or updated
- Example documented
- Build instructions included

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

## R014: Code Formatting (Weight: 1.0)

Code must pass `mojo format` with no changes required.

- Consistent indentation
- Proper spacing around operators
- Correct line lengths
- Standard Mojo style conventions

**Verification**: Run `mojo format --check <file>` and verify exit code 0
**Skill**: ProjectOdyssey/.claude/skills/mojo-format
