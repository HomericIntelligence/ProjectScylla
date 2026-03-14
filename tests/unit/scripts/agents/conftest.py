"""Conftest for scripts/agents tests.

Adds scripts/agents/ to sys.path so that bare imports (e.g. ``from agent_utils
import ...``) used inside the agent scripts resolve correctly when pytest
imports them as ``agents.check_frontmatter`` etc.
"""

from __future__ import annotations

import sys
from pathlib import Path

_AGENTS_DIR = str(Path(__file__).resolve().parents[4] / "scripts" / "agents")
if _AGENTS_DIR not in sys.path:
    sys.path.insert(0, _AGENTS_DIR)
