"""Tests for judge prompt templates.

Python justification: Required for pytest testing framework.
"""

import pytest

from scylla.judge.prompts import (
    CATEGORY_WEIGHTS,
    JUDGE_SYSTEM_PROMPT_FILE,
    TOTAL_CATEGORY_WEIGHT,
    CategoryScore,
    EvaluationCategory,
    EvaluationSummary,
    ExploratoryTesting,
    JudgmentOutput,
    RequirementScore,
    build_judge_prompt,
    build_task_prompt,
    calculate_weighted_category_score,
    get_category_descriptions,
    validate_judgment_output,
)


class TestEvaluationCategory:
    """Tests for EvaluationCategory enum."""

    def test_all_categories_present(self) -> None:
        """Test all 13 categories are defined."""
        assert len(EvaluationCategory) == 13

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
        assert EvaluationCategory.WORKSPACE_CLEANLINESS.value == "workspace_cleanliness"
        assert EvaluationCategory.TEST_QUALITY.value == "test_quality"
        assert EvaluationCategory.SCOPE_DISCIPLINE.value == "scope_discipline"


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
        assert TOTAL_CATEGORY_WEIGHT == pytest.approx(12.5)

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
        # Valid grades (S-F scale)
        for grade in ["S", "A", "B", "C", "D", "F"]:
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
                "functional_correctness": CategoryScore(score=0.9, confidence=0.9, notes="Works"),
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


class TestSystemPromptFile:
    """Tests for system prompt file constant."""

    def test_system_prompt_file_exists(self) -> None:
        """Test JUDGE_SYSTEM_PROMPT_FILE points to existing file."""
        assert JUDGE_SYSTEM_PROMPT_FILE.exists()
        assert JUDGE_SYSTEM_PROMPT_FILE.name == "system_prompt.md"

    def test_system_prompt_file_readable(self) -> None:
        """Test system prompt file is readable."""
        content = JUDGE_SYSTEM_PROMPT_FILE.read_text()
        assert len(content) > 0
        # Check for key evaluation methodology content
        assert "Evaluation Methodology" in content or "evaluation" in content.lower()


class TestBuildJudgePrompt:
    """Tests for build_judge_prompt function (legacy wrapper)."""

    def test_basic_prompt(self) -> None:
        """Test building basic prompt with system prompt prepended."""
        prompt = build_judge_prompt(
            task_prompt="Implement feature X",
            criteria="Tests must pass",
            rubric="R001: Feature works",
        )
        # Should include task context
        assert "Implement feature X" in prompt
        assert "Tests must pass" in prompt
        assert "R001: Feature works" in prompt
        # Should include system prompt content
        assert "Evaluation Methodology" in prompt or "evaluation" in prompt.lower()

    def test_prompt_includes_system_prompt(self) -> None:
        """Test that system prompt is included."""
        # System prompt content should be present in judge prompts
        system_content = JUDGE_SYSTEM_PROMPT_FILE.read_text()
        # Check a distinctive phrase from system prompt is present
        assert "Evaluation Methodology" in system_content or "Grading Scale" in system_content


class TestBuildTaskPrompt:
    """Tests for build_task_prompt function."""

    def test_basic_task_prompt(self) -> None:
        """Test building basic task prompt."""
        prompt = build_task_prompt(
            task_prompt="Implement feature X",
            agent_output="Feature implemented successfully",
            workspace_state="Files: main.py (modified)",
        )
        assert "Task Given to Agent" in prompt
        assert "Implement feature X" in prompt
        assert "Agent's Output" in prompt
        assert "Feature implemented successfully" in prompt
        assert "Workspace State After Agent Execution" in prompt
        assert "Files: main.py (modified)" in prompt

    def test_task_prompt_with_rubric(self) -> None:
        """Test task prompt includes rubric."""
        prompt = build_task_prompt(
            task_prompt="Task",
            agent_output="Output",
            workspace_state="State",
            rubric_content="R001: Test passes",
        )
        assert "Rubric (Evaluation Criteria)" in prompt
        assert "R001: Test passes" in prompt

    def test_task_prompt_with_patchfile(self) -> None:
        """Test task prompt includes patchfile."""
        prompt = build_task_prompt(
            task_prompt="Task",
            agent_output="Output",
            workspace_state="State",
            patchfile="diff --git a/file.py b/file.py\n+new line",
        )
        assert "Git Diff (Patchfile)" in prompt
        assert "+new line" in prompt

    def test_task_prompt_with_pipeline_results(self) -> None:
        """Test task prompt includes pipeline results."""
        prompt = build_task_prompt(
            task_prompt="Task",
            agent_output="Output",
            workspace_state="State",
            pipeline_result_str="**Overall Status**: ALL PASSED ✓",
        )
        assert "Build/Lint/Test Pipeline Results" in prompt
        assert "ALL PASSED ✓" in prompt

    def test_task_prompt_ends_with_evaluation_instruction(self) -> None:
        """Test task prompt ends with evaluation instruction."""
        prompt = build_task_prompt(
            task_prompt="Task",
            agent_output="Output",
            workspace_state="State",
        )
        assert (
            "Evaluate the agent's work using the rubric and criteria in your system prompt"
            in prompt
        )


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


class TestJudgeSystemPrompt:
    """Tests for the judge system prompt file."""

    def test_system_prompt_has_evaluation_methodology(self) -> None:
        """Test system prompt includes evaluation methodology."""
        content = JUDGE_SYSTEM_PROMPT_FILE.read_text()
        assert "Evaluation Methodology" in content or "evaluation" in content.lower()

    def test_system_prompt_has_json_schema(self) -> None:
        """Test system prompt includes JSON output schema."""
        content = JUDGE_SYSTEM_PROMPT_FILE.read_text()
        assert "exploratory_testing" in content
        assert "requirements" in content
        assert "categories" in content
        assert "summary" in content

    def test_system_prompt_references_grading_scale(self) -> None:
        """Test system prompt references the grading scale file."""
        content = JUDGE_SYSTEM_PROMPT_FILE.read_text()
        # Should reference the grading scale document
        assert "grading-scale" in content.lower() or "grade" in content.lower()
