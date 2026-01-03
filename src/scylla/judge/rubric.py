"""Rubric parser for evaluation scoring.

This module provides classes for parsing rubric.yaml files and
calculating weighted scores for judge evaluations.

Python Justification: Required for YAML parsing and complex data structures.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator


class RubricError(Exception):
    """Base exception for rubric errors."""

    pass


class RubricValidationError(RubricError):
    """Raised when rubric validation fails."""

    pass


class EvaluationType(str, Enum):
    """Type of evaluation for a requirement."""

    BINARY = "binary"  # Pass/fail (0.0 or 1.0)
    SCALED = "scaled"  # Continuous score (0.0 to 1.0)


class Requirement(BaseModel):
    """A single requirement in the rubric.

    Attributes:
        id: Unique identifier (e.g., "R001").
        description: What to evaluate.
        weight: Scoring weight (1.0 = standard).
        evaluation: Type of evaluation (binary or scaled).
        validation_command: Optional command to validate requirement.
    """

    id: str = Field(..., description="Unique requirement identifier")
    description: str = Field(..., description="What to evaluate")
    weight: float = Field(default=1.0, ge=0.0, description="Scoring weight")
    evaluation: EvaluationType = Field(default=EvaluationType.SCALED, description="Evaluation type")
    validation_command: str | None = Field(default=None, description="Optional validation command")

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        """Validate requirement ID format."""
        if not v or not v.strip():
            raise ValueError("Requirement ID cannot be empty")
        return v.strip()


class GradeScale(BaseModel):
    """Industry-aligned grade scale thresholds.

    See .claude/shared/grading-scale.md for full specification.

    Attributes:
        s_threshold: Amazing - exceptional, above and beyond (1.00).
        a_threshold: Excellent - production ready (0.80).
        b_threshold: Good - minor improvements possible (0.60).
        c_threshold: Acceptable - functional with issues (0.40).
        d_threshold: Marginal - significant issues (0.20).
    """

    s_threshold: float = Field(default=1.00, ge=0.0, le=1.0)
    a_threshold: float = Field(default=0.80, ge=0.0, le=1.0)
    b_threshold: float = Field(default=0.60, ge=0.0, le=1.0)
    c_threshold: float = Field(default=0.40, ge=0.0, le=1.0)
    d_threshold: float = Field(default=0.20, ge=0.0, le=1.0)

    @field_validator("s_threshold", "a_threshold", "b_threshold", "c_threshold", "d_threshold")
    @classmethod
    def validate_threshold(cls, v: float) -> float:
        """Validate threshold is between 0 and 1."""
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"Threshold must be between 0.0 and 1.0, got {v}")
        return v


class Rubric(BaseModel):
    """Rubric for evaluating agent work.

    Attributes:
        name: Rubric name/title.
        description: Rubric description.
        requirements: List of requirements to evaluate.
        pass_threshold: Score threshold for passing (default 0.70).
        grade_scale: Grade thresholds.
    """

    name: str = Field(default="Evaluation Rubric", description="Rubric name")
    description: str = Field(default="", description="Rubric description")
    requirements: list[Requirement] = Field(
        default_factory=list, description="Requirements to evaluate"
    )
    pass_threshold: float = Field(
        default=0.60, ge=0.0, le=1.0, description="Pass threshold (Good grade)"
    )
    grade_scale: GradeScale = Field(default_factory=GradeScale, description="Grade thresholds")

    def calculate_weighted_score(self, scores: dict[str, float]) -> float:
        """Calculate weighted score from requirement scores.

        Args:
            scores: Dictionary mapping requirement IDs to scores (0.0 to 1.0).

        Returns:
            Weighted average score (0.0 to 1.0).

        Raises:
            RubricValidationError: If required scores are missing.
        """
        if not self.requirements:
            return 0.0

        total_weight = 0.0
        weighted_sum = 0.0

        for req in self.requirements:
            if req.id not in scores:
                raise RubricValidationError(f"Missing score for requirement '{req.id}'")

            score = scores[req.id]
            if not 0.0 <= score <= 1.0:
                raise RubricValidationError(
                    f"Score for '{req.id}' must be between 0.0 and 1.0, got {score}"
                )

            weighted_sum += score * req.weight
            total_weight += req.weight

        if total_weight == 0.0:
            return 0.0

        return weighted_sum / total_weight

    def assign_letter_grade(self, weighted_score: float) -> str:
        """Assign letter grade based on weighted score.

        Uses industry-aligned grade scale. See .claude/shared/grading-scale.md.

        Args:
            weighted_score: The weighted score (0.0 to 1.0).

        Returns:
            Letter grade (S, A, B, C, D, or F).

        Raises:
            RubricValidationError: If score is outside valid range [0.0, 1.0].
        """
        if weighted_score > 1.0 or weighted_score < 0.0:
            raise RubricValidationError(f"Score must be between 0.0 and 1.0, got {weighted_score}")
        if weighted_score >= self.grade_scale.s_threshold:
            return "S"
        elif weighted_score >= self.grade_scale.a_threshold:
            return "A"
        elif weighted_score >= self.grade_scale.b_threshold:
            return "B"
        elif weighted_score >= self.grade_scale.c_threshold:
            return "C"
        elif weighted_score >= self.grade_scale.d_threshold:
            return "D"
        else:
            return "F"

    def is_passing(self, weighted_score: float) -> bool:
        """Check if the weighted score passes the threshold.

        Args:
            weighted_score: The weighted score (0.0 to 1.0).

        Returns:
            True if passing, False otherwise.
        """
        return weighted_score >= self.pass_threshold

    def get_requirement(self, requirement_id: str) -> Requirement | None:
        """Get a requirement by ID.

        Args:
            requirement_id: The requirement ID to find.

        Returns:
            The Requirement if found, None otherwise.
        """
        for req in self.requirements:
            if req.id == requirement_id:
                return req
        return None

    def total_weight(self) -> float:
        """Calculate total weight of all requirements.

        Returns:
            Sum of all requirement weights.
        """
        return sum(req.weight for req in self.requirements)


class RubricParser:
    """Parser for rubric.yaml files."""

    @staticmethod
    def parse(rubric_path: Path) -> Rubric:
        """Parse a rubric.yaml file.

        Args:
            rubric_path: Path to the rubric.yaml file.

        Returns:
            Parsed Rubric object.

        Raises:
            RubricError: If the file cannot be read.
            RubricValidationError: If the rubric is invalid.
        """
        if not rubric_path.exists():
            raise RubricError(f"Rubric file not found: {rubric_path}")

        try:
            content = rubric_path.read_text()
        except OSError as e:
            raise RubricError(f"Failed to read rubric file: {e}") from e

        return RubricParser.parse_yaml(content)

    @staticmethod
    def parse_yaml(yaml_content: str) -> Rubric:
        """Parse rubric from YAML string.

        Args:
            yaml_content: YAML content as string.

        Returns:
            Parsed Rubric object.

        Raises:
            RubricValidationError: If the YAML is invalid.
        """
        try:
            data = yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            raise RubricValidationError(f"Invalid YAML: {e}") from e

        if data is None:
            raise RubricValidationError("Rubric file is empty")

        if not isinstance(data, dict):
            raise RubricValidationError("Rubric must be a YAML mapping")

        return RubricParser._parse_rubric_data(data)

    @staticmethod
    def _parse_rubric_data(data: dict[str, Any]) -> Rubric:
        """Parse rubric from dictionary data.

        Args:
            data: Dictionary from YAML parsing.

        Returns:
            Parsed Rubric object.

        Raises:
            RubricValidationError: If the data is invalid.
        """
        try:
            # Parse requirements
            requirements = []
            raw_requirements = data.get("requirements", [])

            if not isinstance(raw_requirements, list):
                raise RubricValidationError("'requirements' must be a list")

            for i, req_data in enumerate(raw_requirements):
                if not isinstance(req_data, dict):
                    raise RubricValidationError(f"Requirement {i} must be a mapping")

                # Handle evaluation type
                eval_type = req_data.get("evaluation", "scaled")
                if isinstance(eval_type, str):
                    eval_type = EvaluationType(eval_type.lower())

                requirement = Requirement(
                    id=req_data.get("id", f"R{i + 1:03d}"),
                    description=req_data.get("description", ""),
                    weight=float(req_data.get("weight", 1.0)),
                    evaluation=eval_type,
                    validation_command=req_data.get("validation_command"),
                )
                requirements.append(requirement)

            # Parse grade scale from grading section
            grading_data = data.get("grading", {})
            grade_data = grading_data.get("grade_scale", {})
            grade_scale = GradeScale()

            return Rubric(
                name=data.get("name", "Evaluation Rubric"),
                description=data.get("description", ""),
                requirements=requirements,
                pass_threshold=float(grading_data.get("pass_threshold", 0.60)),
                grade_scale=grade_scale,
            )

        except (ValueError, TypeError) as e:
            raise RubricValidationError(f"Invalid rubric data: {e}") from e
