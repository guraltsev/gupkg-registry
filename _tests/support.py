"""Helpers of the tracker tests: gupkg's tracker services over this registry's own trackers and recorded vendor responses.

Not a test module. It puts the gupkg checkout (``GUPKG_REPO``, see ``_tools/gupkg_location.py``) on ``sys.path``, so the
tests import the real tracker services, the HTTP client and ``FakeSystem`` from gupkg's ``src``; it never imports anything
from gupkg's ``tests``. ``_tests/fixtures/http/<case>.json`` holds the vendor responses of one package's tracker.
"""

from __future__ import annotations

import io
import json
import sys
import tarfile
import tomllib
import zipfile
from pathlib import Path
from typing import Any

from _tools.gupkg_location import GUPKG_REPO, REGISTRY_ROOT

sys.path.insert(0, str(GUPKG_REPO / "src"))
sys.path.append(str(GUPKG_REPO / "src" / "gupkg" / "python" / "Lib" / "site-packages"))  # last: installed packages win

from gupkg.model.manifest import Manifest, ManifestKind, parse_manifest  # noqa: E402
from gupkg.model.scope import make_scope  # noqa: E402
from gupkg.model.settings import LAYER_APP, Layer, default_layer, merge_layers  # noqa: E402
from gupkg.scope import process_mode  # noqa: E402
from gupkg.services.http import HttpClient  # noqa: E402
from gupkg.services.track import TrackEnvironment  # noqa: E402
from gupkg.extractors import find_7z  # noqa: E402
from gupkg.system.fake import FakeHttp, FakeSystem, ProcessCall  # noqa: E402
from gupkg.system.port import ProcessResult  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
HTTP_CASES = FIXTURES / "http"
CASES = sorted(HTTP_CASES.glob("*.json"))
PACKAGES = sorted(path.parent.parent.name for path in REGISTRY_ROOT.glob("*/_check_updates/pkg.toml") if not path.parts[-3].startswith(("_", ".")))


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


def tracker_data(package: str) -> dict[str, Any]:
    """Return the parsed ``<package>/_check_updates/pkg.toml`` of this registry."""
    return tomllib.loads((REGISTRY_ROOT / package / "_check_updates" / "pkg.toml").read_text(encoding="utf-8"))


# -- archives built at test time (nothing binary is committed) ---------------------------------------------------


def make_zip(path: Path, members: dict[str, bytes | str]) -> Path:
    """Write a zip archive of *members* and return its path."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    return path


def make_tar(path: Path, members: dict[str, bytes], mode: str = "w") -> Path:
    """Write a tarball of ``{name: data}`` regular files and return its path."""
    with tarfile.open(path, mode) as archive:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    return path


def make_7z(system: FakeSystem, path: Path, files: dict[str, str]) -> Path:
    """Build a 7z archive of *files* with the 7-Zip bundled with gupkg and return its path."""
    source = path.parent / f"{path.stem}-src"
    for name, content in files.items():
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    result = system.run([str(find_7z()), "a", "-bd", str(path), "*"], cwd=source)
    assert result.returncode == 0, result.stdout
    return path


def tree(root: Path) -> dict[str, str]:
    """Return ``{relative posix path: text}`` of every file below *root*."""
    return {path.relative_to(root).as_posix(): path.read_text(encoding="utf-8") for path in sorted(root.rglob("*")) if path.is_file()}


# -- a scripted git for the Git trackers --------------------------------------------------------------------------

COMMIT = "0123456789abcdef0123456789abcdef01234567"
COMMIT_TIME = 1728720930  # 2024-10-12 08:15:30 UTC


def scripted_git(call: ProcessCall) -> ProcessResult:
    """Answer the ``git`` commands a Git tracker makes (``ls-remote``, ``fetch``, ``log``, ``rev-parse``, ``checkout``): one commit, made at ``COMMIT_TIME``."""
    words = list(call.argv[1:])
    while words[:1] == ["-c"]:
        words = words[2:]
    if words[0] == "ls-remote":
        return ProcessResult(0, f"{COMMIT}\t{words[-1]}\n")
    if words[0] == "log":
        return ProcessResult(0, f"{COMMIT_TIME}\n")
    if words[0] == "rev-parse":
        return ProcessResult(0, f"{COMMIT}\n")
    if words[0] == "checkout":
        (call.cwd / ".git").mkdir()
        (call.cwd / ".git" / "HEAD").write_text("ref", encoding="utf-8")
    return ProcessResult(0)
