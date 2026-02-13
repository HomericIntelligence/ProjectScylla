"""OpenAI Codex CLI adapter.

This module provides an adapter for running the OpenAI Codex CLI
within the Scylla evaluation framework.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

from scylla.adapters.base import AdapterConfig
from scylla.adapters.base_cli import BaseCliAdapter

if TYPE_CHECKING:
    from scylla.executor.tier_config import TierConfig


class OpenAICodexAdapter(BaseCliAdapter):
    """Adapter for OpenAI Codex CLI.

    Executes the OpenAI Codex CLI with the specified configuration and
    captures output, token counts, and metrics.

    Example:
        >>> adapter = OpenAICodexAdapter()
        >>> config = AdapterConfig(
        ...     model="gpt-4",
        ...     prompt_file=Path("prompt.md"),
        ...     workspace=Path("/workspace"),
        ...     output_dir=Path("/output"),
        ... )
        >>> result = adapter.run(config)
        >>> print(f"Exit code: {result.exit_code}")

    """

    # OpenAI Codex CLI executable
    CLI_EXECUTABLE = "codex"

    # Fallback pattern for API call detection
    _api_call_fallback_pattern = r'"finish_reason"'

    def _build_command(
        self,
        config: AdapterConfig,
        prompt: str,
        tier_config: TierConfig | None,
    ) -> list[str]:
        """Build the OpenAI Codex CLI command.

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
            "--quiet",  # Reduce verbose output
        ]

        # Apply tier settings
        tier_settings = self.get_tier_settings(tier_config)

        # Disable tools if explicitly set to False
        if tier_settings["tools_enabled"] is False:
            cmd.append("--no-tools")

        # Add extra arguments from config
        if config.extra_args:
            cmd.extend(config.extra_args)

        # Add the prompt as the final argument
        cmd.append(prompt)

        return cmd

    def _parse_token_counts(self, stdout: str, stderr: str) -> tuple[int, int]:
        """Parse token counts from Codex output.

        Looks for patterns like:
        - JSON output: {"usage": {"prompt_tokens": N, "completion_tokens": M}}
        - Text: "Tokens: N input, M output"

        Args:
            stdout: Standard output from CLI.
            stderr: Standard error from CLI.

        Returns:
            Tuple of (input_tokens, output_tokens).

        """
        combined = stdout + "\n" + stderr
        input_tokens = 0
        output_tokens = 0

        # Try JSON format first (common in OpenAI tools)
        try:
            # Look for JSON object containing usage - try to parse the whole string
            data = json.loads(combined.strip())
            usage = data.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)
            if input_tokens > 0 or output_tokens > 0:
                return input_tokens, output_tokens
        except (json.JSONDecodeError, KeyError, TypeError):
            pass

        # Try to find embedded JSON with usage
        try:
            # Find JSON-like patterns with usage key
            for match in re.finditer(r"\{[^{}]*\{[^{}]*\}[^{}]*\}|\{[^{}]+\}", combined):
                try:
                    data = json.loads(match.group())
                    usage = data.get("usage", {})
                    if isinstance(usage, dict):
                        input_tokens = usage.get("prompt_tokens", 0)
                        output_tokens = usage.get("completion_tokens", 0)
                        if input_tokens > 0 or output_tokens > 0:
                            return input_tokens, output_tokens
                except (json.JSONDecodeError, KeyError, TypeError):
                    continue
        except Exception:
            pass

        # Pattern: "prompt_tokens: N" or "completion_tokens: N"
        prompt_match = re.search(r"prompt_tokens?:?\s*(\d+)", combined, re.IGNORECASE)
        if prompt_match:
            input_tokens = int(prompt_match.group(1))

        completion_match = re.search(r"completion_tokens?:?\s*(\d+)", combined, re.IGNORECASE)
        if completion_match:
            output_tokens = int(completion_match.group(1))

        # Pattern: "N input, M output" or similar
        combined_match = re.search(
            r"(\d+)\s*(?:input|in)\s*[,/]\s*(\d+)\s*(?:output|out)",
            combined,
            re.IGNORECASE,
        )
        if combined_match:
            input_tokens = int(combined_match.group(1))
            output_tokens = int(combined_match.group(2))

        return input_tokens, output_tokens
