# Task: Fix Docker CLI Installation

## Objective

Fix the Docker build failure caused by CLI tools (gh, claude) being installed after switching to a non-root user which requires sudo but has no password configured.

## Problem

Docker build is failing with:

```
sudo: a terminal is required to read the password
```

The GitHub CLI (`gh`) is being installed in the development stage after switching to the `dev` user, which requires sudo but has no password configured.

## Requirements

1. Move GitHub CLI installation to the base stage (runs as root)
2. Add Claude Code CLI installation
3. Add `$HOME/.local/bin` to PATH for Claude CLI access
4. Eliminate the need for sudo entirely

## Expected Output

- Modified `Dockerfile` with CLI installations in the root stage
- Both `gh` and `claude` CLIs accessible without sudo

## Success Criteria

- `docker build` completes successfully
- `gh --version` works in container
- `claude --version` works in container
- No sudo prompts during build
