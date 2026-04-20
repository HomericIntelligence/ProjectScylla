"""Check cyclomatic complexity against a threshold."""

# Thin re-export wrapper — functionality moved to hephaestus.
# Remove in next release cycle after consumers are updated.
# See: HomericIntelligence/ProjectHephaestus#<PR>
from hephaestus.validation.complexity import *  # noqa: F403

if __name__ == "__main__":
    import sys

    from hephaestus.validation.complexity import main

    sys.exit(main())
