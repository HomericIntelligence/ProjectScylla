"""Base CLI adapter for command-line agent implementations.

This module provides a base class for CLI-based adapters that share common
execution patterns, eliminating duplication across OpenAI Codex, OpenCode, and Cline.
"""

from __future__ import annotations

import re
import subprocess
from abc import abstractmethod
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


class BaseCliAdapter(BaseAdapter):
    """Base adapter for CLI-based agent implementations.

    Provides common implementation for subprocess execution, environment preparation,
    and API call parsing. Subclasses must implement:
    - CLI_EXECUTABLE: The command-line executable name
    - _build_command(): Build the CLI command with specific flags
    - _parse_token_counts(): Parse token counts from output

    Optionally, subclasses can define:
    - _api_call_fallback_pattern: Regex pattern for fallback API call detection

    Example:
        >>> class MyCliAdapter(BaseCliAdapter):
        ...     CLI_EXECUTABLE = "mycli"
        ...
        ...     def _build_command(self, config, prompt, tier_config):
        ...         return [self.CLI_EXECUTABLE, "--model", config.model, prompt]
        ...
        ...     def _parse_token_counts(self, stdout, stderr):
        ...         # Parse tokens from output
        ...         return (input_tokens, output_tokens)

    """

    # Subclasses must define the CLI executable name
    CLI_EXECUTABLE: str

    def run(
        self,
        config: AdapterConfig,
        tier_config: TierConfig | None = None,
    ) -> AdapterResult:
        """Execute CLI with the given configuration.

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
            raise AdapterError(f"CLI not found. Is '{self.CLI_EXECUTABLE}' installed?") from None

        except subprocess.SubprocessError as e:
            raise AdapterError(f"Failed to execute {self.CLI_EXECUTABLE}: {e}") from e

        end_time = datetime.now(timezone.utc)
        duration = (end_time - start_time).total_seconds()

        # Parse output for metrics
        tokens_input, tokens_output = self._parse_token_counts(result.stdout, result.stderr)
        api_calls = self._parse_api_calls(result.stdout, result.stderr)

        # Create token stats (CLI adapters typically don't provide cache info)
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

    @abstractmethod
    def _build_command(
        self,
        config: AdapterConfig,
        prompt: str,
        tier_config: TierConfig | None,
    ) -> list[str]:
        """Build the CLI command.

        Args:
            config: Adapter configuration.
            prompt: The prompt to send (with tier injection if applicable).
            tier_config: Tier configuration for tool/delegation settings.

        Returns:
            Command as list of strings.

        """
        ...

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
        env.pop("CLAUDECODE", None)
        return env

    @abstractmethod
    def _parse_token_counts(self, stdout: str, stderr: str) -> tuple[int, int]:
        """Parse token counts from CLI output.

        Args:
            stdout: Standard output from CLI.
            stderr: Standard error from CLI.

        Returns:
            Tuple of (input_tokens, output_tokens).

        """
        ...

    def _parse_api_calls(self, stdout: str, stderr: str) -> int:
        """Parse API call count from output.

        Uses common patterns across CLI tools, with optional fallback pattern
        defined by subclasses via _api_call_fallback_pattern.

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

        # Try fallback pattern if defined by subclass
        if hasattr(self, "_api_call_fallback_pattern"):
            fallback = self._api_call_fallback_pattern
            if fallback:
                fallback_matches = len(re.findall(fallback, combined, re.IGNORECASE))
                if fallback_matches > 0:
                    return fallback_matches

        # Default: assume at least 1 call if there's meaningful output
        if len(stdout.strip()) > 100:
            return 1

        return 0
