"""Shared utilities for judge-related operations."""

import json
import re
from typing import Any


def extract_json_from_llm_response(output: str) -> dict[str, Any] | None:
    r"""Extract a JSON object from LLM output text.

    Handles multiple common LLM response formats:
    - Raw JSON objects
    - JSON in markdown code blocks (```json or ```)
    - JSON wrapped in XML tags with preamble text
    - JSON with leading/trailing text

    This function uses a robust brace-matching algorithm to extract JSON
    objects even when surrounded by explanatory text or XML tags.

    Args:
        output: Raw LLM output text that may contain JSON.

    Returns:
        Parsed JSON dictionary, or None if no valid JSON object found.

    Examples:
        >>> extract_json_from_llm_response('{"score": 5}')
        {'score': 5}

        >>> extract_json_from_llm_response('```json\n{"score": 5}\n```')
        {'score': 5}

        >>> extract_json_from_llm_response('<json>{"score": 5}</json>')
        {'score': 5}

        >>> extract_json_from_llm_response('Here is the result: {"score": 5}')
        {'score': 5}

    """
    # Try to find JSON in code blocks first
    json_block = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", output)
    if json_block:
        try:
            return json.loads(json_block.group(1))
        except json.JSONDecodeError:
            pass

    # Try to find raw JSON object using brace matching
    start = output.find("{")
    if start == -1:
        return None

    # Find matching closing brace
    depth = 0
    end = start
    for i, char in enumerate(output[start:], start):
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break

    if depth != 0:
        return None

    try:
        return json.loads(output[start:end])
    except json.JSONDecodeError:
        return None
