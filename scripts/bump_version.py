"""Bump the project version in pyproject.toml and pixi.toml atomically."""
# Thin re-export wrapper — functionality moved to hephaestus.
# Remove in next release cycle after consumers are updated.
# See: HomericIntelligence/ProjectHephaestus#<PR>
from hephaestus.version.consistency import *  # noqa: F401,F403

if __name__ == "__main__":
    import sys
    from hephaestus.version.consistency import bump_version_main
    sys.exit(bump_version_main())
