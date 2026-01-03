### Agentic Loop Patterns

Claude Code supports iterative exploration through agentic loops. Use this pattern for complex tasks:

#### Exploration → Planning → Execution

**Phase 1: Exploration** - Gather context and understand the problem:

```markdown
Exploration Tasks:
1. Read relevant documentation (CLAUDE.md, agent files, related issues)
2. Search for existing patterns (grep for similar implementations)
3. Identify constraints and requirements (compiler version, API patterns)
4. Review recent changes (git log, PR history)

Tools: Read, Grep, Glob, Bash (git log)
Output: Problem understanding, constraints, existing patterns
```

**Phase 2: Planning** - Design the solution:

```markdown
Planning Tasks:
1. Break down the problem into subtasks
2. Identify files to modify and create
3. Design interfaces and data structures
4. Plan verification steps (tests, linting, CI)

Tools: Extended thinking, structured reasoning
Output: Implementation plan, task breakdown, success criteria
```

**Phase 3: Execution** - Implement the solution:

```markdown
Execution Tasks:
1. Make code changes (Edit, Write)
2. Run verification (Bash: mojo test, pre-commit)
3. Fix errors iteratively (Read error output → Edit → Rerun)
4. Create PR and link to issue (gh-create-pr-linked skill)

Tools: Edit, Write, Bash, agent skills
Output: Working implementation, passing tests, merged PR
```

**Example - Agentic Loop for Issue #2549**:

```markdown
Iteration 1: Exploration
- Read CLAUDE.md to understand structure (Read tool)
- Search for existing Claude guidance (Grep "Claude|agent|skill")
- Review Issue #2549 requirements (gh issue view 2549)
- Read Claude 4 docs links (external URLs)
Output: Understand where to insert new section, what to include

Iteration 2: Planning
- Design section structure (6 subsections based on requirements)
- Identify insertion point (after "Working with Agents", before "Delegation")
- Plan examples (extended thinking, skills vs sub-agents, hooks)
- Define success criteria (markdown linting, cross-references, integration)
Output: Section outline, examples drafted, verification plan

Iteration 3: Execution
- Insert new section using Edit tool
- Add cross-references to existing sections
- Run markdown linting (just pre-commit-all)
- Fix any linting errors
- Create PR with "Closes #2549"
Output: Updated CLAUDE.md, passing linting, PR created

Iteration 4: Verification & Refinement
- Review generated content for accuracy
- Verify all examples use correct syntax
- Check cross-references point to real sections
- Confirm integration with existing content
- Enable auto-merge if CI passes
Output: PR ready for merge, issue resolved
```

**Key Principles**:

1. **Iterate, don't perfect upfront** - Start with exploration, refine through execution
2. **Fail fast** - Run verification early and often
3. **Learn from errors** - Each failure provides information for the next iteration
4. **Checkpoint progress** - Commit working states, even if incomplete
5. **Adapt the plan** - If exploration reveals new constraints, update the plan

**When to Use Agentic Loops**:

- ✅ Complex refactoring across multiple files
- ✅ Debugging issues with unclear root causes
- ✅ Implementing features with design tradeoffs
- ✅ Exploring unfamiliar codebases

**When NOT to Use Agentic Loops**:

- ❌ Simple, well-defined tasks (use direct execution)
- ❌ Boilerplate code generation (use templates/examples)
- ❌ Mechanical changes (formatting, renaming)

### Cross-References

- **Agent Skills**: See available skills in [Skill Delegation Patterns](#skill-delegation-patterns)
- **Sub-Agents**: See agent hierarchy in `/agents/hierarchy.md`
- **Hooks**: See error handling patterns in `.claude/shared/error-handling.md`
- **Extended Thinking**: Referenced in [Key Agent Principles](#key-agent-principles)
- **GitHub Workflow**: See `.claude/shared/github-issue-workflow.md` for issue/PR patterns
- **Tool Use**: See tool documentation in Claude Code docs

### Further Reading

- [Claude 4 Best Practices](<https://platform.claude.com/docs/en/build-with-claude/overview>)
- [Agent Skills Best Practices](<https://platform.claude.com/docs/en/agents-and-tools/claude-for-sheets>)
- [Sub-Agents Guide](<https://code.claude.com/docs/en/sub-agents>)
- [Output Styles](<https://code.claude.com/docs/en/output-styles>)
- [Hooks Guide](<https://code.claude.com/docs/en/hooks-guide>)
