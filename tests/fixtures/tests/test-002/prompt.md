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

- Use `fn main()` as entry point (NOT `def main()` - this is required for Mojo v0.26.1)
- Use `print()` for output (NOT `print_string()`)
- Ensure code passes `mojo build` without errors or warnings
- Ensure code passes `mojo format` with no changes required
- Follow ownership patterns (`out self`, `mut self`, etc.)
- No deprecated patterns (`inout`, `@value`, `DynamicVector`)

## Expected Output

When running the example:
```
Hello, world
```

## Success Criteria

- Example discovered proper location in repository
- Code compiles with `mojo build` (zero errors/warnings)
- Code passes `mojo format` with no changes required
- Code compiles with `bazel build` if Bazel is used
- Running the example prints "Hello, world"
- Exit code is 0
- Module docstring present
- README updated or created as appropriate

**IMPORTANT**: Explore the repository structure first to understand where
examples should be placed. Follow existing conventions.
