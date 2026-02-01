"""Unit tests for DataFrame builder functions using mock RunData."""

import numpy as np
import pandas as pd
import pytest

from scylla.analysis.dataframes import build_criteria_df, build_judges_df, build_runs_df
from scylla.analysis.loader import CriterionScore, ItemScore, JudgeEvaluation, RunData
from scylla.e2e.models import TokenStats


@pytest.fixture
def mock_criterion_scores():
    """Create mock criterion scores for testing."""
    return {
        "functional": CriterionScore(
            name="functional",
            achieved=8.0,
            max_points=10.0,
            score=0.8,
            items={
                "F1": ItemScore(
                    item_id="F1", achieved=3.0, max_points=4.0, reason="Good implementation"
                ),
                "F2": ItemScore(item_id="F2", achieved=5.0, max_points=6.0, reason="Minor issues"),
            },
        ),
        "code_quality": CriterionScore(
            name="code_quality",
            achieved=7.0,
            max_points=10.0,
            score=0.7,
            items={
                "Q1": ItemScore(item_id="Q1", achieved=4.0, max_points=5.0, reason="Clean code"),
                "Q2": ItemScore(item_id="Q2", achieved=3.0, max_points=5.0, reason="Some issues"),
            },
        ),
    }


@pytest.fixture
def mock_judges(mock_criterion_scores):
    """Create mock judge evaluations for testing."""
    return [
        JudgeEvaluation(
            judge_model="claude-opus-4-5-20251101",
            judge_number=1,
            score=0.75,
            passed=True,
            grade="B",
            is_valid=True,
            reasoning="Good work overall",
            criteria=mock_criterion_scores,
        ),
        JudgeEvaluation(
            judge_model="claude-sonnet-4-5-20250929",
            judge_number=2,
            score=0.80,
            passed=True,
            grade="A",
            is_valid=True,
            reasoning="Excellent implementation",
            criteria=mock_criterion_scores,
        ),
        JudgeEvaluation(
            judge_model="claude-haiku-4-5-20241223",
            judge_number=3,
            score=0.70,
            passed=True,
            grade="B",
            is_valid=True,
            reasoning="Solid work",
            criteria=mock_criterion_scores,
        ),
    ]


@pytest.fixture
def mock_run_data(mock_judges):
    """Create a mock RunData object for testing."""
    return RunData(
        experiment="test-experiment-001",
        agent_model="Sonnet 4.5",
        tier="T0",
        subtest="test-01",
        run_number=1,
        score=0.75,
        passed=True,
        grade="B",
        cost_usd=0.05,
        duration_seconds=120.5,
        agent_duration_seconds=100.0,
        judge_duration_seconds=20.5,
        token_stats=TokenStats(
            input_tokens=1000,
            output_tokens=500,
            cache_creation_tokens=200,
            cache_read_tokens=300,
        ),
        exit_code=0,
        judges=mock_judges,
    )


def test_build_runs_df_with_mock_data(mock_run_data):
    """Test build_runs_df with mock RunData objects."""
    # Arrange
    experiments = {"test-experiment-001": [mock_run_data]}

    # Act
    df = build_runs_df(experiments)

    # Assert
    assert len(df) == 1
    assert df.iloc[0]["experiment"] == "test-experiment-001"
    assert df.iloc[0]["agent_model"] == "Sonnet 4.5"
    assert df.iloc[0]["tier"] == "T0"
    assert df.iloc[0]["subtest"] == "test-01"
    assert df.iloc[0]["run_number"] == 1
    assert df.iloc[0]["score"] == 0.75
    assert df.iloc[0]["passed"] is True
    assert df.iloc[0]["grade"] == "B"
    assert df.iloc[0]["cost_usd"] == 0.05


def test_build_runs_df_impl_rate_consensus(mock_run_data):
    """Test that build_runs_df correctly computes consensus impl_rate as median."""
    # Arrange
    experiments = {"test-001": [mock_run_data]}

    # Act
    df = build_runs_df(experiments)

    # Assert - impl_rate should be median of judge impl_rates
    # Each judge has: (8+7)/(10+10) = 15/20 = 0.75
    expected_impl_rate = 0.75
    assert "impl_rate" in df.columns
    assert abs(df.iloc[0]["impl_rate"] - expected_impl_rate) < 1e-6


def test_build_runs_df_token_stats(mock_run_data):
    """Test that build_runs_df correctly extracts token statistics."""
    # Arrange
    experiments = {"test-001": [mock_run_data]}

    # Act
    df = build_runs_df(experiments)

    # Assert
    assert df.iloc[0]["input_tokens"] == 1000
    assert df.iloc[0]["output_tokens"] == 500
    assert df.iloc[0]["cache_creation_tokens"] == 200
    assert df.iloc[0]["cache_read_tokens"] == 300
    # total_tokens is computed: input + output + cache_creation + cache_read
    # = 1000 + 500 + 200 + 300 = 2000
    assert df.iloc[0]["total_tokens"] == 2000


def test_build_runs_df_multiple_runs(mock_run_data):
    """Test build_runs_df with multiple runs."""
    # Arrange - create second run with different data
    run2 = RunData(
        experiment="test-experiment-001",
        agent_model="Haiku 4.5",
        tier="T1",
        subtest="test-02",
        run_number=2,
        score=0.60,
        passed=False,
        grade="D",
        cost_usd=0.03,
        duration_seconds=90.0,
        agent_duration_seconds=75.0,
        judge_duration_seconds=15.0,
        token_stats=TokenStats(
            input_tokens=800, output_tokens=400, cache_creation_tokens=0, cache_read_tokens=0
        ),
        exit_code=1,
        judges=mock_run_data.judges,  # Reuse same judges for simplicity
    )

    experiments = {"test-001": [mock_run_data, run2]}

    # Act
    df = build_runs_df(experiments)

    # Assert
    assert len(df) == 2
    assert df.iloc[0]["agent_model"] == "Sonnet 4.5"
    assert df.iloc[1]["agent_model"] == "Haiku 4.5"
    assert df.iloc[0]["tier"] == "T0"
    assert df.iloc[1]["tier"] == "T1"


def test_build_runs_df_empty_experiments():
    """Test build_runs_df with empty experiments dict."""
    # Arrange
    experiments = {}

    # Act
    df = build_runs_df(experiments)

    # Assert - empty DataFrame has no columns in current implementation
    assert len(df) == 0
    assert isinstance(df, pd.DataFrame)


def test_build_runs_df_empty_judges():
    """Test build_runs_df handles runs with no judges gracefully."""
    # Arrange
    run_no_judges = RunData(
        experiment="test-001",
        agent_model="Sonnet 4.5",
        tier="T0",
        subtest="test-01",
        run_number=1,
        score=0.0,
        passed=False,
        grade="F",
        cost_usd=0.01,
        duration_seconds=10.0,
        agent_duration_seconds=8.0,
        judge_duration_seconds=2.0,
        token_stats=TokenStats(
            input_tokens=100, output_tokens=50, cache_creation_tokens=0, cache_read_tokens=0
        ),
        exit_code=1,
        judges=[],  # No judges
    )

    experiments = {"test-001": [run_no_judges]}

    # Act
    df = build_runs_df(experiments)

    # Assert
    assert len(df) == 1
    assert np.isnan(df.iloc[0]["impl_rate"])  # Should be NaN when no judges


def test_build_judges_df_with_mock_data(mock_run_data):
    """Test build_judges_df with mock RunData objects."""
    # Arrange
    experiments = {"test-001": [mock_run_data]}

    # Act
    df = build_judges_df(experiments)

    # Assert
    assert len(df) == 3  # 3 judges
    assert (df["experiment"] == "test-experiment-001").all()
    assert (df["agent_model"] == "Sonnet 4.5").all()
    assert (df["tier"] == "T0").all()
    assert (df["subtest"] == "test-01").all()
    assert (df["run_number"] == 1).all()


def test_build_judges_df_judge_fields(mock_run_data):
    """Test build_judges_df correctly extracts judge-specific fields."""
    # Arrange
    experiments = {"test-001": [mock_run_data]}

    # Act
    df = build_judges_df(experiments)

    # Assert - Check first judge
    judge1 = df[df["judge_number"] == 1].iloc[0]
    assert judge1["judge_model"] == "claude-opus-4-5-20251101"
    assert judge1["judge_score"] == 0.75
    assert judge1["judge_passed"] is True
    assert judge1["judge_grade"] == "B"
    assert judge1["judge_is_valid"] is True


def test_build_judges_df_impl_rate_per_judge(mock_run_data):
    """Test that build_judges_df computes impl_rate per judge."""
    # Arrange
    experiments = {"test-001": [mock_run_data]}

    # Act
    df = build_judges_df(experiments)

    # Assert - Each judge should have impl_rate = (8+7)/(10+10) = 0.75
    assert "judge_impl_rate" in df.columns
    expected_impl_rate = 0.75
    for _, row in df.iterrows():
        assert abs(row["judge_impl_rate"] - expected_impl_rate) < 1e-6


def test_build_judges_df_multiple_runs(mock_run_data):
    """Test build_judges_df with multiple runs."""
    # Arrange
    run2 = RunData(
        experiment="test-001",
        agent_model="Haiku 4.5",
        tier="T1",
        subtest="test-02",
        run_number=2,
        score=0.60,
        passed=False,
        grade="D",
        cost_usd=0.03,
        duration_seconds=90.0,
        agent_duration_seconds=75.0,
        judge_duration_seconds=15.0,
        token_stats=TokenStats(
            input_tokens=800, output_tokens=400, cache_creation_tokens=0, cache_read_tokens=0
        ),
        exit_code=1,
        judges=mock_run_data.judges,
    )

    experiments = {"test-001": [mock_run_data, run2]}

    # Act
    df = build_judges_df(experiments)

    # Assert
    assert len(df) == 6  # 2 runs × 3 judges = 6 rows
    run1_judges = df[df["run_number"] == 1]
    run2_judges = df[df["run_number"] == 2]
    assert len(run1_judges) == 3
    assert len(run2_judges) == 3


def test_build_criteria_df_with_mock_data(mock_run_data):
    """Test build_criteria_df with mock RunData objects."""
    # Arrange
    experiments = {"test-001": [mock_run_data]}

    # Act
    df = build_criteria_df(experiments)

    # Assert
    # 3 judges × 2 criteria = 6 rows
    assert len(df) == 6
    assert (df["experiment"] == "test-experiment-001").all()
    assert (df["agent_model"] == "Sonnet 4.5").all()


def test_build_criteria_df_criterion_fields(mock_run_data):
    """Test build_criteria_df correctly extracts criterion fields."""
    # Arrange
    experiments = {"test-001": [mock_run_data]}

    # Act
    df = build_criteria_df(experiments)

    # Assert - Check functional criterion for judge 1
    functional = df[(df["judge_number"] == 1) & (df["criterion"] == "functional")].iloc[0]
    assert functional["criterion_score"] == 0.8
    assert functional["criterion_achieved"] == 8.0
    assert functional["criterion_max"] == 10.0

    # Check code_quality criterion
    code_quality = df[(df["judge_number"] == 1) & (df["criterion"] == "code_quality")].iloc[0]
    assert code_quality["criterion_score"] == 0.7
    assert code_quality["criterion_achieved"] == 7.0
    assert code_quality["criterion_max"] == 10.0


def test_build_criteria_df_multiple_judges(mock_run_data):
    """Test build_criteria_df includes all judges."""
    # Arrange
    experiments = {"test-001": [mock_run_data]}

    # Act
    df = build_criteria_df(experiments)

    # Assert
    unique_judges = df["judge_number"].unique()
    assert len(unique_judges) == 3
    assert set(unique_judges) == {1, 2, 3}

    # Each judge should have 2 criteria
    for judge_num in [1, 2, 3]:
        judge_criteria = df[df["judge_number"] == judge_num]
        assert len(judge_criteria) == 2
        assert set(judge_criteria["criterion"]) == {"functional", "code_quality"}


def test_build_criteria_df_empty_experiments():
    """Test build_criteria_df with empty experiments."""
    # Arrange
    experiments = {}

    # Act
    df = build_criteria_df(experiments)

    # Assert - empty DataFrame has no columns in current implementation
    assert len(df) == 0
    assert isinstance(df, pd.DataFrame)


def test_compute_judge_impl_rate_helper():
    """Test the compute_judge_impl_rate helper function."""
    from scylla.analysis.dataframes import compute_judge_impl_rate

    # Arrange
    criteria = {
        "functional": CriterionScore(
            name="functional",
            achieved=8.0,
            max_points=10.0,
            score=0.8,
            items={},
        ),
        "code_quality": CriterionScore(
            name="code_quality",
            achieved=6.0,
            max_points=10.0,
            score=0.6,
            items={},
        ),
    }

    judge = JudgeEvaluation(
        judge_model="test-model",
        judge_number=1,
        score=0.7,
        passed=True,
        grade="B",
        is_valid=True,
        reasoning="Test",
        criteria=criteria,
    )

    # Act
    impl_rate = compute_judge_impl_rate(judge)

    # Assert - (8+6)/(10+10) = 14/20 = 0.7
    assert abs(impl_rate - 0.7) < 1e-6


def test_compute_consensus_impl_rate_helper():
    """Test the compute_consensus_impl_rate helper function."""
    from scylla.analysis.dataframes import compute_consensus_impl_rate

    # Arrange - create judges with different impl_rates
    judges = []
    for i, (achieved1, achieved2) in enumerate([(8, 6), (9, 7), (7, 5)], start=1):
        criteria = {
            "c1": CriterionScore(
                name="c1", achieved=achieved1, max_points=10.0, score=achieved1 / 10, items={}
            ),
            "c2": CriterionScore(
                name="c2", achieved=achieved2, max_points=10.0, score=achieved2 / 10, items={}
            ),
        }
        judges.append(
            JudgeEvaluation(
                judge_model="test",
                judge_number=i,
                score=0.7,
                passed=True,
                grade="B",
                is_valid=True,
                reasoning="",
                criteria=criteria,
            )
        )

    # Act
    consensus = compute_consensus_impl_rate(judges)

    # Assert - impl_rates are: (8+6)/20=0.7, (9+7)/20=0.8, (7+5)/20=0.6
    # Median of [0.6, 0.7, 0.8] = 0.7
    assert abs(consensus - 0.7) < 1e-6


def test_compute_consensus_impl_rate_empty_judges():
    """Test compute_consensus_impl_rate with empty judge list."""
    from scylla.analysis.dataframes import compute_consensus_impl_rate

    # Act
    consensus = compute_consensus_impl_rate([])

    # Assert
    assert np.isnan(consensus)
