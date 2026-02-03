## Claude 4 & Claude Code Optimization

This section provides guidance on optimizing interactions with Claude 4 (Sonnet and Opus) and
Claude Code features including extended thinking, agent skills, sub-agents, hooks, and output
styles.

### Extended Thinking

**When to Use Extended Thinking**: Claude 4 models support extended thinking for complex
reasoning tasks. Use extended thinking when:

- Analyzing complex codebases or architectural decisions
- Debugging multi-layered issues with unclear root causes
- Planning multi-step refactoring or migrations
- Evaluating tradeoffs between multiple design approaches
- Reasoning about edge cases and failure modes

**When NOT to Use Extended Thinking**:

- Simple CRUD operations or boilerplate code
- Well-defined tasks with clear specifications
- Repetitive tasks (formatting, linting, etc.)
- Tasks with clear step-by-step instructions already provided

**Example - Extended Thinking for Architecture Analysis**:

```markdown
Task: Analyze the tradeoffs between implementing tensor operations as struct methods vs standalone
functions in Mojo.

Extended thinking helps here because:
- Multiple design patterns to evaluate (OOP vs functional)
- Mojo-specific ownership and lifetime considerations
- Performance implications (inlining, SIMD optimization)
- API ergonomics and consistency with stdlib
```

**Example - Skip Extended Thinking for Boilerplate**:

```markdown
Task: Add a new test file following the existing test pattern in tests/shared/core/test_tensor.mojo

Skip extended thinking because:
- Clear pattern already established
- Straightforward copy-paste-modify workflow
- No architectural decisions needed
```

### Thinking Budget Guidelines

Extended thinking consumes tokens. Use appropriate budgets based on task complexity:

| Task Type | Budget | Examples | Rationale |
|-----------|--------|----------|-----------|
| **Simple** | None | Fix typo | Mechanical changes |
| **Standard** | 5K-10K | Add test, function | Well-defined |
| **Complex** | 10K-20K | Restructure, migrate | Dependencies |
| **Architecture** | 20K-50K | Design pattern | Deep analysis |
| **System-wide** | 50K+ | CI failures | Root cause |

**Budget Conservation Tips**:

1. **Provide context upfront** - Include relevant file contents, error messages, and constraints
2. **Break down complex tasks** - Split large problems into smaller, focused subtasks
3. **Use examples** - Show expected patterns rather than describing them
4. **Reference existing code** - Point to similar implementations as templates
