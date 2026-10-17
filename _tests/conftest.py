"""Make the gupkg sources importable: package hooks and the validator import ``gupkg``."""

from __future__ import annotations

import sys

from _tools.gupkg_location import GUPKG_REPO

SOURCE = str(GUPKG_REPO / "src")
if SOURCE not in sys.path:
    sys.path.insert(0, SOURCE)
