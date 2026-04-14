"""Enforce Python version consistency between pyproject.toml and Dockerfile."""
# Thin re-export wrapper — functionality moved to hephaestus.
# Remove in next release cycle after consumers are updated.
# See: HomericIntelligence/ProjectHephaestus#<PR>
from hephaestus.version.consistency import *  # noqa: F401,F403

if __name__ == "__main__":
    import sys
    from hephaestus.version.consistency import check_version_consistency_main
    sys.exit(check_version_consistency_main())
