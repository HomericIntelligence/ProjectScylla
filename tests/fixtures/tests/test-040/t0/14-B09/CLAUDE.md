### Agent Skills vs Sub-Agents

**Decision Tree**: Choose between skills and sub-agents based on task characteristics:

```text
Is the task well-defined with predictable steps?
├─ YES → Use an Agent Skill
│   ├─ Is it a GitHub operation? → Use gh-* skills
│   ├─ Is it a Mojo operation? → Use mojo-* skills
│   ├─ Is it a CI/CD task? → Use ci-* skills
│   └─ Is it a documentation task? → Use doc-* skills
│
└─ NO → Use a Sub-Agent
    ├─ Does it require exploration/discovery? → Use sub-agent
    ├─ Does it need adaptive decision-making? → Use sub-agent
    ├─ Is the workflow dynamic/context-dependent? → Use sub-agent
    └─ Does it need extended thinking? → Use sub-agent
```

**Agent Skills** - Use for automation with predictable workflows:

- **Characteristics**: Declarative YAML, fixed steps, composable, fast
- **Best for**: GitHub API calls, running tests, formatting code, CI workflows
- **Examples**: `gh-create-pr-linked`, `mojo-format`, `run-precommit`

**Sub-Agents** - Use for tasks requiring reasoning and adaptation:

- **Characteristics**: Full Claude instance, extended thinking, exploratory, slower
- **Best for**: Architecture decisions, debugging, code review, complex refactoring
- **Examples**: Documentation Engineer, Implementation Specialist, Review Engineer

**Example - When to Use a Skill**:

```markdown
Task: Create PR linked to issue #2549, run pixi run pre-commit hooks, enable auto-merge

✅ Use Agent Skills:
1. Use `gh-create-pr-linked` skill (predictable GitHub API workflow)
2. Use `run-precommit` skill (fixed command sequence)
3. Use `gh-check-ci-status` skill (polling with clear success/failure states)

Why skills work: Every step is well-defined, no exploration needed
```

**Example - When to Use a Sub-Agent**:

```markdown
Task: Review PR #2549 and suggest improvements to new Claude 4 documentation

✅ Use Sub-Agent (Review Engineer):
- Needs to read and understand the new documentation
- Compare against Claude's official documentation
- Evaluate clarity, completeness, and accuracy
- Provide actionable feedback with examples

Why sub-agent needed: Requires comprehension, judgment, adaptive reasoning
```

**Hybrid Approach** - Sub-agents can delegate to skills:

```markdown
Sub-Agent: Documentation Engineer implementing issue #2549

Workflow:
1. [Sub-agent] Read Claude 4 docs, analyze requirements, draft section
2. [Sub-agent] Use `doc-validate-markdown` skill to check formatting
3. [Sub-agent] Use `gh-create-pr-linked` skill to create PR
4. [Sub-agent] Use `ci-check-status` skill to verify CI passes
```
