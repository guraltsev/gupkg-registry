"""Helpers of the tracker tests: gupkg's tracker services over this registry's own trackers and recorded vendor responses.

Not a test module. It puts the gupkg checkout (``GUPKG_REPO``, see ``_tools/gupkg_location.py``) on ``sys.path``, so the
tests import the real tracker services, the HTTP client and ``FakeSystem`` from gupkg's ``src``; it never imports anything
from gupkg's ``tests``. ``_tests/fixtures/http/<case>.json`` holds the vendor responses of one package's tracker.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from _tools.gupkg_location import GUPKG_REPO, REGISTRY_ROOT

sys.path.insert(0, str(GUPKG_REPO / "src"))
sys.path.append(str(GUPKG_REPO / "src" / "gupkg" / "python" / "Lib" / "site-packages"))  # last: installed packages win

from gupkg.model.manifest import Manifest, ManifestKind, parse_manifest  # noqa: E402
from gupkg.model.scope import make_scope  # noqa: E402
from gupkg.model.settings import LAYER_APP, Layer, default_layer, merge_layers  # noqa: E402
from gupkg.scope import process_mode  # noqa: E402
from gupkg.services.http import HttpClient  # noqa: E402
from gupkg.services.track import TrackEnvironment  # noqa: E402
from gupkg.system.fake import FakeHttp, FakeSystem  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
HTTP_CASES = FIXTURES / "http"
CASES = sorted(HTTP_CASES.glob("*.json"))
CASE_NAMES = [path.stem for path in CASES]


def load_case(name: str) -> dict[str, FakeHttp]:
    """Return ``{url: FakeHttp}`` for the fixture case *name*."""
    document = json.loads((HTTP_CASES / f"{name}.json").read_text(encoding="utf-8"))
    return {
        entry["url"]: FakeHttp(entry.get("body", ""), entry.get("status", 200), entry.get("headers", {}))
        for entry in document["responses"]
    }


def serve(system: FakeSystem, *cases: str) -> FakeSystem:
    """Make *system* serve every response of the fixture *cases*; return it."""
    for case in cases:
        system.urls.update(load_case(case))
    return system


def environment(system: FakeSystem, tmp_path: Path, *, package: str = "pkg") -> TrackEnvironment:
    """Return a ``TrackEnvironment`` over *system* with a client that never sleeps and ignores the process environment."""
    client = HttpClient(system, env={}, sleep=lambda seconds: None, cache_dir=tmp_path / "cache")
    mode = process_mode(system)
    layer = Layer(LAYER_APP, {"schema": 4, "integration": {"integrate": "none"}})
    scope = make_scope(mode, Path("scope-root"), "registry-tests", merge_layers([default_layer(mode.value), layer]), {}, system=system)
    return TrackEnvironment(system, scope, client, work_dir=tmp_path / "work", package=package)


def tracker_manifest(package: str) -> Manifest:
    """Parse the live tracker ``<package>/_check_updates/pkg.toml`` of this registry."""
    text = (REGISTRY_ROOT / package / "_check_updates" / "pkg.toml").read_text(encoding="utf-8")
    return parse_manifest(text, ManifestKind.TRACKER)
