"""Locate the gupkg checkout whose code and launcher this registry is tested against."""

from __future__ import annotations

import os
from pathlib import Path

REGISTRY_ROOT = Path(__file__).resolve().parents[1]


def find_gupkg_repo() -> Path:
    """Return the gupkg repository root.

    Looked up in ``GUPKG_REPO``, then the folder that contains this registry
    checkout, then a sibling folder named ``gupkg``.

    Raises
    ------
    RuntimeError
        If none of them holds ``src/gupkg/cli.py``.
    """
    candidates = [os.environ.get("GUPKG_REPO"), REGISTRY_ROOT.parent, REGISTRY_ROOT.parent / "gupkg"]
    for candidate in candidates:
        if candidate and (Path(candidate) / "src" / "gupkg" / "cli.py").is_file():
            return Path(candidate)
    raise RuntimeError("Cannot find the gupkg repository. Set GUPKG_REPO to its folder.")


GUPKG_REPO = find_gupkg_repo()
