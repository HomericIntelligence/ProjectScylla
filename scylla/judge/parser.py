"""Judgment parser for extracting structured data from judge output.

This module provides parsing and serialization of judgment data,
including writing judgment.json to disk.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scylla.judge.utils import extract_json_from_llm_response

logger = logging.getLogger(__name__)


class JudgmentParseError(Exception):
    """Raised when parsing judgment output fails."""

    pass


@dataclass
class RequirementScore:
    """Score for a single requirement.

    Attributes:
        id: Requirement identifier.
        score: The score (0.0 to 1.0).
        confidence: Confidence in the score (0.0 to 1.0).
        notes: Brief explanation of the score.

    """

    id: str
    score: float
    confidence: float = 0.5
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "id": self.id,
            "score": self.score,
            "confidence": self.confidence,
            "notes": self.notes,
        }


@dataclass
class CategoryScore:
    """Score for an evaluation category.

    Attributes:
        name: Category name.
        score: The score (0.0 to 1.0).
        confidence: Confidence in the score (0.0 to 1.0).
        weight: Category weight.
        notes: Brief explanation of the score.

    """

    name: str
    score: float
    confidence: float = 0.5
    weight: float = 1.0
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "name": self.name,
            "score": self.score,
            "confidence": self.confidence,
            "weight": self.weight,
            "notes": self.notes,
        }


@dataclass
class JudgmentSummary:
    """Summary of a judgment.

    Attributes:
        weighted_score: The weighted score (0.0 to 1.0).
        passed: Whether the evaluation passed.
        letter_grade: Letter grade (A/B/C/D/F).
        overall_confidence: Overall confidence in the judgment.
        strengths: List of identified strengths.
        weaknesses: List of identified weaknesses.

    """

    weighted_score: float
    passed: bool
    letter_grade: str
    overall_confidence: float = 0.5
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "weighted_score": self.weighted_score,
            "passed": self.passed,
            "letter_grade": self.letter_grade,
            "overall_confidence": self.overall_confidence,
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
        }


@dataclass
class ExploratoryTestingResult:
    """Results from exploratory testing phase.

    Attributes:
        commands_run: Commands executed during testing.
        observations: Observations made.
        failures: Failures encountered.

    """

    commands_run: list[str] = field(default_factory=list)
    observations: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "commands_run": self.commands_run,
            "observations": self.observations,
            "failures": self.failures,
        }


@dataclass
class Judgment:
    """Complete judgment from an evaluation.

    Attributes:
        timestamp: ISO 8601 timestamp of the judgment.
        judge_model: Model used for judging.
        requirements: Scores for each requirement.
        categories: Scores for each category.
        summary: Judgment summary.
        exploratory_testing: Results from exploratory testing.
        qualitative_feedback: Free-form qualitative feedback.
        raw_output: Raw output from the judge.

    """

    timestamp: str = ""
    judge_model: str = ""
    requirements: dict[str, RequirementScore] = field(default_factory=dict)
    categories: dict[str, CategoryScore] = field(default_factory=dict)
    summary: JudgmentSummary | None = None
    exploratory_testing: ExploratoryTestingResult | None = None
    qualitative_feedback: str = ""
    raw_output: str = ""

    def __post_init__(self) -> None:
        """Set timestamp if not provided."""
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        result: dict[str, Any] = {
            "timestamp": self.timestamp,
            "judge_model": self.judge_model,
            "requirements": {
                req_id: score.to_dict() for req_id, score in self.requirements.items()
            },
            "categories": {
                cat_name: score.to_dict() for cat_name, score in self.categories.items()
            },
            "qualitative_feedback": self.qualitative_feedback,
        }

        if self.summary:
            result["summary"] = self.summary.to_dict()

        if self.exploratory_testing:
            result["exploratory_testing"] = self.exploratory_testing.to_dict()

        return result

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string.

        Args:
            indent: Indentation level for pretty printing.

        Returns:
            JSON string representation.

        """
        return json.dumps(self.to_dict(), indent=indent)

    def write_json(self, output_path: Path) -> None:
        """Write judgment to JSON file.

        Args:
            output_path: Path to write the judgment.json file.

        Raises:
            IOError: If writing fails.

        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(self.to_json())
        logger.info(f"Wrote judgment to {output_path}")


class JudgmentParser:
    """Parser for extracting structured judgment data from output."""

    def parse(self, output: str, judge_model: str = "") -> Judgment:
        """Parse judgment from raw output.

        Args:
            output: Raw output from the judge.
            judge_model: Model used for judging.

        Returns:
            Parsed Judgment object.

        """
        json_data = self._extract_json(output)

        if json_data is None:
            logger.warning("No valid JSON found in judge output")
            return Judgment(
                judge_model=judge_model,
                raw_output=output,
            )

        return self._build_judgment(json_data, judge_model, output)

    def parse_file(self, file_path: Path, judge_model: str = "") -> Judgment:
        """Parse judgment from a file.

        Args:
            file_path: Path to file containing judge output.
            judge_model: Model used for judging.

        Returns:
            Parsed Judgment object.

        Raises:
            JudgmentParseError: If the file cannot be read.

        """
        try:
            output = file_path.read_text()
        except OSError as e:
            raise JudgmentParseError(f"Failed to read file: {e}") from e

        return self.parse(output, judge_model)

    def _extract_json(self, output: str) -> dict[str, Any] | None:
        """Extract JSON object from output text.

        Args:
            output: Raw output text.

        Returns:
            Parsed JSON dict, or None if not found.

        """
        return extract_json_from_llm_response(output)

    def _build_judgment(
        self,
        data: dict[str, Any],
        judge_model: str,
        raw_output: str,
    ) -> Judgment:
        """Build Judgment from parsed JSON data.

        Args:
            data: Parsed JSON data.
            judge_model: Model used for judging.
            raw_output: Raw output string.

        Returns:
            Judgment object.

        """
        judgment = Judgment(
            judge_model=judge_model,
            raw_output=raw_output,
        )

        # Parse requirements
        requirements = data.get("requirements", {})
        for req_id, req_data in requirements.items():
            if isinstance(req_data, dict):
                judgment.requirements[req_id] = RequirementScore(
                    id=req_id,
                    score=float(req_data.get("score", 0.0)),
                    confidence=float(req_data.get("confidence", 0.5)),
                    notes=str(req_data.get("notes", "")),
                )

        # Parse categories
        categories = data.get("categories", {})
        for cat_name, cat_data in categories.items():
            if isinstance(cat_data, dict):
                judgment.categories[cat_name] = CategoryScore(
                    name=cat_name,
                    score=float(cat_data.get("score", 0.0)),
                    confidence=float(cat_data.get("confidence", 0.5)),
                    weight=float(cat_data.get("weight", 1.0)),
                    notes=str(cat_data.get("notes", "")),
                )

        # Parse summary
        summary = data.get("summary", {})
        if summary:
            judgment.summary = JudgmentSummary(
                weighted_score=float(summary.get("weighted_score", 0.0)),
                passed=bool(summary.get("passed", False)),
                letter_grade=str(summary.get("letter_grade", "F")),
                overall_confidence=float(summary.get("overall_confidence", 0.5)),
                strengths=list(summary.get("strengths", [])),
                weaknesses=list(summary.get("weaknesses", [])),
            )

        # Parse exploratory testing
        exploratory = data.get("exploratory_testing", {})
        if exploratory:
            judgment.exploratory_testing = ExploratoryTestingResult(
                commands_run=list(exploratory.get("commands_run", [])),
                observations=list(exploratory.get("observations", [])),
                failures=list(exploratory.get("failures", [])),
            )

        # Parse qualitative feedback
        judgment.qualitative_feedback = str(data.get("qualitative_feedback", ""))

        return judgment


def load_judgment(file_path: Path) -> Judgment:
    """Load judgment from a JSON file.

    Args:
        file_path: Path to the judgment.json file.

    Returns:
        Loaded Judgment object.

    Raises:
        JudgmentParseError: If the file cannot be read or parsed.

    """
    try:
        content = file_path.read_text()
        data = json.loads(content)
    except (OSError, json.JSONDecodeError) as e:
        raise JudgmentParseError(f"Failed to load judgment: {e}") from e

    parser = JudgmentParser()
    return parser._build_judgment(data, data.get("judge_model", ""), "")
