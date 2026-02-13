"""Cline CLI adapter.

This module provides an adapter for running the Cline CLI
within the Scylla evaluation framework.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from scylla.adapters.base import AdapterConfig
from scylla.adapters.base_cli import BaseCliAdapter

if TYPE_CHECKING:
    from scylla.executor.tier_config import TierConfig


class ClineAdapter(BaseCliAdapter):
    """Adapter for Cline CLI.

    Executes the Cline CLI with the specified configuration and
    captures output, token counts, and metrics.

    Example:
        >>> adapter = ClineAdapter()
        >>> config = AdapterConfig(
        ...     model="claude-sonnet-4-5-20250929",
        ...     prompt_file=Path("prompt.md"),
        ...     workspace=Path("/workspace"),
        ...     output_dir=Path("/output"),
        ... )
        >>> result = adapter.run(config)
        >>> print(f"Exit code: {result.exit_code}")

    """

    # Cline CLI executable
    CLI_EXECUTABLE = "cline"

    # Fallback pattern for API call detection
    _api_call_fallback_pattern = r"(?:Sending request|Request sent)"

    def _build_command(
        self,
        config: AdapterConfig,
        prompt: str,
        tier_config: TierConfig | None,
    ) -> list[str]:
        """Build the Cline CLI command.

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
            "--non-interactive",  # Non-interactive mode
        ]

        # Apply tier settings
        tier_settings = self.get_tier_settings(tier_config)

        # Disable tools if explicitly set to False
        if tier_settings["tools_enabled"] is False:
            cmd.append("--disable-tools")

        # Add extra arguments from config
        if config.extra_args:
            cmd.extend(config.extra_args)

        # Add the prompt as the final argument
        cmd.extend(["--prompt", prompt])

        return cmd

    def _parse_token_counts(self, stdout: str, stderr: str) -> tuple[int, int]:
        """Parse token counts from Cline output.

        Looks for patterns like:
        - "Input tokens: N"
        - "Output tokens: M"
        - "Tokens used: N input, M output"

        Args:
            stdout: Standard output from CLI.
            stderr: Standard error from CLI.

        Returns:
            Tuple of (input_tokens, output_tokens).

        """
        combined = stdout + "\n" + stderr
        input_tokens = 0
        output_tokens = 0

        # Pattern: "Input tokens: N" or "input: N tokens"
        input_match = re.search(r"input\s*(?:tokens?)?:?\s*(\d+)", combined, re.IGNORECASE)
        if input_match:
            input_tokens = int(input_match.group(1))

        # Pattern: "Output tokens: N" or "output: N tokens"
        output_match = re.search(r"output\s*(?:tokens?)?:?\s*(\d+)", combined, re.IGNORECASE)
        if output_match:
            output_tokens = int(output_match.group(1))

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
