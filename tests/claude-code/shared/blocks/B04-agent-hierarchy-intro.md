## Working with Agents

This project uses a hierarchical agent system for all development work. **Always use agents** as the primary
method for completing tasks.

### Agent Hierarchy

See [agents/hierarchy.md](agents/hierarchy.md) for the complete agent hierarchy including:

- 6-level hierarchy (L0 Chief Architect → L5 Junior Engineers)
- Model assignments (Opus, Sonnet, Haiku)
- All 44 agents with roles and responsibilities

### Key Agent Principles

1. **Always start with orchestrators** for new section work
1. **All outputs** must be posted as comments on the GitHub issue
1. **Link all PRs** to issues using `gh pr create --issue <number>` or "Closes #123" in description
1. **Minimal changes only** - smallest change that solves the problem
1. **No scope creep** - focus only on issue requirements
1. **Reply to each review comment** with `✅ Fixed - [brief description]`
1. **Delegate to skills** - Use "Use the X skill to..." pattern for automation
