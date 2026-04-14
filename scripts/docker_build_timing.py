"""Docker build timing utilities."""
# Thin re-export wrapper — functionality moved to hephaestus.
# Remove in next release cycle after consumers are updated.
# See: HomericIntelligence/ProjectHephaestus#<PR>
from hephaestus.ci.docker_timing import *  # noqa: F401,F403

if __name__ == "__main__":
    import sys
    from hephaestus.ci.docker_timing import main
    sys.exit(main())
