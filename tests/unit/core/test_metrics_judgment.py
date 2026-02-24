"""Tests for MetricsInfoBase and JudgmentInfoBase Pydantic models."""

import pytest
from pydantic import ValidationError

from scylla.core.results import JudgmentInfoBase, MetricsInfoBase
from scylla.reporting.result import JudgmentInfo, MetricsInfo


class TestMetricsInfoBase:
    """Tests for MetricsInfoBase Pydantic model."""

    def test_construction_basic(self) -> None:
        """Basic construction with required fields."""
        m = MetricsInfoBase(tokens_input=100, tokens_output=50)
        assert m.tokens_input == 100
        assert m.tokens_output == 50
        assert m.cost_usd == 0.0

    def test_construction_with_cost(self) -> None:
        """Construction with explicit cost_usd."""
        m = MetricsInfoBase(tokens_input=1000, tokens_output=500, cost_usd=0.05)
        assert m.tokens_input == 1000
        assert m.tokens_output == 500
        assert m.cost_usd == 0.05

    def test_cost_usd_defaults_to_zero(self) -> None:
        """cost_usd should default to 0.0 if not specified."""
        m = MetricsInfoBase(tokens_input=1, tokens_output=1)
        assert m.cost_usd == 0.0

    def test_tokens_input_required(self) -> None:
        """tokens_input is required."""
        with pytest.raises(ValidationError):
            MetricsInfoBase(tokens_output=50)  # type: ignore

    def test_tokens_output_required(self) -> None:
        """tokens_output is required."""
        with pytest.raises(ValidationError):
            MetricsInfoBase(tokens_input=100)  # type: ignore

    def test_immutability(self) -> None:
        """Test that instances are frozen (immutable)."""
        m = MetricsInfoBase(tokens_input=100, tokens_output=50)
        with pytest.raises(ValidationError):
            m.tokens_input = 200

    def test_model_dump(self) -> None:
        """Test Pydantic serialization with .model_dump()."""
        m = MetricsInfoBase(tokens_input=100, tokens_output=50, cost_usd=0.01)
        data = m.model_dump()
        assert data == {
            "tokens_input": 100,
            "tokens_output": 50,
            "cost_usd": 0.01,
        }

    def test_equality(self) -> None:
        """Test Pydantic model equality."""
        m1 = MetricsInfoBase(tokens_input=100, tokens_output=50, cost_usd=0.01)
        m2 = MetricsInfoBase(tokens_input=100, tokens_output=50, cost_usd=0.01)
        m3 = MetricsInfoBase(tokens_input=200, tokens_output=50, cost_usd=0.01)
        assert m1 == m2
        assert m1 != m3

    def test_zero_tokens(self) -> None:
        """Support zero token counts."""
        m = MetricsInfoBase(tokens_input=0, tokens_output=0, cost_usd=0.0)
        assert m.tokens_input == 0
        assert m.tokens_output == 0

    def test_large_values(self) -> None:
        """Support large token counts."""
        m = MetricsInfoBase(tokens_input=1_000_000, tokens_output=500_000, cost_usd=100.50)
        assert m.tokens_input == 1_000_000
        assert m.tokens_output == 500_000
        assert m.cost_usd == 100.50


class TestJudgmentInfoBase:
    """Tests for JudgmentInfoBase Pydantic model."""

    def test_construction_passed(self) -> None:
        """Basic construction for a passing run."""
        j = JudgmentInfoBase(passed=True)
        assert j.passed is True
        assert j.impl_rate == 0.0

    def test_construction_failed(self) -> None:
        """Basic construction for a failing run."""
        j = JudgmentInfoBase(passed=False)
        assert j.passed is False

    def test_construction_with_impl_rate(self) -> None:
        """Construction with explicit impl_rate."""
        j = JudgmentInfoBase(passed=True, impl_rate=0.9)
        assert j.passed is True
        assert j.impl_rate == 0.9

    def test_impl_rate_defaults_to_zero(self) -> None:
        """impl_rate should default to 0.0 if not specified."""
        j = JudgmentInfoBase(passed=False)
        assert j.impl_rate == 0.0

    def test_passed_required(self) -> None:
        """Passed is required."""
        with pytest.raises(ValidationError):
            JudgmentInfoBase()  # type: ignore

    def test_immutability(self) -> None:
        """Test that instances are frozen (immutable)."""
        j = JudgmentInfoBase(passed=True, impl_rate=0.9)
        with pytest.raises(ValidationError):
            j.passed = False

    def test_model_dump(self) -> None:
        """Test Pydantic serialization with .model_dump()."""
        j = JudgmentInfoBase(passed=True, impl_rate=0.85)
        data = j.model_dump()
        assert data == {
            "passed": True,
            "impl_rate": 0.85,
        }

    def test_equality(self) -> None:
        """Test Pydantic model equality."""
        j1 = JudgmentInfoBase(passed=True, impl_rate=0.9)
        j2 = JudgmentInfoBase(passed=True, impl_rate=0.9)
        j3 = JudgmentInfoBase(passed=False, impl_rate=0.9)
        assert j1 == j2
        assert j1 != j3

    def test_impl_rate_boundary_values(self) -> None:
        """Support boundary impl_rate values (0.0, 1.0)."""
        j_zero = JudgmentInfoBase(passed=False, impl_rate=0.0)
        j_one = JudgmentInfoBase(passed=True, impl_rate=1.0)
        assert j_zero.impl_rate == 0.0
        assert j_one.impl_rate == 1.0


class TestMetricsInfoInheritance:
    """Tests for MetricsInfo inheritance from MetricsInfoBase."""

    def test_metrics_info_is_metrics_info_base(self) -> None:
        """MetricsInfo is an instance of MetricsInfoBase."""
        m = MetricsInfo(tokens_input=100, tokens_output=50, cost_usd=0.01, api_calls=3)
        assert isinstance(m, MetricsInfoBase)

    def test_base_fields_accessible(self) -> None:
        """Base fields are accessible in MetricsInfo."""
        m = MetricsInfo(tokens_input=100, tokens_output=50, cost_usd=0.01, api_calls=3)
        assert m.tokens_input == 100
        assert m.tokens_output == 50
        assert m.cost_usd == 0.01

    def test_subtype_field_accessible(self) -> None:
        """MetricsInfo-specific field api_calls is accessible."""
        m = MetricsInfo(tokens_input=100, tokens_output=50, cost_usd=0.01, api_calls=3)
        assert m.api_calls == 3

    def test_api_calls_required(self) -> None:
        """api_calls is required in MetricsInfo."""
        with pytest.raises(ValidationError):
            MetricsInfo(tokens_input=100, tokens_output=50)  # type: ignore

    def test_model_dump_includes_all_fields(self) -> None:
        """model_dump includes both base and subtype fields."""
        m = MetricsInfo(tokens_input=100, tokens_output=50, cost_usd=0.01, api_calls=3)
        data = m.model_dump()
        assert data == {
            "tokens_input": 100,
            "tokens_output": 50,
            "cost_usd": 0.01,
            "api_calls": 3,
        }

    def test_immutability_inherited(self) -> None:
        """Frozen immutability is enforced in MetricsInfo."""
        m = MetricsInfo(tokens_input=100, tokens_output=50, cost_usd=0.01, api_calls=3)
        with pytest.raises(ValidationError):
            m.tokens_input = 200


class TestJudgmentInfoInheritance:
    """Tests for JudgmentInfo inheritance from JudgmentInfoBase."""

    def test_judgment_info_is_judgment_info_base(self) -> None:
        """JudgmentInfo is an instance of JudgmentInfoBase."""
        j = JudgmentInfo(passed=True, impl_rate=0.9, letter_grade="A")
        assert isinstance(j, JudgmentInfoBase)

    def test_base_fields_accessible(self) -> None:
        """Base fields are accessible in JudgmentInfo."""
        j = JudgmentInfo(passed=True, impl_rate=0.9, letter_grade="A")
        assert j.passed is True
        assert j.impl_rate == 0.9

    def test_subtype_field_accessible(self) -> None:
        """JudgmentInfo-specific field letter_grade is accessible."""
        j = JudgmentInfo(passed=True, impl_rate=0.9, letter_grade="A")
        assert j.letter_grade == "A"

    def test_letter_grade_required(self) -> None:
        """letter_grade is required in JudgmentInfo."""
        with pytest.raises(ValidationError):
            JudgmentInfo(passed=True, impl_rate=0.9)  # type: ignore

    def test_model_dump_includes_all_fields(self) -> None:
        """model_dump includes both base and subtype fields."""
        j = JudgmentInfo(passed=True, impl_rate=0.9, letter_grade="A")
        data = j.model_dump()
        assert data == {
            "passed": True,
            "impl_rate": 0.9,
            "letter_grade": "A",
        }

    def test_immutability_inherited(self) -> None:
        """Frozen immutability is enforced in JudgmentInfo."""
        j = JudgmentInfo(passed=True, impl_rate=0.9, letter_grade="A")
        with pytest.raises(ValidationError):
            j.passed = False

    @pytest.mark.parametrize("grade", ["A", "B", "C", "D", "F"])
    def test_all_letter_grades(self, grade: str) -> None:
        """Test all standard letter grades."""
        j = JudgmentInfo(passed=(grade == "A"), impl_rate=0.9, letter_grade=grade)
        assert j.letter_grade == grade
