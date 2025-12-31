# Task: Convert Justfile to Makefile

## Objective

Convert the `justfile` in this repository to an equivalent `Makefile` that
provides the same functionality using standard GNU Make.

## Requirements

1. Create a `Makefile` that includes all recipes from the justfile
2. Preserve variable definitions and their usage
3. Handle Docker-related commands correctly
4. Include a `help` target that lists available commands
5. Maintain recipe dependencies
6. Create a cleanup script (`cleanup.sh`) that:
   - Removes all build artifacts
   - Removes any generated files
   - Returns the repository to a clean state
   - Is executable and runs without errors

## Constraints

- Use standard GNU Make syntax (compatible with Make 4.0+)
- Do not use third-party Make extensions
- Preserve comments and documentation
- Keep the file readable and maintainable

## Expected Output

- A new file named `Makefile` in the repository root
- A new file named `cleanup.sh` in the repository root
- The original `justfile` should remain unchanged

## Validation

Your solution will be validated by running equivalent commands with both
build systems and comparing results. The cleanup script will be executed
to verify it properly cleans the environment.
