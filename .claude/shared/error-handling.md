# Error Handling

Shared error handling protocols for all agents. Reference this file instead of duplicating.

## Retry Strategy

### Default Retry Configuration

- **Max Retries**: 3 attempts
- **Backoff**: Exponential (1s, 2s, 4s)
- **Timeout**: 5 minutes per operation

### When to Retry

**DO Retry:**

- Transient network errors
- API rate limits (with backoff)
- Temporary service unavailability
- Timeout errors (with increased timeout)

**DO NOT Retry:**

- Authentication failures
- Invalid input errors
- Permission denied errors
- Resource not found (404)

### Retry Implementation

```python
import time
from functools import wraps

def retry_with_backoff(max_retries=3, base_delay=1):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (TimeoutError, ConnectionError) as e:
                    if attempt == max_retries - 1:
                        raise
                    delay = base_delay * (2 ** attempt)
                    time.sleep(delay)
            return func(*args, **kwargs)
        return wrapper
    return decorator
```

## Timeout Handling

### Default Timeouts

| Operation | Timeout | Notes |
|-----------|---------|-------|
| API Call | 60s | Single LLM request |
| Benchmark Run | 5min | Full benchmark execution |
| Analysis | 2min | Statistical analysis |
| CI Check | 10min | Full CI pipeline |

### Timeout Escalation

```text
1. Operation times out
2. Log timeout with context
3. Retry with 2x timeout (up to max)
4. If still failing, escalate to supervisor
```

## Conflict Resolution

### File Conflicts

```bash
# Check for conflicts
git status

# If conflicts exist
git diff --name-only --diff-filter=U

# Resolution strategy
1. Review conflicting changes
2. Determine correct resolution
3. Edit files to resolve
4. git add <resolved-files>
5. git commit
```

### API Conflicts

When multiple agents access the same resource:

1. Use optimistic locking where available
2. Implement retry with jitter
3. Escalate if conflicts persist

## Failure Modes

### Partial Failure

**Definition**: Some operations succeed, others fail

**Handling**:

1. Document what succeeded
2. Document what failed
3. Determine if partial results are usable
4. Escalate decision to supervisor if unclear

### Complete Failure

**Definition**: All operations fail

**Handling**:

1. Capture detailed error information
2. Check for systematic issues (auth, network)
3. Document failure context
4. Escalate immediately

### Blocking Failure

**Definition**: Failure prevents progress on dependent tasks

**Handling**:

1. Identify all blocked tasks
2. Attempt workarounds if available
3. Escalate to supervisor with impact assessment
4. Continue with non-blocked work

## Loop Detection

### Detecting Infinite Loops

Watch for these patterns:

- Same error occurring more than 5 times
- Same fix being applied repeatedly
- Circular dependencies in tasks

### Breaking Loops

```text
1. Stop current operation
2. Document loop pattern
3. Escalate to supervisor
4. Await new instructions
```

## Escalation Triggers

### Immediate Escalation Required

- Security-related failures
- Data loss or corruption
- Repeated failures (> 3 consecutive)
- Unknown error types
- Cost overruns (> 2x expected)

### Escalation Template

```markdown
## Escalation Report

**Agent**: [Your Name]
**Date**: [YYYY-MM-DD HH:MM]
**Severity**: [Low/Medium/High/Critical]

### Issue Summary
[1-2 sentence description]

### Error Details
- Error Type: [Type]
- Error Message: [Message]
- Context: [What was being done]

### Attempts Made
1. [Attempt 1]
2. [Attempt 2]
3. [Attempt 3]

### Impact
- Blocked tasks: [List]
- Estimated cost: [If applicable]

### Recommended Action
[Your recommendation]
```

## Error Reporting Format

### Structured Error Report

```markdown
## Error Report

### Summary
[Brief description of error]

### Technical Details
- **Error Type**: [Exception class or error code]
- **Error Message**: [Full error message]
- **Stack Trace**: [If available]
- **Timestamp**: [When it occurred]

### Context
- **Operation**: [What was being done]
- **Input**: [Relevant input data]
- **Environment**: [Python version, dependencies]

### Resolution
- **Status**: [Resolved/Pending/Escalated]
- **Action Taken**: [What was done]
- **Result**: [Outcome]
```

## Evaluation-Specific Error Handling

### API Rate Limits

LLM APIs often have rate limits. Handle appropriately:

```python
# Respect rate limits
if response.status_code == 429:
    retry_after = int(response.headers.get('Retry-After', 60))
    time.sleep(retry_after)
    # Retry request
```

### Token Budget Exceeded

If evaluation exceeds token budget:

1. Stop current evaluation
2. Document partial results
3. Report actual vs. budgeted tokens
4. Escalate for budget approval

### Invalid Benchmark Results

If results appear invalid (e.g., 100% pass rate, negative costs):

1. Do NOT report invalid results
2. Investigate root cause
3. Re-run benchmark if data collection issue
4. Escalate if systematic problem
