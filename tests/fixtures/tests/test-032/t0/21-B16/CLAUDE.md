## Repository Architecture

### Project Structure

```text
ProjectOdyssey/
├── agents/                      # Team documentation
│   ├── README.md                # Quick start guide
│   ├── hierarchy.md             # Visual hierarchy diagram
│   ├── agent-hierarchy.md       # Agent specifications
│   ├── delegation-rules.md      # Coordination patterns
│   └── templates/               # Agent configuration templates
├── notes/
│   └── review/                  # Comprehensive specs & decisions
│       ├── agent-architecture-review.md
│       ├── skills-design.md
│       └── orchestration-patterns.md
├── scripts/                     # Python automation scripts
├── logs/                        # Execution logs and state files
└── .clinerules                 # Claude Code conventions
```

### Planning Hierarchy

**4 Levels** (managed through GitHub issues):

1. **Section** (e.g., 01-foundation) - Major area of work
1. **Subsection** (e.g., 01-directory-structure) - Logical grouping
1. **Component** (e.g., 01-create-papers-dir) - Specific deliverable
1. **Subcomponent** (e.g., 01-create-base-dir) - Atomic task

All planning documentation is tracked in GitHub issues. Use `gh issue view <number>` to read plans.

### Documentation Organization

The repository uses three separate locations for documentation to avoid duplication:

#### 1. Team Documentation (`/agents/`)

**Purpose**: Quick start guides, visual references, and templates for team onboarding.

### Contents

- Quick start guides (README.md)
- Visual diagrams (hierarchy.md)
- Quick reference cards (delegation-rules.md)
- Configuration templates (templates/)

**When to Use**: Creating new documentation for team onboarding or quick reference.

#### 2. Developer Documentation (`/docs/dev/`)

**Purpose**: Detailed architectural decisions, comprehensive specifications, and design documents.

### Contents

- Mojo patterns and error handling (mojo-test-failure-patterns.md)
- Skills architecture (skills-design.md, skills-architecture.md)
- Orchestration patterns (orchestration-patterns.md)
- Backward pass catalog (backward-pass-catalog.md)

**When to Use**: Writing detailed specifications, architectural decisions, or comprehensive guides.

#### 3. Issue-Specific Documentation (GitHub Issue Comments)

**Purpose**: Implementation notes, findings, and decisions specific to a single GitHub issue.

**Location**: Post directly to the GitHub issue as comments using `gh issue comment`.

**Reading Issue Context**:

```bash
# Get issue details and body
gh issue view <number>

# Get all comments (implementation history)
gh issue view <number> --comments

# Get structured data
gh issue view <number> --json title,body,comments,labels,state
```

**Writing to Issues**:

```bash
# Post implementation notes
gh issue comment <number> --body "$(cat <<'EOF'
## Implementation Notes

### Summary
[What was implemented]

### Files Changed
- path/to/file.mojo

### Verification
- [x] Tests pass
EOF
)"
```

### Important Rules

- ✅ DO: Post issue-specific findings and decisions as comments
- ✅ DO: Link to comprehensive docs in `/agents/` and `/docs/dev/`
- ✅ DO: Reference related issues with `#<number>` format
- ❌ DON'T: Duplicate comprehensive documentation
- ❌ DON'T: Create local files for issue tracking

### 5-Phase Development Workflow

Every component follows a hierarchical workflow with clear dependencies:

**Workflow**: Plan → [Test | Implementation | Package] → Cleanup

1. **Plan** - Design and documentation (MUST complete first)
1. **Test** - Write tests following TDD (parallel after Plan)
1. **Implementation** - Build the functionality (parallel after Plan)
1. **Package** - Create distributable packages (parallel after Plan)
   - Build binary packages (`.mojopkg` files for Mojo modules)
   - Create distribution archives (`.tar.gz`, `.zip` for tooling/docs)
   - Configure package metadata and installation procedures
   - Add components to existing packages
   - Test package installation in clean environments
   - Create CI/CD packaging workflows
   - **NOT just documenting** - must create actual distributable artifacts
1. **Cleanup** - Refactor and finalize (runs after parallel phases complete)

### Key Points

- Plan phase produces specifications for all other phases
- Test/Implementation/Package can run in parallel after Plan completes
- Cleanup collects issues discovered during the parallel phases
- Each phase has a separate GitHub issue with detailed instructions
