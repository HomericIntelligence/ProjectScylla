"""Enforce consistency between documentation metric values and authoritative config sources."""
# Thin re-export wrapper — functionality moved to hephaestus.
# Remove in next release cycle after consumers are updated.
# See: HomericIntelligence/ProjectHephaestus#<PR>
from hephaestus.validation.doc_config import *  # noqa: F401,F403

if __name__ == "__main__":
    import sys
    from hephaestus.validation.doc_config import main
    sys.exit(main())
