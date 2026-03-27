"""OpenCode CLI adapter.

This module provides an adapter for running the OpenCode CLI
within the Scylla evaluation framework.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from scylla.adapters.base import AdapterConfig
from scylla.adapters.base_cli import BaseCliAdapter

if TYPE_CHECKING:
    from scylla.executor.tier_config import TierConfig


class OpenCodeAdapter(BaseCliAdapter):
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

    # Fallback pattern for API call detection
    _api_call_fallback_pattern = r"(?:completion|response):"

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
