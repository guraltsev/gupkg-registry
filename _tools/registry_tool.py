"""Run gupkg's registry tool against this registry: ``update``, ``pin`` and ``validate``.

A thin launcher: the tool itself (``gupkg_registry`` in the gupkg repository) needs gupkg's source
tree, which this script finds through ``GUPKG_REPO`` (see ``gupkg_location.py``). It defaults
``--registry`` to this checkout.

Usage
-----
``python _tools/registry_tool.py update [PACKAGE ...] [--sandbox DIR] [--auto-push]``
``python _tools/registry_tool.py pin NAME/VERSION``
``python _tools/registry_tool.py validate``
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _tools.gupkg_location import GUPKG_REPO, REGISTRY_ROOT  # noqa: E402

sys.path.insert(0, str(GUPKG_REPO / "src"))
sys.path.append(str(GUPKG_REPO / "src" / "gupkg" / "python" / "Lib" / "site-packages"))  # last: installed packages win

from gupkg_registry.cli import main  # noqa: E402

if __name__ == "__main__":
    arguments = sys.argv[1:]
    if "--registry" not in arguments:
        arguments += ["--registry", str(REGISTRY_ROOT)]
    raise SystemExit(main(arguments))
