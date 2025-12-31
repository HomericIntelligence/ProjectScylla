# Success Criteria: Justfile to Makefile Conversion

## File Creation

- A `Makefile` must exist in the repository root
- The file must be syntactically valid (parseable by GNU Make)
- A `cleanup.sh` script must exist in the repository root
- The cleanup script must be executable

## Recipe Coverage

- Every recipe in the justfile must have an equivalent Makefile target
- Recipe names should be identical or clearly mapped (e.g., `build-debug` → `build-debug`)

## Functional Equivalence

For the following commands, running with just vs make should produce equivalent results:

- `just help` ↔ `make help` (list available commands)
- `just build debug` ↔ `make build-debug` (build in debug mode)
- `just clean` ↔ `make clean` (clean build artifacts)
- `just test-mojo` ↔ `make test-mojo` (run Mojo tests)

"Equivalent results" means:

- Same exit code (0 for success, non-zero for failure)
- Similar output (exact match not required, but core content should match)
- Same side effects (files created/deleted should be the same)

## Variable Handling

- Justfile variables must be converted to Make variables
- Variable interpolation must work correctly

## Quality

- The Makefile should be readable and well-organized
- Comments should explain non-obvious translations

## Cleanup Script

The cleanup script (`cleanup.sh`) must:

- Execute without errors (exit code 0)
- Remove all build artifacts
- Remove any generated files
- Return the repository to a clean state

| Score | Criteria |
|-------|----------|
| 1.0 | Script exists, runs successfully, returns env to clean state |
| 0.7 | Script exists, runs successfully, partial cleanup |
| 0.4 | Script exists but fails or incomplete |
| 0.0 | No cleanup script provided |
