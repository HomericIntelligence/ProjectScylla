# Extended Thinking Investigation

**Issue**: #155 - Agent output missing extended thinking capture
**Date**: 2026-01-08
**Status**: Investigation Complete

## Summary

Extended thinking in Claude API requires explicit configuration not currently exposed through the Claude Code CLI.

## Findings

### How Extended Thinking Works

According to Anthropic's documentation, extended thinking must be **explicitly enabled** in API requests:

1. **Configuration**: Add a `thinking` object to the API request with:
   - `type: "enabled"`
   - `budget_tokens`: Maximum tokens for reasoning (minimum 1,024)

2. **Response Format**: API returns content blocks:
   - `type: "thinking"` - Internal reasoning process
   - `type: "text"` - Final answer

3. **Model Support**:
   - Currently: Sonnet 4.5, Haiku 4.5, Opus 4.5
   - Coming Jan 15, 2026: Opus 4, Opus 4.1, Sonnet 4

### Claude CLI Limitations

**Investigation of Claude CLI** (`claude --help`):
- No `--thinking` or `--extended-thinking` flag available
- No `--budget-tokens` or similar configuration
- Current flags: `--model`, `--output-format`, `--print`, etc.

**Conclusion**: The Claude Code CLI does not currently expose extended thinking configuration.

## Current Implementation

**File**: `src/scylla/adapters/claude_code.py`

The adapter uses:
```python
cmd = [
    "claude",
    "--model", config.model,
    "--print",
    "--output-format", "json",
    "--dangerously-skip-permissions",
]
```

**Already captured**:
- Full stdout (including JSON response)
- Full stderr
- Token statistics
- Cost metrics

**What's missing**:
- Explicit thinking blocks (requires API-level configuration)

## Alternatives

### Option 1: Wait for CLI Support
Monitor Claude CLI updates for extended thinking flags.

### Option 2: Direct API Calls
Modify the adapter to use Anthropic Python SDK for direct API calls:

```python
from anthropic import Anthropic

client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
response = client.messages.create(
    model="claude-sonnet-4-5-20250929",
    max_tokens=1024,
    thinking={
        "type": "enabled",
        "budget_tokens": 5000
    },
    messages=[{"role": "user", "content": prompt}]
)

# Extract thinking blocks
thinking_blocks = [
    block.thinking
    for block in response.content
    if block.type == "thinking"
]
```

### Option 3: Feature Request
Request extended thinking support from Claude CLI team.

## Recommendation

**For Issue #155**: Document the limitation and close with:
- Extended thinking requires API-level configuration
- Not currently supported by Claude CLI
- Can be implemented via direct API calls (Option 2) if needed

**Priority**: LOW - Current implementation captures all available CLI output. Extended thinking would require architectural change (CLI → direct API calls).

## Sources

- [Building with extended thinking - Claude Docs](https://docs.anthropic.com/en/docs/build-with-claude/extended-thinking)
- [Extended thinking - Amazon Bedrock](https://docs.aws.amazon.com/bedrock/latest/userguide/claude-messages-extended-thinking.html)
- [How to Use Claude 4 extended thinking? - CometAPI](https://www.cometapi.com/how-to-use-claude-4-extended-thinking/)

## Related Issues

- #153: Reports show 0.000 (likely resolved by #152)
- #154: Judge output capture (fixed)
- #152: FileNotFoundError on resume (fixed)
