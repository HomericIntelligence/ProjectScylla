"""Thin wrapper — delegates to hephaestus.markdown.fixer."""
# Thin re-export wrapper — functionality moved to hephaestus.
# Remove in next release cycle after consumers are updated.
# See: HomericIntelligence/ProjectHephaestus#<PR>
from hephaestus.markdown.fixer import *  # noqa: F401,F403

if __name__ == "__main__":
    import sys
    from hephaestus.markdown.fixer import main
    sys.exit(main())
