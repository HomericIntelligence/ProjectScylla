"""Tier configuration system for loading and applying tier-specific prompts.

This module provides the TierConfigLoader class for loading tier definitions
from YAML and their associated prompt templates from markdown files.

Python justification: Required for YAML parsing, file I/O, and Pydantic validation.
"""

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class TierDefinition(BaseModel):
    """Definition of a single tier from the YAML configuration."""

    name: str = Field(..., description="Human-readable tier name")
    description: str = Field(..., description="Description of the tier's purpose")
    prompt_file: Optional[str] = Field(
        None, description="Path to prompt markdown file (relative to tiers dir)"
    )
    tools_enabled: Optional[bool] = Field(
        None, description="Whether tools are enabled (None = tool default)"
    )
    delegation_enabled: Optional[bool] = Field(
        None, description="Whether delegation is enabled (None = tool default)"
    )


class TierConfig(BaseModel):
    """Complete tier configuration with loaded prompt content."""

    tier_id: str = Field(..., description="Tier identifier (e.g., 'T0', 'T1', 'T2', 'T3')")
    name: str = Field(..., description="Human-readable tier name")
    description: str = Field(..., description="Description of the tier's purpose")
    prompt_file: Optional[Path] = Field(
        None, description="Absolute path to prompt file"
    )
    prompt_content: Optional[str] = Field(
        None, description="Loaded prompt content"
    )
    tools_enabled: Optional[bool] = Field(
        None, description="Whether tools are enabled"
    )
    delegation_enabled: Optional[bool] = Field(
        None, description="Whether delegation is enabled"
    )

    model_config = {"arbitrary_types_allowed": True}


class TiersDefinitionFile(BaseModel):
    """Root structure of the tiers.yaml file."""

    tiers: dict[str, TierDefinition] = Field(
        ..., description="Mapping of tier IDs to their definitions"
    )

    @field_validator("tiers")
    @classmethod
    def validate_required_tiers(
        cls, v: dict[str, TierDefinition]
    ) -> dict[str, TierDefinition]:
        """Ensure required tiers are present."""
        required = {"T0", "T1", "T2", "T3"}
        missing = required - set(v.keys())
        if missing:
            raise ValueError(f"Missing required tier definitions: {missing}")
        return v


class TierConfigError(Exception):
    """Error raised when tier configuration is invalid or unavailable."""

    pass


class TierConfigLoader:
    """Loads and provides access to tier configurations.

    Loads tier definitions from a YAML file and associated prompt templates
    from markdown files in the tiers directory.

    Example:
        loader = TierConfigLoader(Path("config"))
        t1_config = loader.get_tier("T1")
        print(t1_config.prompt_content)
    """

    def __init__(self, config_dir: Path) -> None:
        """Initialize the loader with the config directory.

        Args:
            config_dir: Path to the config directory containing tiers/tiers.yaml
        """
        self.config_dir = Path(config_dir)
        self.tiers_dir = self.config_dir / "tiers"
        self.tiers_file = self.tiers_dir / "tiers.yaml"
        self._tier_definitions: dict[str, TierDefinition] = {}
        self._load_tiers()

    def _load_tiers(self) -> None:
        """Load tier definitions from the YAML file."""
        import yaml

        if not self.tiers_file.exists():
            raise TierConfigError(f"Tiers file not found: {self.tiers_file}")

        try:
            with open(self.tiers_file) as f:
                raw_data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise TierConfigError(f"Failed to parse tiers.yaml: {e}") from e

        if not raw_data or "tiers" not in raw_data:
            raise TierConfigError("tiers.yaml must contain a 'tiers' key")

        try:
            tiers_def = TiersDefinitionFile.model_validate(raw_data)
            self._tier_definitions = tiers_def.tiers
        except Exception as e:
            raise TierConfigError(f"Invalid tier definitions: {e}") from e

    def get_tier(self, tier_id: str) -> TierConfig:
        """Load configuration for a specific tier.

        Args:
            tier_id: The tier identifier (e.g., "T0", "T1", "T2", "T3")

        Returns:
            TierConfig with loaded prompt content

        Raises:
            TierConfigError: If tier_id is unknown or prompt file is missing
        """
        if tier_id not in self._tier_definitions:
            raise TierConfigError(
                f"Unknown tier: {tier_id}. Available: {list(self._tier_definitions.keys())}"
            )

        tier_def = self._tier_definitions[tier_id]
        prompt_file: Optional[Path] = None
        prompt_content: Optional[str] = None

        if tier_def.prompt_file:
            prompt_file = self.tiers_dir / tier_def.prompt_file
            if not prompt_file.exists():
                raise TierConfigError(
                    f"Prompt file not found for tier {tier_id}: {prompt_file}"
                )
            prompt_content = prompt_file.read_text()

        return TierConfig(
            tier_id=tier_id,
            name=tier_def.name,
            description=tier_def.description,
            prompt_file=prompt_file,
            prompt_content=prompt_content,
            tools_enabled=tier_def.tools_enabled,
            delegation_enabled=tier_def.delegation_enabled,
        )

    def get_all_tiers(self) -> list[TierConfig]:
        """Get all tier configurations.

        Returns:
            List of TierConfig objects for all defined tiers
        """
        return [self.get_tier(tid) for tid in self._tier_definitions.keys()]

    def get_tier_ids(self) -> list[str]:
        """Get list of all available tier IDs.

        Returns:
            List of tier identifiers in definition order
        """
        return list(self._tier_definitions.keys())

    def validate_tier_id(self, tier_id: str) -> bool:
        """Check if a tier ID is valid.

        Args:
            tier_id: The tier identifier to validate

        Returns:
            True if valid, False otherwise
        """
        return tier_id in self._tier_definitions
