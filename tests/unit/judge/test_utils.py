"""Tests for judge utility functions."""

from scylla.judge.utils import extract_json_from_llm_response


class TestExtractJsonFromLlmResponse:
    """Tests for extract_json_from_llm_response utility."""

    def test_raw_json_happy_path(self):
        """Test extraction of raw JSON object."""
        output = '{"score": 5, "passed": true}'
        result = extract_json_from_llm_response(output)
        assert result == {"score": 5, "passed": True}

    def test_json_in_markdown_code_block_with_json_label(self):
        """Test extraction from ```json code block."""
        output = '```json\n{"score": 5, "passed": true}\n```'
        result = extract_json_from_llm_response(output)
        assert result == {"score": 5, "passed": True}

    def test_json_in_markdown_code_block_without_label(self):
        """Test extraction from ``` code block without json label."""
        output = '```\n{"score": 5, "passed": true}\n```'
        result = extract_json_from_llm_response(output)
        assert result == {"score": 5, "passed": True}

    def test_json_wrapped_in_xml_tags_with_preamble(self):
        """Test extraction from XML-wrapped JSON with preamble text."""
        output = """Here is the evaluation result:
<json_evaluation>
{"score": 0.8, "passed": true, "reasoning": "Good work"}
</json_evaluation>
"""
        result = extract_json_from_llm_response(output)
        assert result == {
            "score": 0.8,
            "passed": True,
            "reasoning": "Good work",
        }

    def test_json_with_preamble_text_no_tags(self):
        """Test extraction of JSON with leading preamble text."""
        output = 'Here is the result: {"score": 5, "passed": true}'
        result = extract_json_from_llm_response(output)
        assert result == {"score": 5, "passed": True}

    def test_json_with_trailing_text(self):
        """Test extraction of JSON with trailing text."""
        output = '{"score": 5, "passed": true} - This is a good result'
        result = extract_json_from_llm_response(output)
        assert result == {"score": 5, "passed": True}

    def test_no_json_in_output(self):
        """Test that None is returned when no JSON is found."""
        output = "This is just plain text with no JSON"
        result = extract_json_from_llm_response(output)
        assert result is None

    def test_malformed_json(self):
        """Test that None is returned for malformed JSON."""
        output = '{"score": 5, "passed": true'  # Missing closing brace
        result = extract_json_from_llm_response(output)
        assert result is None

    def test_unbalanced_braces(self):
        """Test that None is returned for unbalanced braces."""
        output = '{"score": 5, "nested": {"key": "value"}'  # Missing closing brace
        result = extract_json_from_llm_response(output)
        assert result is None

    def test_nested_json_objects(self):
        """Test extraction of nested JSON objects."""
        output = '{"score": 5, "metadata": {"author": "test", "version": 1}}'
        result = extract_json_from_llm_response(output)
        assert result == {
            "score": 5,
            "metadata": {"author": "test", "version": 1},
        }

    def test_json_with_arrays(self):
        """Test extraction of JSON with arrays."""
        output = '{"scores": [1, 2, 3], "passed": true}'
        result = extract_json_from_llm_response(output)
        assert result == {"scores": [1, 2, 3], "passed": True}

    def test_complex_real_world_example(self):
        """Test extraction from complex real-world LLM response."""
        output = """I'll evaluate this submission based on the rubric.

<json_evaluation>
{
  "score": 0.85,
  "passed": true,
  "reasoning": "The implementation meets most requirements with minor issues.",
  "criteria_scores": {
    "correctness": {"score": 0.9, "explanation": "Logic is sound"},
    "completeness": {"score": 0.8, "explanation": "Missing edge cases"}
  }
}
</json_evaluation>

Let me know if you need clarification!"""
        result = extract_json_from_llm_response(output)
        assert result is not None
        assert result["score"] == 0.85
        assert result["passed"] is True
        assert "criteria_scores" in result

    def test_empty_string(self):
        """Test that None is returned for empty string."""
        output = ""
        result = extract_json_from_llm_response(output)
        assert result is None

    def test_whitespace_only(self):
        """Test that None is returned for whitespace-only input."""
        output = "   \n\t  "
        result = extract_json_from_llm_response(output)
        assert result is None

    def test_json_with_escaped_quotes(self):
        """Test extraction of JSON with escaped quotes in strings."""
        output = r'{"message": "He said \"hello\" to me"}'
        result = extract_json_from_llm_response(output)
        assert result == {"message": 'He said "hello" to me'}

    def test_multiple_json_objects_extracts_first(self):
        """Test that only the first JSON object is extracted."""
        output = '{"first": 1} {"second": 2}'
        result = extract_json_from_llm_response(output)
        assert result == {"first": 1}
