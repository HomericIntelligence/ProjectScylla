"""Configuration loader for ProjectScylla.

This module provides the ConfigLoader class for loading and merging YAML
configuration files with a three-level priority hierarchy:
    test-specific > model defaults > global defaults
and complex file operations with error handling.
"""

from pathlib import Path
from typing import Any

import yaml

from .models import (
    ConfigurationError,
    DefaultsConfig,
    EvalCase,
    ModelConfig,
    Rubric,
    ScyllaConfig,
    TierConfig,
)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep merge two dictionaries.

    Values in override take precedence. Nested dicts are merged recursively.
    Lists are replaced entirely (not appended).

    Args:
        base: Base dictionary
        override: Override dictionary (values take precedence)

    Returns:
        Merged dictionary

    """
    result = base.copy()

    for key, value in override.items():
        if value is None:
            # Skip None values - don't override with None
            continue

        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            # Recursively merge nested dicts
            result[key] = _deep_merge(result[key], value)
        else:
            # Override value (including lists)
            result[key] = value

    return result


class ConfigLoader:
    """Load and merge configuration files for ProjectScylla.

    Supports a three-level priority hierarchy:
        1. config/defaults.yaml (REQUIRED - base configuration)
        2. config/models/<model_id>.yaml (optional - model-specific)
        3. tests/<test_id>/config.yaml (optional - test-specific)

    Priority order: test > model > defaults

    Example:
        loader = ConfigLoader()
        config = loader.load(
            test_id="001-justfile-to-makefile",
            model_id="claude-opus-4-5-20251101",
        )

    """

    def __init__(self, base_path: str | Path | None = None) -> None:
        """Initialize the ConfigLoader.

        Args:
            base_path: Base path for configuration files. Defaults to current working directory.

        """
        if base_path is None:
            self.base_path = Path.cwd()
        else:
            self.base_path = Path(base_path)

    def _load_yaml(self, path: Path) -> dict[str, Any]:
        """Load a YAML file.

        Args:
            path: Path to YAML file

        Returns:
            Parsed YAML content as dict

        Raises:
            ConfigurationError: If file cannot be read or parsed

        """
        try:
            with open(path) as f:
                content = yaml.safe_load(f)
                return content if content is not None else {}
        except FileNotFoundError:
            raise ConfigurationError(f"Configuration file not found: {path}")
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Invalid YAML in {path}: {e}")
        except PermissionError:
            raise ConfigurationError(f"Permission denied reading: {path}")

    def _load_yaml_optional(self, path: Path) -> dict[str, Any] | None:
        """Load a YAML file if it exists.

        Args:
            path: Path to YAML file

        Returns:
            Parsed YAML content as dict, or None if file doesn't exist

        Raises:
            ConfigurationError: If file exists but cannot be parsed

        """
        if not path.exists():
            return None

        try:
            with open(path) as f:
                content = yaml.safe_load(f)
                return content if content is not None else {}
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Invalid YAML in {path}: {e}")
        except PermissionError:
            raise ConfigurationError(f"Permission denied reading: {path}")

    # -------------------------------------------------------------------------
    # Test Case Loading
    # -------------------------------------------------------------------------

    def load_test(self, test_id: str) -> EvalCase:
        """Load a test case configuration.

        Args:
            test_id: Test identifier (e.g., "001-justfile-to-makefile")

        Returns:
            EvalCase model

        Raises:
            ConfigurationError: If test configuration is invalid or missing

        """
        test_path = self.base_path / "tests" / test_id / "test.yaml"
        data = self._load_yaml(test_path)

        try:
            return EvalCase(**data)
        except Exception as e:
            raise ConfigurationError(f"Invalid test configuration in {test_path}: {e}")

    # -------------------------------------------------------------------------
    # Rubric Loading
    # -------------------------------------------------------------------------

    def load_rubric(self, test_id: str) -> Rubric:
        """Load a rubric for a test case.

        Args:
            test_id: Test identifier

        Returns:
            Rubric model

        Raises:
            ConfigurationError: If rubric is invalid or missing

        """
        rubric_path = self.base_path / "tests" / test_id / "expected" / "rubric.yaml"
        data = self._load_yaml(rubric_path)

        try:
            return Rubric(**data)
        except Exception as e:
            raise ConfigurationError(f"Invalid rubric configuration in {rubric_path}: {e}")

    # -------------------------------------------------------------------------
    # Tier Loading
    # -------------------------------------------------------------------------

    def load_tier(self, tier: str) -> TierConfig:
        """Load a tier configuration.

        Args:
            tier: Tier identifier (e.g., "t0", "t1")

        Returns:
            TierConfig model

        Raises:
            ConfigurationError: If tier configuration is invalid or missing

        """
        # Normalize tier name
        tier = tier.lower().strip()
        if not tier.startswith("t"):
            tier = f"t{tier}"

        tier_path = self.base_path / "config" / "tiers" / f"{tier}.yaml"
        data = self._load_yaml(tier_path)

        # Ensure tier field is set
        if "tier" not in data:
            data["tier"] = tier

        try:
            return TierConfig(**data)
        except Exception as e:
            raise ConfigurationError(f"Invalid tier configuration in {tier_path}: {e}")

    def load_all_tiers(self) -> dict[str, TierConfig]:
        """Load all available tier configurations.

        Returns:
            Dict mapping tier names to TierConfig models

        Raises:
            ConfigurationError: If any tier configuration is invalid

        """
        tiers_dir = self.base_path / "config" / "tiers"
        result: dict[str, TierConfig] = {}

        if not tiers_dir.exists():
            return result

        for tier_file in sorted(tiers_dir.glob("t*.yaml")):
            tier_name = tier_file.stem  # e.g., "t0" from "t0.yaml"
            result[tier_name] = self.load_tier(tier_name)

        return result

    # -------------------------------------------------------------------------
    # Model Loading
    # -------------------------------------------------------------------------

    def load_model(self, model_id: str) -> ModelConfig | None:
        """Load a model configuration.

        Args:
            model_id: Model identifier

        Returns:
            ModelConfig model, or None if not found

        Raises:
            ConfigurationError: If model configuration exists but is invalid

        """
        model_path = self.base_path / "config" / "models" / f"{model_id}.yaml"
        data = self._load_yaml_optional(model_path)

        if data is None:
            return None

        # Ensure model_id is set
        if "model_id" not in data:
            data["model_id"] = model_id

        try:
            return ModelConfig(**data)
        except Exception as e:
            raise ConfigurationError(f"Invalid model configuration in {model_path}: {e}")

    def load_all_models(self) -> dict[str, ModelConfig]:
        """Load all available model configurations.

        Returns:
            Dict mapping model keys (from filename) to ModelConfig models

        Raises:
            ConfigurationError: If any model configuration is invalid

        """
        models_dir = self.base_path / "config" / "models"
        result: dict[str, ModelConfig] = {}

        if not models_dir.exists():
            return result

        for model_file in sorted(models_dir.glob("*.yaml")):
            # Skip special files
            if model_file.name.startswith("."):
                continue

            model_key = model_file.stem  # e.g., "claude-opus-4-5" from "claude-opus-4-5.yaml"
            model = self.load_model(model_key)
            if model:
                result[model_key] = model

        return result

    # -------------------------------------------------------------------------
    # Defaults Loading
    # -------------------------------------------------------------------------

    def load_defaults(self) -> DefaultsConfig:
        """Load global defaults configuration.

        Returns:
            DefaultsConfig model

        Raises:
            ConfigurationError: If defaults.yaml is missing or invalid

        """
        defaults_path = self.base_path / "config" / "defaults.yaml"
        data = self._load_yaml(defaults_path)

        try:
            return DefaultsConfig(**data)
        except Exception as e:
            raise ConfigurationError(f"Invalid defaults configuration in {defaults_path}: {e}")

    # -------------------------------------------------------------------------
    # Merged Configuration Loading
    # -------------------------------------------------------------------------

    def load(self, test_id: str, model_id: str) -> ScyllaConfig:
        """Load and merge configuration for a test run.

        Applies three-level priority hierarchy:
            1. config/defaults.yaml (base)
            2. config/models/<model_id>.yaml (optional)
            3. tests/<test_id>/config.yaml (optional)

        Args:
            test_id: Test identifier
            model_id: Model identifier

        Returns:
            ScyllaConfig with merged configuration

        Raises:
            ConfigurationError: If configuration is invalid

        """
        # Load defaults (required)
        defaults_path = self.base_path / "config" / "defaults.yaml"
        defaults_data = self._load_yaml(defaults_path)

        # Build base config from defaults
        config_data: dict[str, Any] = {}

        # Map evaluation settings to top-level
        if "evaluation" in defaults_data:
            eval_cfg = defaults_data["evaluation"]
            if "runs_per_eval" in eval_cfg:
                config_data["runs_per_tier"] = eval_cfg["runs_per_eval"]
            if "timeout" in eval_cfg:
                config_data["timeout_seconds"] = eval_cfg["timeout"]

        # Copy top-level settings
        for key in [
            "runs_per_tier",
            "timeout_seconds",
            "max_cost_usd",
            "judge",
            "adapters",
            "cleanup",
        ]:
            if key in defaults_data:
                config_data[key] = defaults_data[key]

        # Copy other config sections
        for key in ["output", "logging", "metrics"]:
            if key in defaults_data:
                config_data[key] = defaults_data[key]

        # Load model config (optional)
        model_config = self.load_model(model_id)

        # Apply model overrides
        if model_config:
            if model_config.timeout_seconds is not None:
                config_data["timeout_seconds"] = model_config.timeout_seconds
            if model_config.max_cost_usd is not None:
                config_data["max_cost_usd"] = model_config.max_cost_usd

        # Load test-specific config (optional)
        test_config_path = self.base_path / "tests" / test_id / "config.yaml"
        test_config_data = self._load_yaml_optional(test_config_path)

        if test_config_data:
            config_data = _deep_merge(config_data, test_config_data)

        # Add context
        config_data["test_id"] = test_id
        config_data["model_id"] = model_id
        config_data["model"] = model_config

        try:
            return ScyllaConfig(**config_data)
        except Exception as e:
            raise ConfigurationError(f"Failed to create merged configuration: {e}")
