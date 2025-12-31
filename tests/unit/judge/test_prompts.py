"""Tests for judge prompt templates.

Python justification: Required for pytest testing framework.
"""

import pytest

from scylla.judge.prompts import (
    CATEGORY_WEIGHTS,
    JSON_OUTPUT_SCHEMA,
    JUDGE_PROMPT_TEMPLATE,
    TIER_CONTEXT_TEMPLATES,
    TOTAL_CATEGORY_WEIGHT,
    CategoryScore,
    EvaluationCategory,
    EvaluationSummary,
    ExploratoryTesting,
    JudgmentOutput,
    RequirementScore,
    build_judge_prompt,
    calculate_weighted_category_score,
    get_category_descriptions,
    get_tier_context,
    validate_judgment_output,
)


class TestEvaluationCategory:
    """Tests for EvaluationCategory enum."""

    def test_all_categories_present(self) -> None:
        """Test all 10 categories are defined."""
        assert len(EvaluationCategory) == 10

    def test_category_values(self) -> None:
        """Test category enum values."""
        assert EvaluationCategory.FUNCTIONAL_CORRECTNESS.value == "functional_correctness"
        assert EvaluationCategory.COMPLETENESS.value == "completeness"
        assert EvaluationCategory.CODE_QUALITY.value == "code_quality"
        assert EvaluationCategory.SIMPLICITY.value == "simplicity"
        assert EvaluationCategory.LACK_OF_DUPLICATION.value == "lack_of_duplication"
        assert EvaluationCategory.CLARITY.value == "clarity"
        assert EvaluationCategory.DOCUMENTATION.value == "documentation"
        assert EvaluationCategory.ARCHITECTURAL_CLEANLINESS.value == "architectural_cleanliness"
        assert EvaluationCategory.EFFICIENCY.value == "efficiency"
        assert EvaluationCategory.CLEANUP_SCRIPT_QUALITY.value == "cleanup_script_quality"


class TestCategoryWeights:
    """Tests for category weights."""

    def test_all_categories_have_weights(self) -> None:
        """Test all categories have defined weights."""
        for category in EvaluationCategory:
            assert category in CATEGORY_WEIGHTS

    def test_weights_are_positive(self) -> None:
        """Test all weights are positive."""
        for weight in CATEGORY_WEIGHTS.values():
            assert weight > 0

    def test_total_weight(self) -> None:
        """Test total weight matches expected value."""
        assert TOTAL_CATEGORY_WEIGHT == pytest.approx(9.5)

    def test_specific_weights(self) -> None:
        """Test specific category weights."""
        assert CATEGORY_WEIGHTS[EvaluationCategory.FUNCTIONAL_CORRECTNESS] == 2.0
        assert CATEGORY_WEIGHTS[EvaluationCategory.COMPLETENESS] == 1.5
        assert CATEGORY_WEIGHTS[EvaluationCategory.CODE_QUALITY] == 1.0
        assert CATEGORY_WEIGHTS[EvaluationCategory.SIMPLICITY] == 1.0
        assert CATEGORY_WEIGHTS[EvaluationCategory.LACK_OF_DUPLICATION] == 0.5
        assert CATEGORY_WEIGHTS[EvaluationCategory.CLARITY] == 1.0
        assert CATEGORY_WEIGHTS[EvaluationCategory.DOCUMENTATION] == 0.5
        assert CATEGORY_WEIGHTS[EvaluationCategory.ARCHITECTURAL_CLEANLINESS] == 0.5
        assert CATEGORY_WEIGHTS[EvaluationCategory.EFFICIENCY] == 0.5
        assert CATEGORY_WEIGHTS[EvaluationCategory.CLEANUP_SCRIPT_QUALITY] == 1.0


class TestCategoryScore:
    """Tests for CategoryScore model."""

    def test_valid_score(self) -> None:
        """Test creating valid category score."""
        score = CategoryScore(score=0.8, confidence=0.9, notes="Good work")
        assert score.score == 0.8
        assert score.confidence == 0.9
        assert score.notes == "Good work"

    def test_score_bounds(self) -> None:
        """Test score is bounded 0-1."""
        with pytest.raises(ValueError):
            CategoryScore(score=1.5, confidence=0.5)
        with pytest.raises(ValueError):
            CategoryScore(score=-0.1, confidence=0.5)

    def test_confidence_bounds(self) -> None:
        """Test confidence is bounded 0-1."""
        with pytest.raises(ValueError):
            CategoryScore(score=0.5, confidence=1.5)
        with pytest.raises(ValueError):
            CategoryScore(score=0.5, confidence=-0.1)

    def test_default_notes(self) -> None:
        """Test default empty notes."""
        score = CategoryScore(score=0.5, confidence=0.5)
        assert score.notes == ""


class TestRequirementScore:
    """Tests for RequirementScore model."""

    def test_valid_score(self) -> None:
        """Test creating valid requirement score."""
        score = RequirementScore(score=0.7, confidence=0.85, notes="Met criteria")
        assert score.score == 0.7
        assert score.confidence == 0.85
        assert score.notes == "Met criteria"


class TestExploratoryTesting:
    """Tests for ExploratoryTesting model."""

    def test_default_values(self) -> None:
        """Test default empty lists."""
        testing = ExploratoryTesting()
        assert testing.commands_run == []
        assert testing.observations == []
        assert testing.failures == []

    def test_with_data(self) -> None:
        """Test with provided data."""
        testing = ExploratoryTesting(
            commands_run=["pytest", "mypy"],
            observations=["Tests pass", "Types check"],
            failures=["One flaky test"],
        )
        assert len(testing.commands_run) == 2
        assert len(testing.observations) == 2
        assert len(testing.failures) == 1


class TestEvaluationSummary:
    """Tests for EvaluationSummary model."""

    def test_valid_summary(self) -> None:
        """Test creating valid summary."""
        summary = EvaluationSummary(
            weighted_score=0.85,
            passed=True,
            letter_grade="B",
            overall_confidence=0.9,
            strengths=["Clean code"],
            weaknesses=["Missing docs"],
        )
        assert summary.weighted_score == 0.85
        assert summary.passed is True
        assert summary.letter_grade == "B"

    def test_letter_grade_pattern(self) -> None:
        """Test letter grade validation."""
        # Valid grades
        for grade in ["A", "B", "C", "D", "F"]:
            summary = EvaluationSummary(
                weighted_score=0.5,
                passed=False,
                letter_grade=grade,
                overall_confidence=0.5,
            )
            assert summary.letter_grade == grade

        # Invalid grades
        with pytest.raises(ValueError):
            EvaluationSummary(
                weighted_score=0.5,
                passed=False,
                letter_grade="E",
                overall_confidence=0.5,
            )


class TestJudgmentOutput:
    """Tests for JudgmentOutput model."""

    def test_minimal_output(self) -> None:
        """Test minimal valid output."""
        output = JudgmentOutput(
            summary=EvaluationSummary(
                weighted_score=0.7,
                passed=True,
                letter_grade="C",
                overall_confidence=0.8,
            )
        )
        assert output.summary.passed is True
        assert output.requirements == {}
        assert output.categories == {}

    def test_full_output(self) -> None:
        """Test full output with all fields."""
        output = JudgmentOutput(
            exploratory_testing=ExploratoryTesting(
                commands_run=["pytest"],
                observations=["All pass"],
                failures=[],
            ),
            requirements={
                "R001": RequirementScore(score=0.9, confidence=0.95, notes="Met"),
            },
            categories={
                "functional_correctness": CategoryScore(
                    score=0.9, confidence=0.9, notes="Works"
                ),
            },
            summary=EvaluationSummary(
                weighted_score=0.9,
                passed=True,
                letter_grade="A",
                overall_confidence=0.9,
                strengths=["Good"],
                weaknesses=[],
            ),
            qualitative_feedback="Excellent work",
        )
        assert len(output.requirements) == 1
        assert len(output.categories) == 1
        assert output.qualitative_feedback == "Excellent work"


class TestTierContext:
    """Tests for tier context templates."""

    def test_all_tiers_defined(self) -> None:
        """Test all 7 tiers have context templates."""
        for tier in ["T0", "T1", "T2", "T3", "T4", "T5", "T6"]:
            assert tier in TIER_CONTEXT_TEMPLATES

    def test_get_tier_context_valid(self) -> None:
        """Test getting valid tier context."""
        context = get_tier_context("T0")
        assert "Vanilla" in context
        assert "baseline" in context

        context = get_tier_context("T3")
        assert "Tooling" in context
        assert "function calling" in context

    def test_get_tier_context_invalid(self) -> None:
        """Test getting invalid tier returns empty."""
        assert get_tier_context("T99") == ""
        assert get_tier_context("") == ""


class TestBuildJudgePrompt:
    """Tests for build_judge_prompt function."""

    def test_basic_prompt(self) -> None:
        """Test building basic prompt."""
        prompt = build_judge_prompt(
            task_prompt="Implement feature X",
            criteria="Tests must pass",
            rubric="R001: Feature works",
        )
        assert "Implement feature X" in prompt
        assert "Tests must pass" in prompt
        assert "R001: Feature works" in prompt
        assert "BEGIN EVALUATION" in prompt

    def test_prompt_with_tier(self) -> None:
        """Test building prompt with tier context."""
        prompt = build_judge_prompt(
            task_prompt="Task",
            criteria="Criteria",
            rubric="Rubric",
            tier_id="T3",
        )
        assert "Tooling" in prompt
        assert "function calling" in prompt

    def test_prompt_without_tier(self) -> None:
        """Test building prompt without tier context."""
        prompt = build_judge_prompt(
            task_prompt="Task",
            criteria="Criteria",
            rubric="Rubric",
            tier_id=None,
        )
        # Should not contain tier-specific text
        assert "Tier Context:" not in prompt

    def test_prompt_includes_all_categories(self) -> None:
        """Test prompt includes all evaluation categories."""
        prompt = build_judge_prompt(
            task_prompt="Task",
            criteria="Criteria",
            rubric="Rubric",
        )
        assert "Functional Correctness" in prompt
        assert "Completeness" in prompt
        assert "Code Quality" in prompt
        assert "Simplicity" in prompt
        assert "Lack of Duplication" in prompt
        assert "Clarity" in prompt
        assert "Documentation" in prompt
        assert "Architectural Cleanliness" in prompt
        assert "Efficiency" in prompt
        assert "Cleanup Script Quality" in prompt

    def test_prompt_includes_json_schema(self) -> None:
        """Test prompt includes JSON schema."""
        prompt = build_judge_prompt(
            task_prompt="Task",
            criteria="Criteria",
            rubric="Rubric",
        )
        assert "exploratory_testing" in prompt
        assert "requirements" in prompt
        assert "categories" in prompt
        assert "summary" in prompt

    def test_prompt_includes_three_phases(self) -> None:
        """Test prompt includes all three evaluation phases."""
        prompt = build_judge_prompt(
            task_prompt="Task",
            criteria="Criteria",
            rubric="Rubric",
        )
        assert "Phase 1: Exploratory Testing" in prompt
        assert "Phase 2: Holistic Assessment" in prompt
        assert "Phase 3: Rubric Scoring" in prompt


class TestCalculateWeightedCategoryScore:
    """Tests for weighted category score calculation."""

    def test_empty_categories(self) -> None:
        """Test empty categories returns 0."""
        assert calculate_weighted_category_score({}) == 0.0

    def test_single_category(self) -> None:
        """Test single category score."""
        categories = {
            "functional_correctness": CategoryScore(score=0.8, confidence=0.9),
        }
        # Weight is 2.0, score is 0.8 -> 0.8
        assert calculate_weighted_category_score(categories) == pytest.approx(0.8)

    def test_multiple_categories(self) -> None:
        """Test multiple category weighted score."""
        categories = {
            "functional_correctness": CategoryScore(score=1.0, confidence=0.9),  # weight 2.0
            "completeness": CategoryScore(score=0.5, confidence=0.9),  # weight 1.5
        }
        # (1.0 * 2.0 + 0.5 * 1.5) / (2.0 + 1.5) = 2.75 / 3.5 = 0.7857...
        expected = (1.0 * 2.0 + 0.5 * 1.5) / (2.0 + 1.5)
        assert calculate_weighted_category_score(categories) == pytest.approx(expected)

    def test_all_categories(self) -> None:
        """Test with all categories at same score."""
        categories = {
            category.value: CategoryScore(score=0.8, confidence=0.9)
            for category in EvaluationCategory
        }
        # All same score, so weighted average is same
        assert calculate_weighted_category_score(categories) == pytest.approx(0.8)

    def test_unknown_category(self) -> None:
        """Test unknown category uses default weight."""
        categories = {
            "unknown_category": CategoryScore(score=0.5, confidence=0.9),
        }
        # Unknown category gets weight 1.0
        assert calculate_weighted_category_score(categories) == pytest.approx(0.5)


class TestGetCategoryDescriptions:
    """Tests for category descriptions."""

    def test_all_categories_have_descriptions(self) -> None:
        """Test all categories have descriptions."""
        descriptions = get_category_descriptions()
        for category in EvaluationCategory:
            assert category.value in descriptions

    def test_descriptions_are_nonempty(self) -> None:
        """Test all descriptions are non-empty strings."""
        descriptions = get_category_descriptions()
        for desc in descriptions.values():
            assert isinstance(desc, str)
            assert len(desc) > 0


class TestValidateJudgmentOutput:
    """Tests for judgment output validation."""

    def test_valid_output(self) -> None:
        """Test validating valid output."""
        raw = {
            "summary": {
                "weighted_score": 0.8,
                "passed": True,
                "letter_grade": "B",
                "overall_confidence": 0.9,
            }
        }
        output = validate_judgment_output(raw)
        assert isinstance(output, JudgmentOutput)
        assert output.summary.passed is True

    def test_full_output(self) -> None:
        """Test validating full output."""
        raw = {
            "exploratory_testing": {
                "commands_run": ["pytest"],
                "observations": ["Pass"],
                "failures": [],
            },
            "requirements": {
                "R001": {"score": 0.9, "confidence": 0.9, "notes": "Good"},
            },
            "categories": {
                "functional_correctness": {"score": 0.9, "confidence": 0.9, "notes": "Works"},
            },
            "summary": {
                "weighted_score": 0.9,
                "passed": True,
                "letter_grade": "A",
                "overall_confidence": 0.9,
                "strengths": ["Clean"],
                "weaknesses": [],
            },
            "qualitative_feedback": "Great job",
        }
        output = validate_judgment_output(raw)
        assert output.requirements["R001"].score == 0.9
        assert output.categories["functional_correctness"].score == 0.9

    def test_invalid_output(self) -> None:
        """Test validating invalid output raises error."""
        raw = {"invalid": "data"}
        with pytest.raises(ValueError):
            validate_judgment_output(raw)


class TestJudgePromptTemplate:
    """Tests for the main prompt template."""

    def test_template_has_placeholders(self) -> None:
        """Test template has required placeholders."""
        assert "{task_prompt}" in JUDGE_PROMPT_TEMPLATE
        assert "{criteria}" in JUDGE_PROMPT_TEMPLATE
        assert "{rubric}" in JUDGE_PROMPT_TEMPLATE
        assert "{tier_context}" in JUDGE_PROMPT_TEMPLATE
        assert "{json_schema}" in JUDGE_PROMPT_TEMPLATE

    def test_template_includes_weights(self) -> None:
        """Test template includes category weights."""
        assert "2.0" in JUDGE_PROMPT_TEMPLATE  # Functional Correctness
        assert "1.5" in JUDGE_PROMPT_TEMPLATE  # Completeness
        assert "0.5" in JUDGE_PROMPT_TEMPLATE  # Documentation, etc.


class TestJsonOutputSchema:
    """Tests for JSON output schema."""

    def test_schema_includes_all_sections(self) -> None:
        """Test schema includes all required sections."""
        assert "exploratory_testing" in JSON_OUTPUT_SCHEMA
        assert "requirements" in JSON_OUTPUT_SCHEMA
        assert "categories" in JSON_OUTPUT_SCHEMA
        assert "summary" in JSON_OUTPUT_SCHEMA
        assert "qualitative_feedback" in JSON_OUTPUT_SCHEMA

    def test_schema_includes_all_categories(self) -> None:
        """Test schema includes all evaluation categories."""
        for category in EvaluationCategory:
            assert category.value in JSON_OUTPUT_SCHEMA
