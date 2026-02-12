"""OpenCode CLI adapter.

This module provides an adapter for running the OpenCode CLI
within the Scylla evaluation framework.
KNOWN ISSUE: This adapter shares ~80% code with openai_codex.py and cline.py
See GitHub Issue #479 - Consolidate copy-paste CLI adapters (DRY violation)
TODO: Extract shared logic into BaseCliAdapter to eliminate duplication
"""

from __future__ import annotations

import re
import subprocess
from datetime import datetime, timezone
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


class OpenCodeAdapter(BaseAdapter):
    """Adapter for OpenCode CLI.

    Executes the OpenCode CLI with the specified configuration and
    captures output, token counts, and metrics.

    Example:
        >>> adapter = OpenCodeAdapter()
        >>> config = AdapterConfig(
        ...     model="gpt-4",
        ...     prompt_file=Path("prompt.md"),
        ...     workspace=Path("/workspace"),
        ...     output_dir=Path("/output"),
        ... )
        >>> result = adapter.run(config)
        >>> print(f"Exit code: {result.exit_code}")

    """

    # OpenCode CLI executable
    CLI_EXECUTABLE = "opencode"

    def run(
        self,
        config: AdapterConfig,
        tier_config: TierConfig | None = None,
    ) -> AdapterResult:
        """Execute OpenCode CLI with the given configuration.

        Args:
            config: Adapter configuration with model, prompt, workspace, etc.
            tier_config: Optional tier-specific configuration for prompt injection.

        Returns:
            AdapterResult with execution details.

        Raises:
            AdapterError: If execution fails.

        """
        self.validate_config(config)

        # Load and potentially inject tier prompt
        task_prompt = self.load_prompt(config.prompt_file)
        final_prompt = self.inject_tier_prompt(task_prompt, tier_config)

        # Build CLI command
        cmd = self._build_command(config, final_prompt, tier_config)

        # Prepare environment with API keys
        env = self._prepare_env(config)

        # Execute
        start_time = datetime.now(timezone.utc)
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
            end_time = datetime.now(timezone.utc)
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
            raise AdapterError(f"OpenCode CLI not found. Is '{self.CLI_EXECUTABLE}' installed?")

        except subprocess.SubprocessError as e:
            raise AdapterError(f"Failed to execute OpenCode: {e}") from e

        end_time = datetime.now(timezone.utc)
        duration = (end_time - start_time).total_seconds()

        # Parse output for metrics
        tokens_input, tokens_output = self._parse_token_counts(result.stdout, result.stderr)
        api_calls = self._parse_api_calls(result.stdout, result.stderr)

        # Create token stats (OpenCode doesn't provide cache info, so only basic stats)
        token_stats = AdapterTokenStats(
            input_tokens=tokens_input,
            output_tokens=tokens_output,
        )

        # Calculate cost
        cost = self.calculate_cost(tokens_input, tokens_output, config.model)

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
    ) -> list[str]:
        """Build the OpenCode CLI command.

        Args:
            config: Adapter configuration.
            prompt: The prompt to send (with tier injection if applicable).
            tier_config: Tier configuration for tool/delegation settings.

        Returns:
            Command as list of strings.

        """
        cmd = [
            self.CLI_EXECUTABLE,
            "--model",
            config.model,
            "--batch",  # Non-interactive batch mode
        ]

        # Apply tier settings
        tier_settings = self.get_tier_settings(tier_config)

        # Disable tools if explicitly set to False
        if tier_settings["tools_enabled"] is False:
            cmd.append("--no-tools")

        # Add extra arguments from config
        if config.extra_args:
            cmd.extend(config.extra_args)

        # Add the prompt using stdin flag
        cmd.extend(["--message", prompt])

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

    def _parse_token_counts(self, stdout: str, stderr: str) -> tuple[int, int]:
        """Parse token counts from OpenCode output.

        Looks for patterns like:
        - "tokens: N in, M out"
        - "input_tokens: N, output_tokens: M"
        - Standard "Input tokens: N" format

        Args:
            stdout: Standard output from CLI.
            stderr: Standard error from CLI.

        Returns:
            Tuple of (input_tokens, output_tokens).

        """
        combined = stdout + "\n" + stderr
        input_tokens = 0
        output_tokens = 0

        # Pattern: "tokens: N in, M out"
        tokens_match = re.search(
            r"tokens?:?\s*(\d+)\s*in\s*[,/]\s*(\d+)\s*out",
            combined,
            re.IGNORECASE,
        )
        if tokens_match:
            input_tokens = int(tokens_match.group(1))
            output_tokens = int(tokens_match.group(2))
            return input_tokens, output_tokens

        # Pattern: "input_tokens: N" and "output_tokens: M"
        input_match = re.search(r"input_tokens?:?\s*(\d+)", combined, re.IGNORECASE)
        if input_match:
            input_tokens = int(input_match.group(1))

        output_match = re.search(r"output_tokens?:?\s*(\d+)", combined, re.IGNORECASE)
        if output_match:
            output_tokens = int(output_match.group(1))

        if input_tokens > 0 or output_tokens > 0:
            return input_tokens, output_tokens

        # Pattern: "N input, M output" or similar
        combined_match = re.search(
            r"(\d+)\s*(?:input|in)\s*[,/]\s*(\d+)\s*(?:output|out)",
            combined,
            re.IGNORECASE,
        )
        if combined_match:
            input_tokens = int(combined_match.group(1))
            output_tokens = int(combined_match.group(2))

        # Pattern: "Total: N tokens (X input, Y output)"
        total_match = re.search(
            r"\((\d+)\s*input,\s*(\d+)\s*output\)",
            combined,
            re.IGNORECASE,
        )
        if total_match:
            input_tokens = int(total_match.group(1))
            output_tokens = int(total_match.group(2))

        return input_tokens, output_tokens

    def _parse_api_calls(self, stdout: str, stderr: str) -> int:
        """Parse API call count from output.

        Args:
            stdout: Standard output from CLI.
            stderr: Standard error from CLI.

        Returns:
            Number of API calls detected.

        """
        combined = stdout + "\n" + stderr

        # Pattern: "API calls: N" or "N API calls"
        match = re.search(
            r"(?:API\s+calls?:?\s*(\d+)|(\d+)\s+API\s+calls?)",
            combined,
            re.IGNORECASE,
        )
        if match:
            return int(match.group(1) or match.group(2))

        # Count completion markers
        completion_count = len(re.findall(r"(?:completion|response):", combined, re.IGNORECASE))
        if completion_count > 0:
            return completion_count

        # Default: assume at least 1 call if there's meaningful output
        if len(stdout.strip()) > 100:
            return 1

        return 0
