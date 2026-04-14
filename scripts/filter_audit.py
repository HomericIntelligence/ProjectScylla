"""Filter pip-audit JSON output to fail only on HIGH/CRITICAL severity vulnerabilities."""
# Thin re-export wrapper — functionality moved to hephaestus.
# Remove in next release cycle after consumers are updated.
# See: HomericIntelligence/ProjectHephaestus#<PR>
from hephaestus.ci.pip_audit import *  # noqa: F401,F403

if __name__ == "__main__":
    import sys
    from hephaestus.ci.pip_audit import main
    sys.exit(main())
