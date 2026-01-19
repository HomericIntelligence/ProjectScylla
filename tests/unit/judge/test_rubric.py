"""Tests for rubric parser.

Python justification: Required for pytest testing framework.
"""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from scylla.judge.rubric import (
    EvaluationType,
    Requirement,
    Rubric,
    RubricError,
    RubricParser,
    RubricValidationError,
)


class TestEvaluationType:
    """Tests for EvaluationType enum."""

    def test_binary_value(self) -> None:
        """Test BINARY enum value."""
        assert EvaluationType.BINARY.value == "binary"

    def test_scaled_value(self) -> None:
        """Test SCALED enum value."""
        assert EvaluationType.SCALED.value == "scaled"

    def test_from_string(self) -> None:
        """Test creating from string."""
        assert EvaluationType("binary") == EvaluationType.BINARY
        assert EvaluationType("scaled") == EvaluationType.SCALED


class TestRequirement:
    """Tests for Requirement model."""

    def test_minimal_requirement(self) -> None:
        """Test creating requirement with minimal fields."""
        req = Requirement(id="R001", description="Test requirement")
        assert req.id == "R001"
        assert req.description == "Test requirement"
        assert req.weight == 1.0
        assert req.evaluation == EvaluationType.SCALED
        assert req.validation_command is None

    def test_full_requirement(self) -> None:
        """Test creating requirement with all fields."""
        req = Requirement(
            id="R002",
            description="Binary check",
            weight=2.0,
            evaluation=EvaluationType.BINARY,
            validation_command="pytest tests/",
        )
        assert req.id == "R002"
        assert req.weight == 2.0
        assert req.evaluation == EvaluationType.BINARY
        assert req.validation_command == "pytest tests/"

    def test_empty_id_rejected(self) -> None:
        """Test that empty ID is rejected."""
        with pytest.raises(ValueError, match="cannot be empty"):
            Requirement(id="", description="Test")

    def test_whitespace_id_rejected(self) -> None:
        """Test that whitespace-only ID is rejected."""
        with pytest.raises(ValueError, match="cannot be empty"):
            Requirement(id="   ", description="Test")

    def test_id_stripped(self) -> None:
        """Test that ID is stripped of whitespace."""
        req = Requirement(id="  R001  ", description="Test")
        assert req.id == "R001"

    def test_negative_weight_rejected(self) -> None:
        """Test that negative weight is rejected."""
        with pytest.raises(ValueError):
            Requirement(id="R001", description="Test", weight=-1.0)


class TestRubric:
    """Tests for Rubric model."""

    def test_default_rubric(self) -> None:
        """Test default rubric values."""
        rubric = Rubric()
        assert rubric.name == "Evaluation Rubric"
        assert rubric.description == ""
        assert rubric.requirements == []
        assert rubric.pass_threshold == 0.60  # Good grade threshold

    def test_custom_rubric(self) -> None:
        """Test rubric with custom values."""
        reqs = [
            Requirement(id="R001", description="Test 1"),
            Requirement(id="R002", description="Test 2"),
        ]
        rubric = Rubric(
            name="Custom Rubric",
            description="Test description",
            requirements=reqs,
            pass_threshold=0.80,
        )
        assert rubric.name == "Custom Rubric"
        assert rubric.description == "Test description"
        assert len(rubric.requirements) == 2
        assert rubric.pass_threshold == 0.80


class TestCalculateWeightedScore:
    """Tests for weighted score calculation."""

    def test_empty_requirements(self) -> None:
        """Test score with no requirements."""
        rubric = Rubric()
        assert rubric.calculate_weighted_score({}) == 0.0

    def test_equal_weights(self) -> None:
        """Test score with equal weights."""
        rubric = Rubric(
            requirements=[
                Requirement(id="R001", description="Test 1", weight=1.0),
                Requirement(id="R002", description="Test 2", weight=1.0),
            ]
        )
        scores = {"R001": 0.8, "R002": 0.6}
        assert rubric.calculate_weighted_score(scores) == pytest.approx(0.7)

    def test_unequal_weights(self) -> None:
        """Test score with unequal weights."""
        rubric = Rubric(
            requirements=[
                Requirement(id="R001", description="Test 1", weight=2.0),
                Requirement(id="R002", description="Test 2", weight=1.0),
            ]
        )
        scores = {"R001": 0.9, "R002": 0.6}
        # (0.9 * 2.0 + 0.6 * 1.0) / 3.0 = 2.4 / 3.0 = 0.8
        assert rubric.calculate_weighted_score(scores) == pytest.approx(0.8)

    def test_missing_score_raises(self) -> None:
        """Test that missing score raises error."""
        rubric = Rubric(
            requirements=[
                Requirement(id="R001", description="Test 1"),
            ]
        )
        with pytest.raises(RubricValidationError, match="Missing score"):
            rubric.calculate_weighted_score({})

    def test_score_out_of_range_raises(self) -> None:
        """Test that score out of range raises error."""
        rubric = Rubric(
            requirements=[
                Requirement(id="R001", description="Test 1"),
            ]
        )
        with pytest.raises(RubricValidationError, match="between 0.0 and 1.0"):
            rubric.calculate_weighted_score({"R001": 1.5})

    def test_zero_total_weight(self) -> None:
        """Test score when all weights are zero."""
        rubric = Rubric(
            requirements=[
                Requirement(id="R001", description="Test 1", weight=0.0),
            ]
        )
        assert rubric.calculate_weighted_score({"R001": 0.5}) == 0.0


class TestIsPassing:
    """Tests for passing check."""

    def test_passing(self) -> None:
        """Test passing score."""
        rubric = Rubric(pass_threshold=0.70)
        assert rubric.is_passing(0.70) is True
        assert rubric.is_passing(0.80) is True

    def test_failing(self) -> None:
        """Test failing score."""
        rubric = Rubric(pass_threshold=0.70)
        assert rubric.is_passing(0.69) is False
        assert rubric.is_passing(0.0) is False


class TestGetRequirement:
    """Tests for requirement lookup."""

    def test_found(self) -> None:
        """Test finding existing requirement."""
        rubric = Rubric(
            requirements=[
                Requirement(id="R001", description="Test 1"),
                Requirement(id="R002", description="Test 2"),
            ]
        )
        req = rubric.get_requirement("R001")
        assert req is not None
        assert req.id == "R001"

    def test_not_found(self) -> None:
        """Test requirement not found."""
        rubric = Rubric(
            requirements=[
                Requirement(id="R001", description="Test 1"),
            ]
        )
        assert rubric.get_requirement("R999") is None


class TestTotalWeight:
    """Tests for total weight calculation."""

    def test_empty(self) -> None:
        """Test total weight with no requirements."""
        rubric = Rubric()
        assert rubric.total_weight() == 0.0

    def test_multiple_requirements(self) -> None:
        """Test total weight with multiple requirements."""
        rubric = Rubric(
            requirements=[
                Requirement(id="R001", description="Test 1", weight=2.0),
                Requirement(id="R002", description="Test 2", weight=1.5),
                Requirement(id="R003", description="Test 3", weight=0.5),
            ]
        )
        assert rubric.total_weight() == pytest.approx(4.0)


class TestRubricParserParseYaml:
    """Tests for YAML parsing."""

    def test_minimal_yaml(self) -> None:
        """Test parsing minimal YAML."""
        yaml_content = """
name: Test Rubric
requirements:
  - id: R001
    description: Test requirement
"""
        rubric = RubricParser.parse_yaml(yaml_content)
        assert rubric.name == "Test Rubric"
        assert len(rubric.requirements) == 1
        assert rubric.requirements[0].id == "R001"

    def test_full_yaml(self) -> None:
        """Test parsing full YAML with all fields (industry-aligned scale)."""
        yaml_content = """
name: Complete Rubric
description: Full test rubric
requirements:
  - id: R001
    description: First requirement
    weight: 2.0
    evaluation: binary
    validation_command: "pytest tests/"
  - id: R002
    description: Second requirement
    weight: 1.0
    evaluation: scaled
grading:
  pass_threshold: 0.60
  grade_scale:
    S: 1.00
    A: 0.80
    B: 0.60
    C: 0.40
    D: 0.20
    F: 0.0
"""
        rubric = RubricParser.parse_yaml(yaml_content)
        assert rubric.name == "Complete Rubric"
        assert rubric.description == "Full test rubric"
        assert rubric.pass_threshold == 0.60
        # Grade scale is no longer configurable - uses centralized assign_letter_grade()
        assert len(rubric.requirements) == 2
        assert rubric.requirements[0].evaluation == EvaluationType.BINARY
        assert rubric.requirements[0].validation_command == "pytest tests/"
        assert rubric.requirements[1].evaluation == EvaluationType.SCALED

    def test_empty_yaml(self) -> None:
        """Test parsing empty YAML."""
        with pytest.raises(RubricValidationError, match="empty"):
            RubricParser.parse_yaml("")

    def test_invalid_yaml(self) -> None:
        """Test parsing invalid YAML."""
        with pytest.raises(RubricValidationError, match="Invalid YAML"):
            RubricParser.parse_yaml("name: [invalid")

    def test_non_mapping_yaml(self) -> None:
        """Test parsing non-mapping YAML."""
        with pytest.raises(RubricValidationError, match="must be a YAML mapping"):
            RubricParser.parse_yaml("- item1\n- item2")

    def test_invalid_requirements_type(self) -> None:
        """Test parsing with invalid requirements type."""
        yaml_content = """
name: Test
requirements: "not a list"
"""
        with pytest.raises(RubricValidationError, match="must be a list"):
            RubricParser.parse_yaml(yaml_content)

    def test_invalid_requirement_type(self) -> None:
        """Test parsing with invalid requirement item type."""
        yaml_content = """
name: Test
requirements:
  - "not a mapping"
"""
        with pytest.raises(RubricValidationError, match="must be a mapping"):
            RubricParser.parse_yaml(yaml_content)

    def test_auto_generated_ids(self) -> None:
        """Test that IDs are auto-generated when missing."""
        yaml_content = """
name: Test
requirements:
  - description: First
  - description: Second
"""
        rubric = RubricParser.parse_yaml(yaml_content)
        assert rubric.requirements[0].id == "R001"
        assert rubric.requirements[1].id == "R002"

    def test_default_values(self) -> None:
        """Test default values when fields are omitted."""
        yaml_content = """
requirements:
  - id: R001
    description: Test
"""
        rubric = RubricParser.parse_yaml(yaml_content)
        assert rubric.name == "Evaluation Rubric"
        assert rubric.description == ""
        assert rubric.pass_threshold == 0.60  # Good grade threshold
        assert rubric.requirements[0].weight == 1.0
        assert rubric.requirements[0].evaluation == EvaluationType.SCALED


class TestRubricParserParse:
    """Tests for file parsing."""

    def test_parse_file(self) -> None:
        """Test parsing rubric from file."""
        yaml_content = """
name: File Rubric
requirements:
  - id: R001
    description: Test
"""
        with TemporaryDirectory() as tmpdir:
            rubric_file = Path(tmpdir) / "rubric.yaml"
            rubric_file.write_text(yaml_content)

            rubric = RubricParser.parse(rubric_file)
            assert rubric.name == "File Rubric"

    def test_parse_missing_file(self) -> None:
        """Test parsing non-existent file."""
        with pytest.raises(RubricError, match="not found"):
            RubricParser.parse(Path("/nonexistent/rubric.yaml"))

    def test_parse_unreadable_file(self) -> None:
        """Test parsing unreadable file."""
        with TemporaryDirectory() as tmpdir:
            rubric_file = Path(tmpdir) / "rubric.yaml"
            rubric_file.write_text("name: Test")
            rubric_file.chmod(0o000)

            try:
                with pytest.raises(RubricError, match="Failed to read"):
                    RubricParser.parse(rubric_file)
            finally:
                # Restore permissions for cleanup
                rubric_file.chmod(0o644)


class TestRubricErrors:
    """Tests for error classes."""

    def test_rubric_error(self) -> None:
        """Test RubricError base exception."""
        error = RubricError("Test error")
        assert str(error) == "Test error"

    def test_rubric_validation_error(self) -> None:
        """Test RubricValidationError exception."""
        error = RubricValidationError("Validation failed")
        assert str(error) == "Validation failed"
        assert isinstance(error, RubricError)
