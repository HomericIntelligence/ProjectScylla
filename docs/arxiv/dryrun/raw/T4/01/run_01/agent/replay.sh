#!/bin/bash
# Generated: 2026-01-20T06:13:16.678174+00:00
# Total commands: 1
#
# This script executes commands for the test run.
# All output is captured to stdout/stderr logs.
#
set -e  # Exit on first error
set -x  # Print commands as they execute

# Environment variables (secrets redacted)
# Uncomment and fill in as needed:
# export ANTHROPIC_API_KEY='your-anthropic-api-key-here'
# export OPENAI_API_KEY='your-openai-api-key-here'

# Commands

# Command 1/1 at 2026-01-20T06:13:16.678008+00:00
# Duration: 0.00s, Exit: 0
cd /home/mvillmow/fullruns/test001-dryrun/2026-01-20T06-13-07-test-001/T4/01/run_01/workspace
claude --model claude-sonnet-4-5-20250929 --print --output-format json --dangerously-skip-permissions /home/mvillmow/fullruns/test001-dryrun/2026-01-20T06-13-07-test-001/T4/01/run_01/agent/prompt.md
