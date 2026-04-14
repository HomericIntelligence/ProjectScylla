"""Documentation link validation script for ProjectScylla."""
# Thin re-export wrapper — functionality moved to hephaestus.
# Remove in next release cycle after consumers are updated.
# See: HomericIntelligence/ProjectHephaestus#<PR>
from hephaestus.markdown.link_fixer import *  # noqa: F401,F403

if __name__ == "__main__":
    import sys
    from hephaestus.markdown.link_fixer import main
    sys.exit(main())
