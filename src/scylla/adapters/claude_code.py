"""Claude Code CLI adapter.

This module provides an adapter for running the Claude Code CLI
within the Scylla evaluation framework.

Python Justification: Required for subprocess execution and output capture.
"""

from __future__ import annotations

import re
import subprocess
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from scylla.adapters.base import (
    AdapterConfig,
    AdapterError,
    AdapterResult,
    AdapterTokenStats,
    BaseAdapter,
)

if TYPE_CHECKING:
    from scylla.executor.tier_config import TierConfig


class ClaudeCodeAdapter(BaseAdapter):
    """Adapter for Claude Code CLI.

    Executes the Claude Code CLI with the specified configuration and
    captures output, token counts, and metrics.

    Example:
        >>> adapter = ClaudeCodeAdapter()
        >>> config = AdapterConfig(
        ...     model="claude-sonnet-4-5-20250929",
        ...     prompt_file=Path("prompt.md"),
        ...     workspace=Path("/workspace"),
        ...     output_dir=Path("/output"),
        ... )
        >>> result = adapter.run(config)
        >>> print(f"Exit code: {result.exit_code}")

    """

    # Claude Code CLI executable
    CLI_EXECUTABLE = "claude"

    def run(
        self,
        config: AdapterConfig,
        tier_config: TierConfig | None = None,
        system_prompt_mode: str = "default",
    ) -> AdapterResult:
        """Execute Claude Code CLI with the given configuration.

        Args:
            config: Adapter configuration with model, prompt, workspace, etc.
            tier_config: Optional tier-specific configuration for prompt injection.
            system_prompt_mode: How to handle system prompt:
                - "none": Use empty system prompt (T0 vanilla)
                - "default": Use Claude Code's built-in prompt (T1)
                - "custom": Let CLAUDE.md in workspace take effect (T2+)

        Returns:
            AdapterResult with execution details.

        Raises:
            AdapterError: If execution fails.
            AdapterTimeoutError: If execution times out.

        """
        self.validate_config(config)

        # Load and potentially inject tier prompt
        task_prompt = self.load_prompt(config.prompt_file)
        final_prompt = self.inject_tier_prompt(task_prompt, tier_config)

        # Build CLI command
        cmd = self._build_command(config, final_prompt, tier_config, system_prompt_mode)

        # Prepare environment with API keys
        env = self._prepare_env(config)

        # Execute
        start_time = datetime.now(UTC)
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=config.timeout,
                cwd=config.workspace,
                env=env,
            )

        except subprocess.TimeoutExpired as e:
            end_time = datetime.now(UTC)
            duration = (end_time - start_time).total_seconds()

            # Write logs even on timeout
            stdout = e.stdout.decode() if e.stdout else ""
            stderr = e.stderr.decode() if e.stderr else ""
            self.write_logs(config.output_dir, stdout, stderr)

            return AdapterResult(
                exit_code=-1,
                stdout=stdout,
                stderr=stderr,
                duration_seconds=duration,
                timed_out=True,
                error_message=f"Execution timed out after {config.timeout} seconds",
            )

        except FileNotFoundError:
            raise AdapterError(f"Claude Code CLI not found. Is '{self.CLI_EXECUTABLE}' installed?")

        except subprocess.SubprocessError as e:
            raise AdapterError(f"Failed to execute Claude Code: {e}") from e

        end_time = datetime.now(UTC)
        duration = (end_time - start_time).total_seconds()

        # Check for rate limit BEFORE parsing metrics
        # This ensures we detect and raise RateLimitError immediately
        from scylla.e2e.rate_limit import RateLimitError, detect_rate_limit

        rate_limit_info = detect_rate_limit(result.stdout, result.stderr, source="agent")
        if rate_limit_info:
            # Write logs before raising exception
            self.write_logs(config.output_dir, result.stdout, result.stderr)
            raise RateLimitError(rate_limit_info)

        # Parse output for metrics
        token_stats = self._parse_token_stats(result.stdout, result.stderr)
        api_calls = self._parse_api_calls(result.stdout, result.stderr)

        # Parse cost directly from JSON if available, otherwise calculate
        cost = self._parse_cost(result.stdout)
        if cost == 0.0 and (token_stats.input_tokens > 0 or token_stats.output_tokens > 0):
            # Use total input (including cache reads) for cost calculation
            total_input = token_stats.input_tokens + token_stats.cache_read_tokens
            cost = self.calculate_cost(total_input, token_stats.output_tokens, config.model)

        # Write logs
        self.write_logs(config.output_dir, result.stdout, result.stderr)

        return AdapterResult(
            exit_code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            duration_seconds=duration,
            token_stats=token_stats,
            cost_usd=cost,
            api_calls=api_calls,
            timed_out=False,
        )

    def _build_command(
        self,
        config: AdapterConfig,
        prompt: str,
        tier_config: TierConfig | None,
        system_prompt_mode: str = "default",
    ) -> list[str]:
        """Build the Claude Code CLI command.

        Args:
            config: Adapter configuration.
            prompt: The prompt to send (with tier injection if applicable).
            tier_config: Tier configuration for tool/delegation settings.
            system_prompt_mode: How to handle system prompt:
                - "none": Use empty system prompt (T0 vanilla)
                - "default": Use Claude Code's built-in prompt (T1)
                - "custom": Let CLAUDE.md in workspace take effect (T2+)

        Returns:
            Command as list of strings.

        """
        cmd = [
            self.CLI_EXECUTABLE,
            "--model",
            config.model,
            "--print",  # Print output to stdout
            "--output-format",
            "json",  # JSON output for structured parsing
            "--dangerously-skip-permissions",  # Non-interactive mode
        ]

        # Handle system prompt based on mode
        # T0: Remove built-in system prompt entirely
        if system_prompt_mode == "none":
            cmd.extend(["--system-prompt", ""])
        # T1 "default": Omit flag to use Claude Code's default
        # T2+ "custom": CLAUDE.md in workspace handles it

        # Apply tier settings
        tier_settings = self.get_tier_settings(tier_config)

        # Disable tools if explicitly set to False
        if tier_settings["tools_enabled"] is False:
            cmd.extend(["--tools", ""])

        # Add extra arguments from config
        if config.extra_args:
            cmd.extend(config.extra_args)

        # Add the prompt as the final argument
        cmd.append(prompt)

        return cmd

    def _prepare_env(self, config: AdapterConfig) -> dict[str, str]:
        """Prepare environment variables for subprocess.

        Args:
            config: Adapter configuration with env_vars.

        Returns:
            Environment dictionary.

        """
        import os

        env = os.environ.copy()
        env.update(config.env_vars)
        return env

    def _parse_token_stats(self, stdout: str, stderr: str) -> AdapterTokenStats:
        """Parse detailed token statistics from Claude Code output.

        Supports two formats:
        1. JSON output (preferred): Parses full usage object with cache tokens
        2. Text output (fallback): Regex patterns for basic token counts

        Args:
            stdout: Standard output from CLI.
            stderr: Standard error from CLI.

        Returns:
            AdapterTokenStats with all token types.

        """
        import json

        # Try JSON parsing first (from --output-format json)
        try:
            data = json.loads(stdout.strip())
            usage = data.get("usage", {})
            return AdapterTokenStats(
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
                cache_creation_tokens=usage.get("cache_creation_input_tokens", 0),
                cache_read_tokens=usage.get("cache_read_input_tokens", 0),
            )
        except (json.JSONDecodeError, AttributeError):
            pass

        # Fallback to regex parsing for text output
        combined = stdout + "\n" + stderr
        input_tokens = 0
        output_tokens = 0

        # Pattern: "Input tokens: 1234"
        input_match = re.search(r"input\s+tokens?:?\s*(\d+)", combined, re.IGNORECASE)
        if input_match:
            input_tokens = int(input_match.group(1))

        # Pattern: "Output tokens: 567"
        output_match = re.search(r"output\s+tokens?:?\s*(\d+)", combined, re.IGNORECASE)
        if output_match:
            output_tokens = int(output_match.group(1))

        # Pattern: "1234 input, 567 output" or similar
        combined_match = re.search(
            r"(\d+)\s*(?:input|in)\s*[,/]\s*(\d+)\s*(?:output|out)",
            combined,
            re.IGNORECASE,
        )
        if combined_match:
            input_tokens = int(combined_match.group(1))
            output_tokens = int(combined_match.group(2))

        # Pattern: "Total: 1801 tokens (1234 input, 567 output)"
        total_match = re.search(
            r"\((\d+)\s*input,\s*(\d+)\s*output\)",
            combined,
            re.IGNORECASE,
        )
        if total_match:
            input_tokens = int(total_match.group(1))
            output_tokens = int(total_match.group(2))

        # Fallback doesn't have cache info, return basic stats
        return AdapterTokenStats(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_creation_tokens=0,
            cache_read_tokens=0,
        )

    def _parse_api_calls(self, stdout: str, stderr: str) -> int:
        """Parse API call count from output.

        Args:
            stdout: Standard output from CLI.
            stderr: Standard error from CLI.

        Returns:
            Number of API calls detected.

        """
        import json

        # Try JSON parsing first (from --output-format json)
        try:
            data = json.loads(stdout.strip())
            # num_turns represents the number of API turn exchanges
            num_turns = data.get("num_turns", 0)
            if num_turns > 0:
                return num_turns
        except (json.JSONDecodeError, AttributeError):
            pass

        # Fallback to regex parsing for text output
        combined = stdout + "\n" + stderr

        # Pattern: "API calls: 5" or "5 API calls"
        match = re.search(
            r"(?:API\s+calls?:?\s*(\d+)|(\d+)\s+API\s+calls?)", combined, re.IGNORECASE
        )
        if match:
            return int(match.group(1) or match.group(2))

        # If no explicit count, estimate from output patterns
        # Count occurrences of typical API response markers
        response_markers = re.findall(r"(?:Response|Completion):", combined, re.IGNORECASE)
        if response_markers:
            return len(response_markers)

        # Default: assume at least 1 call if there's meaningful output
        if len(stdout.strip()) > 100:
            return 1

        return 0

    def _parse_cost(self, stdout: str) -> float:
        """Parse cost from JSON output.

        Args:
            stdout: Standard output from CLI (JSON format).

        Returns:
            Cost in USD, or 0.0 if not available.

        """
        import json

        try:
            data = json.loads(stdout.strip())
            return data.get("total_cost_usd", 0.0)
        except (json.JSONDecodeError, AttributeError):
            return 0.0
