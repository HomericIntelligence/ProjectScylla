# Adapter Interface Specification

This document defines the contract for adapters that run AI agents within the Scylla evaluation framework.

## Overview

Adapters are the bridge between the Scylla test runner and specific AI agent implementations. Each adapter is responsible for:

1. Receiving test configuration from the runner
2. Executing the agent with appropriate settings
3. Capturing all outputs (stdout, stderr, agent logs)
4. Recording metrics (tokens, cost, timing)
5. Returning the execution result

## Adapter Contract

### Input Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `model` | `str` | Yes | Model identifier (e.g., "claude-sonnet-4-5-20250929") |
| `prompt_file` | `Path` | Yes | Path to the prompt markdown file |
| `workspace` | `Path` | Yes | Working directory for the agent |
| `output_dir` | `Path` | Yes | Directory for logs and metrics output |
| `config` | `dict` | Yes | Merged configuration from tier and test |
| `timeout` | `int` | Yes | Maximum execution time in seconds |

### Configuration Dictionary

The `config` parameter contains merged settings from the tier configuration and test definition:

```python
config = {
    # Tier settings
    "tier_id": "T1",
    "tier_name": "Prompted",
    "tier_prompt": "Think step by step...",  # May be None for T0
    "tools_enabled": False,
    "delegation_enabled": False,

    # Test settings
    "test_id": "justfile-001",
    "task_description": "Convert Justfile to Makefile",

    # Environment
    "api_keys": {
        "ANTHROPIC_API_KEY": "...",
    },
}
```

### Output Files

Adapters must write the following files to `output_dir`:

| File | Format | Description |
|------|--------|-------------|
| `stdout.log` | Text | Captured standard output from the agent |
| `stderr.log` | Text | Captured standard error |
| `agent.log` | Text | Agent interaction log (tool calls, reasoning) |
| `metrics.json` | JSON | Execution metrics (see schema below) |

### metrics.json Schema

```json
{
  "tokens_input": 45230,
  "tokens_output": 12456,
  "tokens_total": 57686,
  "cost_usd": 1.23,
  "api_calls": 15,
  "duration_seconds": 847.2,
  "exit_code": 0,
  "error": null,
  "started_at": "2024-01-15T14:30:00Z",
  "ended_at": "2024-01-15T14:44:07Z"
}
```

### Return Value

The adapter's `run()` method returns the process exit code:

- `0`: Agent completed successfully
- Non-zero: Agent failed or encountered an error

## Base Adapter Interface

All adapters must inherit from `BaseAdapter`:

```python
from abc import ABC, abstractmethod
from pathlib import Path


class BaseAdapter(ABC):
    """Base class for all agent adapters."""

    @abstractmethod
    def run(
        self,
        model: str,
        prompt_file: Path,
        workspace: Path,
        output_dir: Path,
        config: dict,
        timeout: int,
    ) -> int:
        """Execute agent and return exit code.

        Args:
            model: Model identifier.
            prompt_file: Path to prompt markdown file.
            workspace: Working directory for agent.
            output_dir: Directory for logs and metrics.
            config: Merged configuration dictionary.
            timeout: Maximum execution time in seconds.

        Returns:
            Exit code (0 = success, non-zero = failure).
        """
        ...

    def get_name(self) -> str:
        """Return adapter name for logging."""
        return self.__class__.__name__

    def validate_config(self, config: dict) -> bool:
        """Validate configuration before execution.

        Override to add adapter-specific validation.

        Args:
            config: Configuration dictionary.

        Returns:
            True if valid, raises ValueError otherwise.
        """
        return True
```

## Adapter Implementations

### Claude Code Adapter

For running Claude Code CLI:

```python
class ClaudeCodeAdapter(BaseAdapter):
    """Adapter for Claude Code CLI."""

    def run(
        self,
        model: str,
        prompt_file: Path,
        workspace: Path,
        output_dir: Path,
        config: dict,
        timeout: int,
    ) -> int:
        # Build command
        cmd = [
            "claude",
            "--model", model,
            "--prompt", str(prompt_file),
            "--cwd", str(workspace),
        ]

        # Apply tier settings
        if config.get("tier_prompt"):
            cmd.extend(["--system-prompt", config["tier_prompt"]])

        if not config.get("tools_enabled", True):
            cmd.append("--no-tools")

        # Execute with capture
        with StreamingCapture(output_dir) as capture:
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=timeout,
            )
            capture.write_stdout(result.stdout)
            capture.write_stderr(result.stderr)
            capture.set_exit_code(result.returncode)

        return result.returncode
```

### API Direct Adapter

For direct API calls without a CLI:

```python
class APIDirectAdapter(BaseAdapter):
    """Adapter for direct API calls."""

    def run(
        self,
        model: str,
        prompt_file: Path,
        workspace: Path,
        output_dir: Path,
        config: dict,
        timeout: int,
    ) -> int:
        import anthropic

        client = anthropic.Anthropic()

        # Load prompt
        prompt = prompt_file.read_text()

        # Build messages
        messages = [{"role": "user", "content": prompt}]

        # Add tier system prompt if present
        system = config.get("tier_prompt")

        with StreamingCapture(output_dir) as capture:
            try:
                response = client.messages.create(
                    model=model,
                    max_tokens=4096,
                    system=system,
                    messages=messages,
                )

                # Capture output
                output = response.content[0].text
                capture.write_stdout(output)

                # Record metrics
                capture.update_metrics(
                    tokens_input=response.usage.input_tokens,
                    tokens_output=response.usage.output_tokens,
                    api_calls=1,
                )

                return 0

            except Exception as e:
                capture.write_stderr(str(e))
                capture.set_error(str(e))
                return 1
```

### Aider Adapter

For running Aider coding assistant:

```python
class AiderAdapter(BaseAdapter):
    """Adapter for Aider coding assistant."""

    def run(
        self,
        model: str,
        prompt_file: Path,
        workspace: Path,
        output_dir: Path,
        config: dict,
        timeout: int,
    ) -> int:
        cmd = [
            "aider",
            "--model", model,
            "--message-file", str(prompt_file),
            "--yes",  # Non-interactive
        ]

        with StreamingCapture(output_dir) as capture:
            result = subprocess.run(
                cmd,
                cwd=workspace,
                capture_output=True,
                timeout=timeout,
            )
            capture.write_stdout(result.stdout.decode())
            capture.write_stderr(result.stderr.decode())
            capture.set_exit_code(result.returncode)

        return result.returncode
```

## Adding New Adapters

To add a new adapter:

1. **Create the adapter class**:
   ```bash
   # Create file
   touch scylla/adapters/my_adapter.py
   ```

2. **Implement BaseAdapter**:
   ```python
   from scylla.adapters.base import BaseAdapter

   class MyAdapter(BaseAdapter):
       def run(self, model, prompt_file, workspace, output_dir, config, timeout):
           # Implementation here
           ...
   ```

3. **Register the adapter**:
   ```python
   # In scylla/adapters/__init__.py
   from .my_adapter import MyAdapter

   ADAPTERS = {
       "claude-code": ClaudeCodeAdapter,
       "api-direct": APIDirectAdapter,
       "aider": AiderAdapter,
       "my-adapter": MyAdapter,  # Add here
   }
   ```

4. **Add tests**:
   ```python
   # In tests/unit/adapters/test_my_adapter.py
   def test_my_adapter_basic():
       adapter = MyAdapter()
       result = adapter.run(...)
       assert result == 0
   ```

## Best Practices

### Error Handling

- Catch and log all exceptions
- Write error details to stderr.log
- Set appropriate exit codes
- Include stack traces in error messages

### Timeout Handling

```python
try:
    result = subprocess.run(cmd, timeout=timeout)
except subprocess.TimeoutExpired:
    # Kill the process
    # Write timeout to stderr
    capture.write_stderr(f"Timeout after {timeout} seconds")
    capture.set_error("Execution timeout")
    return 124  # Standard timeout exit code
```

### Metric Collection

- Record token counts from API responses
- Calculate cost using model pricing
- Track API call count for rate limit analysis
- Measure actual execution time (not timeout)

### Log Streaming

- Write logs incrementally (not at end)
- Flush after each write
- Handle large outputs gracefully
- Don't hold entire output in memory

## Configuration Reference

### Tier-Specific Settings

| Setting | T0 | T1 | T2 | T3+ |
|---------|----|----|----|----|
| `tier_prompt` | None | CoT prompt | Domain skills | Full prompt |
| `tools_enabled` | Default | False | False | True |
| `delegation_enabled` | Default | False | False | True |

### Environment Variables

Adapters should expect these environment variables in Docker containers:

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `TIER` | Current tier ID (T0, T1, etc.) |
| `MODEL` | Model identifier |
| `RUN_NUMBER` | Run number (01-10) |

## Testing Adapters

### Unit Tests

Test the adapter in isolation:

```python
def test_adapter_validates_config():
    adapter = MyAdapter()
    with pytest.raises(ValueError):
        adapter.validate_config({})  # Missing required fields


def test_adapter_creates_output_files():
    with TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        adapter = MyAdapter()
        adapter.run(
            model="test-model",
            prompt_file=Path("test.md"),
            workspace=Path("."),
            output_dir=output_dir,
            config={},
            timeout=60,
        )
        assert (output_dir / "stdout.log").exists()
        assert (output_dir / "metrics.json").exists()
```

### Integration Tests

Test with actual Docker containers:

```python
@pytest.mark.integration
def test_adapter_in_container():
    executor = DockerExecutor()
    # Run adapter in container
    # Verify output files
    # Check metrics accuracy
```

## Related Documentation

- [Test Runner](./test-runner.md) - How adapters are invoked
- [Tier Configuration](./tier-config.md) - Tier settings passed to adapters
- [Metrics Schema](./metrics-schema.md) - Full metrics specification
