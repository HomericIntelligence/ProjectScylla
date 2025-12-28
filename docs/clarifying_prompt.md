# ProjectScylla Implementation Plan Review

You are conducting a thorough review of the ProjectScylla agent testing framework plan. Your goal is to identify gaps, ambiguities, and areas requiring clarification before implementation begins.

## Context Files to Read First

1. `/home/mvillmow/ProjectScylla/docs/plan.md` - Implementation plan with issue links
2. `/home/mvillmow/.claude/plans/swift-skipping-creek.md` - Detailed 21-part plan
3. `/home/mvillmow/ProjectScylla/tests/001-justfile-to-makefile/` - First test case

## GitHub Issues to Review

Read each GitHub issue for implementation details using `gh issue view <number>`:

### Phase 1: Foundation

- #3 - Project structure and environment setup
- #4 - Configuration loading system
- #5 - Architecture documentation
- #6 - Test schema specification

### Phase 2: Execution Engine

- #7 - Workspace management
- #8 - Test runner orchestration (includes Docker/tier support)
- #9 - Log and metrics capture
- #10 - Adapter interface specification

### Phase 3: Adapters

- #11 - Base adapter class (includes tier configuration)
- #12 - Claude Code adapter
- #13 - OpenAI Codex adapter
- #14 - Cline adapter
- #15 - OpenCode adapter

### Phase 4: Judge System

- #16 - Rubric parser
- #17 - Judge prompt templates (includes 10 quality categories)
- #18 - Evaluator implementation (includes 3-run consensus)
- #19 - Judgment parser
- #20 - Judge protocol documentation
- #38 - Cleanup script evaluation

### Phase 5: Metrics and Statistics

- #21 - Statistical calculations
- #22 - Grading calculations
- #23 - 10-run aggregation (includes cross-tier support)
- #24 - Metrics formulas documentation
- #37 - Cross-tier analysis

### Phase 6: Reporting

- #25 - result.json writer
- #26 - summary.json generator
- #27 - scorecard.json generator
- #28 - Markdown report generator (includes tier comparison)

### Phase 7: CLI

- #29 - Command-line interface
- #30 - Progress display

### Phase 8: First Test Case

- #31 - Create 001-justfile-to-makefile test case (includes cleanup script)
- #32 - Validate framework with single run
- #33 - Execute full 10-run suite
- #34 - Generate first report

### Phase 9: Tier System

- #35 - Docker container orchestration
- #36 - Tier configuration system

---

## Review Methodology

For each phase, cross-reference the plan with the GitHub issues:

1. Read the issue with `gh issue view <number> --comments`
2. Compare issue details against plan sections
3. Identify inconsistencies, gaps, or missing details
4. Note any assumptions in the issue that aren't validated

---

### 1. Test Execution Model

**Reference Issues**: #7, #8, #9, #35

Questions to clarify:

- How exactly does the adapter invoke the agent CLI inside Docker?
- What environment variables are passed to the container?
- How is the tier-specific prompt injected (file mount, env var, CLI flag)?
- What happens if Docker is unavailable on the host?
- How are API keys/credentials passed securely to containers?
- What's the container resource limit (CPU, memory, disk)?
- How do we handle agents that require internet access vs air-gapped runs?

---

### 2. Tier System Specifics

**Reference Issues**: #36, #11, #8

Questions to clarify:

- What exactly goes in each tier prompt file (t1-prompted.md, t2-skills.md, t3-tooling.md)?
- For T0 (Vanilla), do we pass ANY prompt or literally nothing?
- For T3+ (Tooling), what tools are enabled? How are they configured?
- How do we ensure tier prompts are agent-agnostic (work with Claude Code, Cline, etc.)?
- Are tiers cumulative (T2 includes T1 content) or independent?

---

### 3. Judge System Details

**Reference Issues**: #16, #17, #18, #19, #20, #38

Questions to clarify:

- How does Claude Code + Opus 4.5 access the workspace for judging?
- What's the exact invocation command for the judge?
- How do we capture judge token usage and cost separately from agent runs?
- What if the judge fails or times out? Retry logic?
- How do we validate judge consistency across the 3 runs?
- What's the threshold for "too much disagreement" between judge runs?
- How does cleanup script evaluation integrate with overall scoring?

---

### 4. Metrics & Statistics

**Reference Issues**: #21, #22, #23, #24, #37

Questions to clarify:

- How do we handle runs that timeout or abort? Include in statistics or exclude?
- What's the minimum number of successful runs needed to report statistics?
- How do we calculate Cost-of-Pass when pass_rate is 0?
- Are there any metrics specific to certain tiers (e.g., T3+ tool call count)?
- How do we track token usage per component (agent vs judge vs orchestrator)?
- What statistical tests validate cross-tier differences are significant?

---

### 5. Adapter Interface

**Reference Issues**: #10, #11, #12, #13, #14, #15

Questions to clarify:

- What's the exact subprocess command for each adapter?
- How do adapters handle different prompt injection methods per agent CLI?
- What's the contract for adapter success vs failure?
- How do we detect if an agent "gave up" vs completed unsuccessfully?
- How do adapters capture structured output (if available) vs just logs?
- How does tier configuration affect adapter behavior?

---

### 6. First Test Case Specifics

**Reference Issues**: #31, #32, #33, #34

Questions to clarify:

- Is "justfile to Makefile" representative of the types of tests we'll run?
- What other test case categories are planned?
- How do we handle tests that require specific environments (GPU, database, etc.)?
- What's the expected difficulty distribution (easy/medium/hard tests)?
- What does the cleanup script requirement look like for this test?

---

### 7. Reporting & Output

**Reference Issues**: #25, #26, #27, #28

Questions to clarify:

- Who is the audience for reports (researchers, engineers, executives)?
- What visualization is needed (charts, graphs) or just tables?
- Should reports be versioned or timestamped?
- How do we handle comparing results across different time periods?
- Is there a dashboard or just static reports?
- How does the tier comparison section present statistical significance?

---

### 8. Operational Concerns

**Reference Issues**: #3, #4, #29, #30

Questions to clarify:

- How do we run this in CI/CD?
- What's the expected runtime for a full test suite?
- How do we handle partial failures (some tiers complete, others fail)?
- Is there a way to resume interrupted test runs?
- How do we manage storage for runs/ directory over time?
- What CLI commands are needed for different workflows?

---

### 9. Edge Cases & Error Handling

**Reference Issues**: #8, #9, #18, #35

Questions to clarify:

- What if an agent produces output but the workspace is corrupted?
- What if the cleanup script itself causes damage?
- How do we handle agents that try to escape the container?
- What if token counting differs between adapters?
- How do we handle model version changes mid-experiment?

---

### 10. Research Validity

**Reference Issues**: #37, #24, #20

Questions to clarify:

- How do we ensure reproducibility of results?
- What's the strategy for controlling for external factors (API latency, rate limits)?
- How do we document and version tier prompts for reproducibility?
- Is there a control group or baseline beyond T0?
- How do we handle the variance introduced by different models within the same adapter?

---

## Interview Approach

For each gap identified:

1. State the gap clearly
2. Reference which GitHub issue(s) it affects
3. Explain why it matters for implementation
4. Propose 2-3 possible solutions
5. Ask the user to choose or provide their preference

Group questions into batches of 3-4 related topics to avoid overwhelming the user.

---

## Output

After the interview:

1. Update `/home/mvillmow/ProjectScylla/docs/plan.md` with clarifications
2. Update `/home/mvillmow/.claude/plans/swift-skipping-creek.md` with new details
3. Create new GitHub issues for any newly identified work using `gh issue create`
4. Update existing issues with additional details using `gh issue edit`
5. Document all decisions with issue cross-references

---

## Commands Reference

```bash
# Read issue with comments
gh issue view <number> --comments

# Update issue body
gh issue edit <number> --body-file <file>

# Add comment to issue
gh issue comment <number> --body "..."

# Create new issue
gh issue create --title "..." --body "..." --label "..."

# List all issues
gh issue list --limit 50
```

---

Begin by reading all context files and GitHub issues, then start with the most critical gaps first.
