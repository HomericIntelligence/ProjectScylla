"""Test that all grading logic is consistent with documentation.

This test validates that:
1. All grade assignment functions produce the same results
2. Grade thresholds match docs/design/grading-scale.md specification
3. S grade requires exactly 1.0 (perfect score)
4. Assertions catch invalid scores
"""

import pytest

from scylla.config.models import GradeScale
from scylla.judge.rubric import GradeScale as JudgeGradeScale
from scylla.judge.rubric import Requirement, Rubric
from scylla.metrics.grading import assign_letter_grade


class TestGradingConsistency:
    """Test grading consistency across codebase."""

    def test_grade_thresholds_match_documentation(self):
        """Verify default grade thresholds match grading-scale.md."""
        # These values are from docs/design/grading-scale.md
        expected_thresholds = {
            "S": 1.00,
            "A": 0.80,
            "B": 0.60,
            "C": 0.40,
            "D": 0.20,
            "F": 0.00,
        }

        grade_scale = GradeScale()
        assert grade_scale.S == expected_thresholds["S"]
        assert grade_scale.A == expected_thresholds["A"]
        assert grade_scale.B == expected_thresholds["B"]
        assert grade_scale.C == expected_thresholds["C"]
        assert grade_scale.D == expected_thresholds["D"]
        assert grade_scale.F == expected_thresholds["F"]

    def test_s_grade_requires_perfect_score(self):
        """S grade should ONLY be assigned to exactly 1.0."""
        # Perfect score = S
        assert assign_letter_grade(1.0) == "S"

        # Near-perfect scores should NOT get S
        assert assign_letter_grade(0.99) == "A"
        assert assign_letter_grade(0.95) == "A"
        assert assign_letter_grade(0.999) == "A"

    def test_grade_assignment_boundaries(self):
        """Test grade assignment at exact threshold boundaries."""
        test_cases = [
            # (score, expected_grade)
            (1.00, "S"),  # Perfect
            (0.99, "A"),  # Just below S
            (0.80, "A"),  # A threshold
            (0.79, "B"),  # Just below A
            (0.60, "B"),  # B threshold
            (0.59, "C"),  # Just below B
            (0.40, "C"),  # C threshold
            (0.39, "D"),  # Just below C
            (0.20, "D"),  # D threshold
            (0.19, "F"),  # Just below D
            (0.00, "F"),  # Minimum
        ]

        for score, expected_grade in test_cases:
            actual_grade = assign_letter_grade(score)
            assert (
                actual_grade == expected_grade
            ), f"Score {score} should be grade {expected_grade}, got {actual_grade}"

    def test_metrics_grading_validates_range(self):
        """Test that assign_letter_grade asserts on invalid scores."""
        # Scores > 1.0 should raise assertion
        with pytest.raises(AssertionError, match="outside valid range"):
            assign_letter_grade(1.1)

        with pytest.raises(AssertionError, match="outside valid range"):
            assign_letter_grade(1.01)

        # Scores < 0.0 should raise assertion
        with pytest.raises(AssertionError, match="outside valid range"):
            assign_letter_grade(-0.1)

        with pytest.raises(AssertionError, match="outside valid range"):
            assign_letter_grade(-1.0)

    def test_rubric_grading_validates_range(self):
        """Test that Rubric.assign_letter_grade validates score range."""
        # Create minimal rubric for testing
        rubric = Rubric(
            requirements=[
                Requirement(
                    id="R001",
                    description="Test requirement",
                    weight=1.0,
                    evaluation="binary",
                )
            ],
            pass_threshold=0.60,
            grade_scale=JudgeGradeScale(),
        )

        # Valid scores should work
        assert rubric.assign_letter_grade(1.0) == "S"
        assert rubric.assign_letter_grade(0.8) == "A"
        assert rubric.assign_letter_grade(0.0) == "F"

        # Invalid scores should raise error
        with pytest.raises(Exception, match="must be between 0.0 and 1.0"):
            rubric.assign_letter_grade(1.1)

        with pytest.raises(Exception, match="must be between 0.0 and 1.0"):
            rubric.assign_letter_grade(-0.1)

    def test_both_grading_functions_agree(self):
        """Test that both grading functions produce identical results."""
        # Create rubric with default grade scale
        rubric = Rubric(
            requirements=[
                Requirement(
                    id="R001",
                    description="Test requirement",
                    weight=1.0,
                    evaluation="binary",
                )
            ],
            pass_threshold=0.60,
            grade_scale=JudgeGradeScale(),
        )

        # Test a range of scores
        test_scores = [0.0, 0.2, 0.4, 0.6, 0.8, 0.85, 0.95, 0.99, 1.0]

        for score in test_scores:
            metrics_grade = assign_letter_grade(score)
            rubric_grade = rubric.assign_letter_grade(score)
            assert metrics_grade == rubric_grade, (
                f"Grade mismatch for score {score}: "
                f"metrics.grading={metrics_grade} vs rubric={rubric_grade}"
            )

    def test_grade_assignment_exhaustive(self):
        """Exhaustively test grade assignment for all integer percentages."""
        expected_grades = {
            range(0, 20): "F",
            range(20, 40): "D",
            range(40, 60): "C",
            range(60, 80): "B",
            range(80, 100): "A",
            range(100, 101): "S",  # Only 100
        }

        for score_range, expected_grade in expected_grades.items():
            for percentage in score_range:
                score = percentage / 100.0
                actual_grade = assign_letter_grade(score)
                assert actual_grade == expected_grade, (
                    f"Score {score} ({percentage}%) should be {expected_grade}, "
                    f"got {actual_grade}"
                )

    def test_s_grade_exclusively_for_perfect(self):
        """Verify S grade is NEVER assigned to scores less than 1.0."""
        # Test many scores below 1.0
        for i in range(95, 100):  # 0.95 to 0.99
            score = i / 100.0
            grade = assign_letter_grade(score)
            assert grade != "S", f"Score {score} incorrectly got S grade (expected A)"
            assert grade == "A", f"Score {score} should be A, got {grade}"

        # Test edge cases very close to 1.0
        for delta in [0.001, 0.01, 0.1]:
            score = 1.0 - delta
            grade = assign_letter_grade(score)
            assert grade != "S", f"Score {score} incorrectly got S grade"
            assert grade == "A", f"Score {score} should be A, got {grade}"
