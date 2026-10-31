"""Shared helpers of the registry tests: they run this repository's two scripts as child processes.

The registry-wide tests import nothing from gupkg: validation goes through ``_tools/pkg_check.py`` (the stand-in
for ``gupkg pkg check``) and ``_tools/registry_tool.py validate``, which locate gupkg themselves. The tracker tests
import gupkg's services through ``_tests/support.py``; ``system`` below is the ``FakeSystem`` they run on.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

import _tests.support  # noqa: F401  (puts the gupkg checkout's ``src`` on ``sys.path`` before any test module imports ``gupkg``)

REGISTRY_ROOT = Path(__file__).resolve().parents[1]


def run_script(script: str, *arguments: str) -> subprocess.CompletedProcess[str]:
    """Run ``_tools/<script>`` with this Python and return the finished process (output captured as text)."""
    return subprocess.run(
        [sys.executable, str(REGISTRY_ROOT / "_tools" / script), *arguments],
        capture_output=True, text=True, encoding="utf-8", check=False, timeout=600,
    )


@pytest.fixture(scope="session")
def pkg_check_results() -> dict[str, dict[str, list[str]]]:
    """Return ``{directory: {"errors": [...], "warnings": [...]}}`` for every tracker and pinned version."""
    process = run_script("pkg_check.py", "--all", "--json")
    assert process.stdout.strip(), process.stderr
    return {row["path"]: row for row in json.loads(process.stdout)}


@pytest.fixture
def system(tmp_path: Path):
    """A ``FakeSystem`` whose machine is ``tmp_path/machine``: no network, no real processes except the regex worker."""
    from _tests.support import FakeSystem

    return FakeSystem(tmp_path / "machine")
