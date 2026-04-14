"""Validate config files against their JSON schemas as a pre-commit gate."""
# Thin re-export wrapper — functionality moved to hephaestus.
# Remove in next release cycle after consumers are updated.
# See: HomericIntelligence/ProjectHephaestus#<PR>
from hephaestus.validation.schema import *  # noqa: F401,F403

if __name__ == "__main__":
    import sys
    from hephaestus.validation.schema import main
    sys.exit(main())
