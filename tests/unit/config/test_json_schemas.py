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
        ["defaults.schema.json", "tier.schema.json", "model.schema.json"],
    )
    def test_schema_file_exists(self, schema_name: str) -> None:
        """Schema file must exist."""
        assert (SCHEMAS_DIR / schema_name).exists()

    @pytest.mark.parametrize(
        "schema_name",
        ["defaults.schema.json", "tier.schema.json", "model.schema.json"],
    )
    def test_schema_is_valid_json(self, schema_name: str) -> None:
        """Schema file must be valid JSON."""
        schema = load_schema(schema_name)
        assert isinstance(schema, dict)

    @pytest.mark.parametrize(
        "schema_name",
        ["defaults.schema.json", "tier.schema.json", "model.schema.json"],
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
        ["t0.yaml", "t1.yaml", "t2.yaml", "t3.yaml", "t4.yaml", "t5.yaml", "t6.yaml"],
    )
    def test_real_tier_fixture_is_valid(self, schema: dict[str, Any], fixture_file: str) -> None:
        """Tier fixture files must conform to tier.schema.json."""
        data = load_yaml(TIER_FIXTURES_DIR / fixture_file)
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
            "claude-sonnet-4-5-20250929.yaml",
            "claude-haiku-4-5-20250929.yaml",
            "claude-opus-4-5-20251101.yaml",
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
