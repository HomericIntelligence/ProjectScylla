"""Tests for JSON schema files in schemas/.

Validates that each schema:
- Is well-formed JSON
- Passes against real config files
- Rejects invalid data (additionalProperties enforcement)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest
import yaml

# Paths
REPO_ROOT = Path(__file__).parents[3]
SCHEMAS_DIR = REPO_ROOT / "schemas"
CONFIG_DIR = REPO_ROOT / "config"
TIER_FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "config" / "tiers"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_schema(name: str) -> dict[str, Any]:
    """Load a JSON schema by filename."""
    path = SCHEMAS_DIR / name
    with path.open() as f:
        return json.load(f)  # type: ignore[no-any-return]


def load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file as a dict."""
    with path.open() as f:
        return yaml.safe_load(f)  # type: ignore[no-any-return]


def check_schema(instance: dict[str, Any], schema: dict[str, Any]) -> None:
    """Check instance against schema using jsonschema draft-07."""
    validator_cls = jsonschema.validators.validator_for(schema)
    validator = validator_cls(schema)
    validator.validate(instance)


# ---------------------------------------------------------------------------
# Schema loading tests
# ---------------------------------------------------------------------------


class TestSchemaFiles:
    """Verify schema files exist and are valid JSON."""

    @pytest.mark.parametrize(
        "schema_name",
        [
            "defaults.schema.json",
            "tier.schema.json",
            "model.schema.json",
            "test.schema.json",
            "rubric.schema.json",
        ],
    )
    def test_schema_file_exists(self, schema_name: str) -> None:
        """Schema file must exist."""
        assert (SCHEMAS_DIR / schema_name).exists()

    @pytest.mark.parametrize(
        "schema_name",
        [
            "defaults.schema.json",
            "tier.schema.json",
            "model.schema.json",
            "test.schema.json",
            "rubric.schema.json",
        ],
    )
    def test_schema_is_valid_json(self, schema_name: str) -> None:
        """Schema file must be valid JSON."""
        schema = load_schema(schema_name)
        assert isinstance(schema, dict)

    @pytest.mark.parametrize(
        "schema_name",
        [
            "defaults.schema.json",
            "tier.schema.json",
            "model.schema.json",
            "test.schema.json",
            "rubric.schema.json",
        ],
    )
    def test_schema_has_required_keys(self, schema_name: str) -> None:
        """Each schema must have $schema, title, type, and additionalProperties."""
        schema = load_schema(schema_name)
        assert "$schema" in schema
        assert "title" in schema
        assert schema.get("type") == "object"
        assert schema.get("additionalProperties") is False


# ---------------------------------------------------------------------------
# defaults.schema.json
# ---------------------------------------------------------------------------


class TestDefaultsSchema:
    """Tests for defaults.schema.json against config/defaults.yaml."""

    @pytest.fixture
    def schema(self) -> dict[str, Any]:
        """Load defaults schema."""
        return load_schema("defaults.schema.json")

    @pytest.fixture
    def defaults_data(self) -> dict[str, Any]:
        """Load config/defaults.yaml."""
        return load_yaml(CONFIG_DIR / "defaults.yaml")

    def test_real_defaults_yaml_is_valid(
        self, schema: dict[str, Any], defaults_data: dict[str, Any]
    ) -> None:
        """config/defaults.yaml must conform to defaults.schema.json."""
        check_schema(defaults_data, schema)

    def test_rejects_additional_property(self, schema: dict[str, Any]) -> None:
        """Schema must reject unknown top-level keys."""
        with pytest.raises(jsonschema.ValidationError):
            check_schema({"unknown_key": "value"}, schema)

    def test_accepts_empty_object(self, schema: dict[str, Any]) -> None:
        """All fields are optional — empty dict must conform."""
        check_schema({}, schema)

    def test_rejects_invalid_logging_level(self, schema: dict[str, Any]) -> None:
        """logging.level must be one of the valid log levels."""
        with pytest.raises(jsonschema.ValidationError):
            check_schema({"logging": {"level": "VERBOSE"}}, schema)

    def test_rejects_out_of_range_runs_per_eval(self, schema: dict[str, Any]) -> None:
        """evaluation.runs_per_eval must be in [1, 100]."""
        with pytest.raises(jsonschema.ValidationError):
            check_schema({"evaluation": {"runs_per_eval": 0}}, schema)

    def test_seed_allows_null(self, schema: dict[str, Any]) -> None:
        """evaluation.seed can be null."""
        check_schema({"evaluation": {"seed": None}}, schema)

    def test_seed_allows_integer(self, schema: dict[str, Any]) -> None:
        """evaluation.seed can be an integer."""
        check_schema({"evaluation": {"seed": 42}}, schema)


# ---------------------------------------------------------------------------
# tier.schema.json
# ---------------------------------------------------------------------------


class TestTierSchema:
    """Tests for tier.schema.json against fixture tier configs."""

    @pytest.fixture
    def schema(self) -> dict[str, Any]:
        """Load tier schema."""
        return load_schema("tier.schema.json")

    @pytest.mark.parametrize(
        "fixture_file",
        sorted(TIER_FIXTURES_DIR.glob("t*.yaml")),
        ids=lambda p: p.name,
    )
    def test_real_tier_fixture_is_valid(self, schema: dict[str, Any], fixture_file: Path) -> None:
        """Tier fixture files must conform to tier.schema.json."""
        data = load_yaml(fixture_file)
        check_schema(data, schema)

    def test_rejects_missing_tier(self, schema: dict[str, Any]) -> None:
        """Tier is required."""
        with pytest.raises(jsonschema.ValidationError):
            check_schema({"name": "Vanilla"}, schema)

    def test_rejects_missing_name(self, schema: dict[str, Any]) -> None:
        """Name is required."""
        with pytest.raises(jsonschema.ValidationError):
            check_schema({"tier": "t0"}, schema)

    def test_rejects_invalid_tier_format(self, schema: dict[str, Any]) -> None:
        """Tier must match pattern t0-t6."""
        with pytest.raises(jsonschema.ValidationError):
            check_schema({"tier": "T0", "name": "Vanilla"}, schema)

    def test_rejects_out_of_range_tier(self, schema: dict[str, Any]) -> None:
        """Tier t7 is out of range."""
        with pytest.raises(jsonschema.ValidationError):
            check_schema({"tier": "t7", "name": "Beyond"}, schema)

    def test_rejects_additional_property(self, schema: dict[str, Any]) -> None:
        """Schema must reject unknown keys."""
        with pytest.raises(jsonschema.ValidationError):
            check_schema({"tier": "t0", "name": "Vanilla", "unknown": True}, schema)

    def test_system_prompt_allows_null(self, schema: dict[str, Any]) -> None:
        """system_prompt can be null."""
        check_schema({"tier": "t0", "name": "Vanilla", "system_prompt": None}, schema)

    def test_system_prompt_allows_string(self, schema: dict[str, Any]) -> None:
        """system_prompt can be a string."""
        check_schema(
            {"tier": "t1", "name": "Prompted", "system_prompt": "You are helpful."},
            schema,
        )

    def test_minimal_valid_tier(self, schema: dict[str, Any]) -> None:
        """Only tier and name are required."""
        check_schema({"tier": "t3", "name": "Delegation"}, schema)

    @pytest.mark.parametrize("field", ["uses_tools", "uses_delegation", "uses_hierarchy"])
    def test_capability_field_explicit_false(self, schema: dict[str, Any], field: str) -> None:
        """Schema accepts capability fields explicitly set to false."""
        check_schema({"tier": "t0", "name": "Vanilla", field: False}, schema)

    @pytest.mark.parametrize("field", ["uses_tools", "uses_delegation"])
    def test_capability_field_explicit_true(self, schema: dict[str, Any], field: str) -> None:
        """Schema accepts capability fields explicitly set to true."""
        check_schema({"tier": "t4", "name": "Hierarchy", field: True}, schema)

    def test_capability_field_uses_hierarchy_explicit_true(self, schema: dict[str, Any]) -> None:
        """Schema accepts uses_hierarchy=true when uses_delegation=true is also present."""
        check_schema(
            {"tier": "t4", "name": "Hierarchy", "uses_delegation": True, "uses_hierarchy": True},
            schema,
        )

    def test_capability_fields_absent(self, schema: dict[str, Any]) -> None:
        """Schema accepts tier when all capability fields are absent (default-false path)."""
        check_schema({"tier": "t0", "name": "Vanilla"}, schema)

    def test_capability_fields_all_explicit_false(self, schema: dict[str, Any]) -> None:
        """Schema accepts t0/t1 fixture pattern: all three capability fields explicitly false."""
        check_schema(
            {
                "tier": "t0",
                "name": "Vanilla",
                "description": "Base LLM with zero-shot prompting",
                "uses_tools": False,
                "uses_delegation": False,
                "uses_hierarchy": False,
            },
            schema,
        )

    def test_rejects_hierarchy_without_delegation(self, schema: dict[str, Any]) -> None:
        """uses_hierarchy=true without uses_delegation=true must fail schema validation."""
        with pytest.raises(jsonschema.ValidationError):
            check_schema(
                {"tier": "t4", "name": "Invalid", "uses_hierarchy": True, "uses_delegation": False},
                schema,
            )

    def test_accepts_hierarchy_with_delegation(self, schema: dict[str, Any]) -> None:
        """uses_hierarchy=true with uses_delegation=true must pass schema validation."""
        check_schema(
            {"tier": "t4", "name": "Hierarchy", "uses_hierarchy": True, "uses_delegation": True},
            schema,
        )

    def test_accepts_delegation_without_hierarchy(self, schema: dict[str, Any]) -> None:
        """uses_delegation=true without uses_hierarchy (t3 pattern) must pass schema validation."""
        check_schema(
            {"tier": "t3", "name": "Delegation", "uses_delegation": True, "uses_hierarchy": False},
            schema,
        )


# ---------------------------------------------------------------------------
# model.schema.json
# ---------------------------------------------------------------------------


class TestModelSchema:
    """Tests for model.schema.json against config/models/*.yaml."""

    @pytest.fixture
    def schema(self) -> dict[str, Any]:
        """Load model schema."""
        return load_schema("model.schema.json")

    @pytest.mark.parametrize(
        "model_file",
        [
            "claude-sonnet-4-6.yaml",
            "claude-haiku-4-5.yaml",
            "claude-opus-4-6.yaml",
            "goose.yaml",
        ],
    )
    def test_real_model_yaml_is_valid(self, schema: dict[str, Any], model_file: str) -> None:
        """Real model config files must conform to model.schema.json."""
        data = load_yaml(CONFIG_DIR / "models" / model_file)
        check_schema(data, schema)

    def test_rejects_missing_model_id(self, schema: dict[str, Any]) -> None:
        """model_id is required."""
        with pytest.raises(jsonschema.ValidationError):
            check_schema({"name": "Claude"}, schema)

    def test_rejects_additional_property(self, schema: dict[str, Any]) -> None:
        """Schema must reject unknown keys."""
        with pytest.raises(jsonschema.ValidationError):
            check_schema({"model_id": "test-model", "unknown_field": "value"}, schema)

    def test_rejects_out_of_range_temperature(self, schema: dict[str, Any]) -> None:
        """Temperature must be in [0.0, 2.0]."""
        with pytest.raises(jsonschema.ValidationError):
            check_schema({"model_id": "test", "temperature": 3.0}, schema)

    def test_rejects_zero_max_tokens(self, schema: dict[str, Any]) -> None:
        """max_tokens must be >= 1."""
        with pytest.raises(jsonschema.ValidationError):
            check_schema({"model_id": "test", "max_tokens": 0}, schema)

    def test_timeout_allows_null(self, schema: dict[str, Any]) -> None:
        """timeout_seconds can be null."""
        check_schema({"model_id": "test", "timeout_seconds": None}, schema)

    def test_timeout_allows_integer(self, schema: dict[str, Any]) -> None:
        """timeout_seconds can be a valid integer."""
        check_schema({"model_id": "test", "timeout_seconds": 3600}, schema)

    def test_max_cost_allows_null(self, schema: dict[str, Any]) -> None:
        """max_cost_usd can be null."""
        check_schema({"model_id": "test", "max_cost_usd": None}, schema)

    def test_minimal_valid_model(self, schema: dict[str, Any]) -> None:
        """Only model_id is required."""
        check_schema({"model_id": "minimal-model"}, schema)


# ---------------------------------------------------------------------------
# test.schema.json
# ---------------------------------------------------------------------------

TESTS_FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "tests"

_MINIMAL_TEST = {
    "id": "test-001",
    "name": "Hello World",
    "language": "python",
    "source": {
        "repo": "https://github.com/mvillmow/Hello-World",
        "hash": "7fd1a60b01f91b314f59955a4e4d4e80d8edf11d",
    },
    "task": {"prompt_file": "prompt.md"},
    "validation": {
        "criteria_file": "expected/criteria.md",
        "rubric_file": "expected/rubric.yaml",
    },
}


class TestTestSchema:
    """Tests for test.schema.json against fixture test cases."""

    @pytest.fixture
    def schema(self) -> dict[str, Any]:
        """Load test schema."""
        return load_schema("test.schema.json")

    @pytest.mark.parametrize(
        "fixture_dir",
        ["test-001", "test-002"],
    )
    def test_real_test_fixture_is_valid(self, schema: dict[str, Any], fixture_dir: str) -> None:
        """Real test fixture files must conform to test.schema.json."""
        data = load_yaml(TESTS_FIXTURES_DIR / fixture_dir / "test.yaml")
        check_schema(data, schema)

    def test_rejects_missing_required_id(self, schema: dict[str, Any]) -> None:
        """Id is required."""
        data = {k: v for k, v in _MINIMAL_TEST.items() if k != "id"}
        with pytest.raises(jsonschema.ValidationError):
            check_schema(data, schema)

    def test_rejects_missing_required_name(self, schema: dict[str, Any]) -> None:
        """Name is required."""
        data = {k: v for k, v in _MINIMAL_TEST.items() if k != "name"}
        with pytest.raises(jsonschema.ValidationError):
            check_schema(data, schema)

    def test_rejects_missing_required_language(self, schema: dict[str, Any]) -> None:
        """Language is required."""
        data = {k: v for k, v in _MINIMAL_TEST.items() if k != "language"}
        with pytest.raises(jsonschema.ValidationError):
            check_schema(data, schema)

    def test_rejects_additional_property(self, schema: dict[str, Any]) -> None:
        """Schema must reject unknown top-level keys."""
        data = {**_MINIMAL_TEST, "unknown_key": "value"}
        with pytest.raises(jsonschema.ValidationError):
            check_schema(data, schema)

    def test_rejects_invalid_language(self, schema: dict[str, Any]) -> None:
        """Language must be python or mojo."""
        data = {**_MINIMAL_TEST, "language": "javascript"}
        with pytest.raises(jsonschema.ValidationError):
            check_schema(data, schema)

    def test_accepts_optional_tags(self, schema: dict[str, Any]) -> None:
        """Tags array is accepted."""
        data = {**_MINIMAL_TEST, "tags": ["build-system", "migration"]}
        check_schema(data, schema)

    def test_accepts_optional_tiers(self, schema: dict[str, Any]) -> None:
        """Tiers array is accepted."""
        data = {**_MINIMAL_TEST, "tiers": ["T0", "T1", "T2"]}
        check_schema(data, schema)

    def test_accepts_minimal_valid_test(self, schema: dict[str, Any]) -> None:
        """All required fields present, no optional ones."""
        check_schema(_MINIMAL_TEST, schema)


# ---------------------------------------------------------------------------
# rubric.schema.json
# ---------------------------------------------------------------------------

_MINIMAL_RUBRIC_REQUIREMENTS = {
    "requirements": [
        {
            "id": "R001",
            "description": "First requirement",
            "weight": 1.0,
            "evaluation": "binary",
        }
    ],
    "grading": {"pass_threshold": 0.60},
}

_MINIMAL_RUBRIC_CATEGORIES = {
    "categories": {
        "functional": {
            "weight": 1.0,
            "scoring_type": "checklist",
            "items": [{"id": "F1", "check": "File exists", "points": 1.0}],
        }
    },
    "grading": {"pass_threshold": 0.60},
}


class TestRubricSchema:
    """Tests for rubric.schema.json against fixture rubric files."""

    @pytest.fixture
    def schema(self) -> dict[str, Any]:
        """Load rubric schema."""
        return load_schema("rubric.schema.json")

    @pytest.mark.parametrize(
        "fixture_path",
        [
            "test-001/expected/rubric.yaml",
            "test-002/expected/rubric.yaml",
            "test-003/expected/rubric.yaml",
        ],
    )
    def test_real_rubric_fixture_is_valid(self, schema: dict[str, Any], fixture_path: str) -> None:
        """Real rubric fixture files must conform to rubric.schema.json."""
        data = load_yaml(TESTS_FIXTURES_DIR / fixture_path)
        check_schema(data, schema)

    def test_rejects_missing_grading(self, schema: dict[str, Any]) -> None:
        """Grading is required."""
        data = {"requirements": _MINIMAL_RUBRIC_REQUIREMENTS["requirements"]}
        with pytest.raises(jsonschema.ValidationError):
            check_schema(data, schema)

    def test_rejects_additional_top_level_property(self, schema: dict[str, Any]) -> None:
        """Schema must reject unknown top-level keys."""
        data = {**_MINIMAL_RUBRIC_REQUIREMENTS, "unknown_field": "value"}
        with pytest.raises(jsonschema.ValidationError):
            check_schema(data, schema)

    def test_rejects_invalid_pass_threshold(self, schema: dict[str, Any]) -> None:
        """pass_threshold must be in [0.0, 1.0]."""
        data = {**_MINIMAL_RUBRIC_REQUIREMENTS, "grading": {"pass_threshold": 1.5}}
        with pytest.raises(jsonschema.ValidationError):
            check_schema(data, schema)

    def test_accepts_requirements_format(self, schema: dict[str, Any]) -> None:
        """Requirements-based rubric is accepted."""
        check_schema(_MINIMAL_RUBRIC_REQUIREMENTS, schema)

    def test_accepts_categories_format(self, schema: dict[str, Any]) -> None:
        """Categories-based rubric is accepted."""
        check_schema(_MINIMAL_RUBRIC_CATEGORIES, schema)

    def test_accepts_requirement_with_criteria(self, schema: dict[str, Any]) -> None:
        """Requirement items may include optional criteria array."""
        data = {
            "requirements": [
                {
                    "id": "R001",
                    "description": "Check with criteria",
                    "weight": 1.0,
                    "evaluation": "scaled",
                    "criteria": ["criterion one", "criterion two"],
                }
            ],
            "grading": {"pass_threshold": 0.60},
        }
        check_schema(data, schema)

    def test_accepts_minimal_valid_rubric(self, schema: dict[str, Any]) -> None:
        """Only grading is required."""
        check_schema({"grading": {"pass_threshold": 0.60}}, schema)
