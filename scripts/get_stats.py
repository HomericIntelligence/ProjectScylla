"""Get GitHub contribution statistics using GitHub CLI."""
# Thin re-export wrapper — functionality moved to hephaestus.
# Remove in next release cycle after consumers are updated.
# See: HomericIntelligence/ProjectHephaestus#<PR>
from hephaestus.github.stats import *  # noqa: F401,F403

if __name__ == "__main__":
    import sys
    from hephaestus.github.stats import main
    sys.exit(main())
