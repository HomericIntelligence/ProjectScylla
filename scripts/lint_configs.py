"""Configuration linting tool for ProjectScylla."""
# Thin re-export wrapper — functionality moved to hephaestus.
# Remove in next release cycle after consumers are updated.
# See: HomericIntelligence/ProjectHephaestus#<PR>
from hephaestus.validation.config_lint import *  # noqa: F401,F403

if __name__ == "__main__":
    import sys
    from hephaestus.validation.config_lint import main
    sys.exit(main())
