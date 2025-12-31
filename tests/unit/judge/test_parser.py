"""Tests for judgment parser.

Python justification: Required for pytest testing framework.
"""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from scylla.judge.parser import (
    CategoryScore,
    ExploratoryTestingResult,
    Judgment,
    JudgmentParseError,
    JudgmentParser,
    JudgmentSummary,
    RequirementScore,
    load_judgment,
)


class TestRequirementScore:
    """Tests for RequirementScore dataclass."""

    def test_create_score(self) -> None:
        score = RequirementScore(id="R001", score=0.8, confidence=0.9, notes="Good")
        assert score.id == "R001"
        assert score.score == 0.8
        assert score.confidence == 0.9
        assert score.notes == "Good"

    def test_to_dict(self) -> None:
        score = RequirementScore(id="R001", score=0.8, confidence=0.9)
        d = score.to_dict()
        assert d["id"] == "R001"
        assert d["score"] == 0.8


class TestCategoryScore:
    """Tests for CategoryScore dataclass."""

    def test_create_score(self) -> None:
        score = CategoryScore(name="code_quality", score=0.85, weight=1.5)
        assert score.name == "code_quality"
        assert score.score == 0.85
        assert score.weight == 1.5

    def test_to_dict(self) -> None:
        score = CategoryScore(name="test", score=0.7)
        d = score.to_dict()
        assert d["name"] == "test"
        assert d["score"] == 0.7


class TestJudgmentSummary:
    """Tests for JudgmentSummary dataclass."""

    def test_create_summary(self) -> None:
        summary = JudgmentSummary(
            weighted_score=0.85,
            passed=True,
            letter_grade="B",
            overall_confidence=0.9,
            strengths=["Good code"],
            weaknesses=["Missing docs"],
        )
        assert summary.weighted_score == 0.85
        assert summary.passed is True
        assert summary.letter_grade == "B"

    def test_to_dict(self) -> None:
        summary = JudgmentSummary(
            weighted_score=0.8, passed=True, letter_grade="B",
        )
        d = summary.to_dict()
        assert d["weighted_score"] == 0.8
        assert d["passed"] is True


class TestExploratoryTestingResult:
    """Tests for ExploratoryTestingResult dataclass."""

    def test_default_values(self) -> None:
        result = ExploratoryTestingResult()
        assert result.commands_run == []
        assert result.observations == []
        assert result.failures == []

    def test_to_dict(self) -> None:
        result = ExploratoryTestingResult(commands_run=["pytest"])
        d = result.to_dict()
        assert d["commands_run"] == ["pytest"]


class TestJudgment:
    """Tests for Judgment dataclass."""

    def test_auto_timestamp(self) -> None:
        judgment = Judgment()
        assert judgment.timestamp != ""

    def test_to_dict(self) -> None:
        judgment = Judgment(
            judge_model="test-model",
            requirements={"R001": RequirementScore(id="R001", score=0.9)},
            summary=JudgmentSummary(
                weighted_score=0.9, passed=True, letter_grade="A",
            ),
        )
        d = judgment.to_dict()
        assert d["judge_model"] == "test-model"
        assert "R001" in d["requirements"]
        assert d["summary"]["passed"] is True

    def test_to_json(self) -> None:
        judgment = Judgment(judge_model="test")
        json_str = judgment.to_json()
        data = json.loads(json_str)
        assert data["judge_model"] == "test"

    def test_write_json(self) -> None:
        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "judgment.json"
            judgment = Judgment(judge_model="test")
            judgment.write_json(output_path)
            
            assert output_path.exists()
            data = json.loads(output_path.read_text())
            assert data["judge_model"] == "test"


class TestJudgmentParser:
    """Tests for JudgmentParser class."""

    def test_parse_full_json(self) -> None:
        parser = JudgmentParser()
        output = '''{
            "requirements": {"R001": {"score": 0.9, "confidence": 0.8, "notes": "Met"}},
            "categories": {"code_quality": {"score": 0.85, "weight": 1.0}},
            "summary": {
                "weighted_score": 0.87, "passed": true, "letter_grade": "B",
                "overall_confidence": 0.85
            },
            "qualitative_feedback": "Good work"
        }'''
        judgment = parser.parse(output, judge_model="test-model")
        assert judgment.requirements["R001"].score == 0.9
        assert judgment.categories["code_quality"].score == 0.85
        assert judgment.summary.passed is True
        assert judgment.judge_model == "test-model"

    def test_parse_json_in_code_block(self) -> None:
        parser = JudgmentParser()
        output = '''Some text
```json
{"requirements": {"R001": {"score": 0.8}}}
```
More text'''
        judgment = parser.parse(output)
        assert judgment.requirements["R001"].score == 0.8

    def test_parse_nested_json(self) -> None:
        parser = JudgmentParser()
        output = '{"outer": {"inner": {"score": 0.5}}}'
        result = parser._extract_json(output)
        assert result["outer"]["inner"]["score"] == 0.5

    def test_parse_no_json(self) -> None:
        parser = JudgmentParser()
        judgment = parser.parse("No JSON here")
        assert judgment.requirements == {}

    def test_parse_malformed_json(self) -> None:
        parser = JudgmentParser()
        judgment = parser.parse("{invalid: json")
        assert judgment.requirements == {}

    def test_parse_exploratory_testing(self) -> None:
        parser = JudgmentParser()
        output = '''{
            "exploratory_testing": {
                "commands_run": ["pytest", "mypy"],
                "observations": ["All pass"],
                "failures": []
            }
        }'''
        judgment = parser.parse(output)
        assert judgment.exploratory_testing is not None
        assert len(judgment.exploratory_testing.commands_run) == 2

    def test_parse_file(self) -> None:
        parser = JudgmentParser()
        with TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "output.txt"
            file_path.write_text('{"requirements": {"R001": {"score": 0.7}}}')
            
            judgment = parser.parse_file(file_path)
            assert judgment.requirements["R001"].score == 0.7

    def test_parse_file_not_found(self) -> None:
        parser = JudgmentParser()
        with pytest.raises(JudgmentParseError, match="Failed to read"):
            parser.parse_file(Path("/nonexistent/file.txt"))


class TestLoadJudgment:
    """Tests for load_judgment function."""

    def test_load_valid_judgment(self) -> None:
        with TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "judgment.json"
            data = {
                "judge_model": "test",
                "requirements": {"R001": {"score": 0.8}},
                "summary": {
                    "weighted_score": 0.8, "passed": True, "letter_grade": "B",
                },
            }
            file_path.write_text(json.dumps(data))
            
            judgment = load_judgment(file_path)
            assert judgment.requirements["R001"].score == 0.8

    def test_load_missing_file(self) -> None:
        with pytest.raises(JudgmentParseError, match="Failed to load"):
            load_judgment(Path("/nonexistent/judgment.json"))

    def test_load_invalid_json(self) -> None:
        with TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "judgment.json"
            file_path.write_text("not valid json")
            
            with pytest.raises(JudgmentParseError, match="Failed to load"):
                load_judgment(file_path)


class TestJudgmentParseError:
    """Tests for JudgmentParseError exception."""

    def test_error_message(self) -> None:
        error = JudgmentParseError("Parse failed")
        assert str(error) == "Parse failed"
