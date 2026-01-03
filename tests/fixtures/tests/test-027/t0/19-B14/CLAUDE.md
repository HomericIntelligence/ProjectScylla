## Delegation to Agent Hub

.claude/ is the centralized location for agentic descriptions and SKILLs. Sub-agents reference
`.claude/agents/*.md` and `.claude/skills/*.md` for roles, capabilities, and prod fix learnings.

### Shared Reference Files

All agents and skills reference these shared files to avoid duplication:

| File | Purpose |
|------|---------|
| `.claude/shared/common-constraints.md` | Minimal changes principle, scope discipline |
| `.claude/shared/documentation-rules.md` | Output locations, before-starting checklist |
| `.claude/shared/pr-workflow.md` | PR creation, verification, review responses |
| `.claude/shared/mojo-guidelines.md` | Mojo v0.26.1+ syntax, parameter conventions |
| `.claude/shared/mojo-anti-patterns.md` | 64+ test failure patterns from PRs |
| `.claude/shared/error-handling.md` | Retry strategy, timeout handling, escalation |

### MCP Integration

**DEPRECATED**: GitHub MCP integration is being removed. Use `gh` CLI directly for all
GitHub operations to avoid token overhead.

Skills with `mcp_fallback` in YAML frontmatter will be updated to use direct CLI calls only.

### Mojo Development Guidelines

**Quick Reference**: See [mojo-guidelines.md](/.claude/shared/mojo-guidelines.md) for v0.26.1+ syntax

**Critical Patterns**:

- **Constructors**: Use `out self` (not `mut self`)
- **Mutating methods**: Use `mut self`
- **Ownership transfer**: Use `^` operator for List/Dict/String
- **List initialization**: Use literals `[1, 2, 3]` not `List[Int](1, 2, 3)`

**Common Mistakes**: See [mojo-anti-patterns.md](/.claude/shared/mojo-anti-patterns.md) for 64+ failure patterns

**Compiler as Truth**: When uncertain, test with `mojo build` - the compiler is authoritative

## Environment Setup

This project uses Pixi for environment management:

```bash
# Pixi is already configured - dependencies are in pixi.toml
# Mojo is the primary language target for future implementations
```
