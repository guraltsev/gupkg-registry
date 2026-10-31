"""Cover the trackers of the registry: each one finds its newest version and download address in the vendor's responses.

A tracker is a package's ``_check_updates/pkg.toml``: where to look for the newest version and how to build the download address
and checksum from what is found. ``gupkg check-updates`` and the registry tool both run it. Here each live tracker runs through
gupkg's real services (providers, HTTP client, checksum discovery, manifest renderer) against the responses of
``_tests/fixtures/http/<case>.json``, and what comes out is the pinned version directory the tool would write.

Rules covered:

- every tracker but the Git ones has a case, and every case belongs to a package of this registry;
- a tracker finds the version and download address its case expects, and the discovered checksum, if the vendor gives one;
- the pinned version it renders passes the package checker, so a tracker cannot write a version that is invalid;
- the headers the trackers declare (``[track.headers]``, ``[source.headers]``) are exactly the ones pinned in this module, the tracker
  sends its own on its request, and a pinned version keeps the ``[source.headers]``;
- a tracker finds nothing, and says so, in a page that is not the vendor's: it never invents a version;
- the three Git trackers pin the full commit they found;
- ``unversioned`` in ``_registry.toml`` lists exactly the packages whose download address holds no version.

Real: the registry's trackers, gupkg's services and package checker. Replaced: the network (``FakeSystem``) and ``git``.
Out of scope: the live vendors (re-record a case with ``_tools/record_http_fixtures.py``, see the README), how a provider works
(gupkg's own tests) and downloading the artifact.
"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

import pytest

from gupkg.model.manifest import ManifestKind, manifest_to_toml, render_pinned
from gupkg.pkgcheck import check_directory
from gupkg.services.track import TrackError, run_tracker
from gupkg.system.fake import FakeHttp, FakeSystem

from _tests.conftest import REGISTRY_ROOT
from _tests.support import CASES, COMMIT, PACKAGES, environment, load_case, scripted_git, serve, tracker_data, tracker_manifest

GIT_TRACKED = [name for name in PACKAGES if tracker_data(name)["track"]["provider"] == "git"]
UNRELATED_PAGE = "<html><body>This is not the page the tracker was written for.</body></html>"


def read_case(case: Path) -> dict:
    """Return the parsed fixture case file."""
    return json.loads(case.read_text(encoding="utf-8"))


def write_pinned(directory: Path, manifest, result):
    """Render the pinned version a tracker found into ``directory/pinned/<version>/pkg.toml``; return that folder and the manifest."""
    pinned = render_pinned(manifest, result)
    folder = directory / "pinned" / result.version
    folder.mkdir(parents=True)
    (folder / "pkg.toml").write_text(manifest_to_toml(pinned), encoding="utf-8", newline="\n")
    return folder, pinned


def test_every_tracker_but_the_git_ones_has_a_case_and_every_case_has_a_tracker() -> None:
    """A tracker without recorded responses is never run by these tests; a case for a package that is gone tests nothing."""
    covered = {read_case(case)["tracker"] for case in CASES}

    assert set(PACKAGES) - covered == set(GIT_TRACKED) and len(GIT_TRACKED) == 3
    assert covered - set(PACKAGES) == set()


def test_a_case_says_whether_its_responses_were_recorded_or_written_for_the_test() -> None:
    """A case is either synthetic (`recorded` is null) or carries its recording date and the origin `recorded from the live sites`; never both or neither."""
    for case in CASES:
        document = read_case(case)
        if document["recorded"] is None:
            assert document["origin"].startswith("synthetic fixture"), case.name
        else:
            assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", document["recorded"]), case.name
            assert document["origin"].startswith("recorded from the live sites"), case.name


@pytest.mark.parametrize("case", [pytest.param(path, id=path.stem) for path in CASES])
def test_a_tracker_finds_its_version_and_download_in_the_vendors_responses(system: FakeSystem, tmp_path: Path, case: Path) -> None:
    """The tracker finds the newest version, the expanded download address and the vendor's checksum (if any), and the pinned version it writes validates.

    The expected values are the case's own `expected` block, so re-recording a case needs no code edit.
    """
    document = read_case(case)
    expected = document["expected"]
    serve(system, case.stem)
    manifest = tracker_manifest(document["tracker"])

    result = run_tracker(manifest, environment(system, tmp_path, package=document["tracker"]))
    folder, pinned = write_pinned(tmp_path, manifest, result)

    assert result.version == expected["version"]
    assert pinned.source.download_url == expected["download_url"]
    assert pinned.source.sha256 == expected["sha256"]
    assert pinned.source.sha256_from == expected["sha256_from"]
    assert pinned.kind is ManifestKind.VERSION and pinned.track is None
    report = check_directory(folder)
    assert report.errors == () and report.warnings == (), (report.errors, report.warnings)


UA_CHECK = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) gupkg-update-check/1"
ACCEPT_HTML = "text/html,application/xhtml+xml,*/*"
# The headers each package's tracker must send on its request for the page ([track.headers]), written out here as data: a vendor
# that refuses other clients stops answering when one of these is dropped or changed, so changing one is an explicit edit of this list.
TRACK_HEADERS = {
    "SumatraPDF-portable": {"User-Agent": "gupkg-sumatrapdf-update-check/1"},
    "dontsleep": {"User-Agent": "Mozilla/5.0 gupkg-dontsleep-check/1"},
    "graphviz": {"User-Agent": UA_CHECK, "Accept": ACCEPT_HTML},
    "hwinfo": {"User-Agent": UA_CHECK},
    "hwinfo-portable": {"User-Agent": UA_CHECK},
    "hwmonitor": {"User-Agent": UA_CHECK, "Accept": ACCEPT_HTML},
    "irfanview": {"User-Agent": UA_CHECK, "Accept": ACCEPT_HTML},
    "lockhunter": {"User-Agent": UA_CHECK, "Accept": ACCEPT_HTML},
    "netio-gui": {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"},
    "openhardwaremonitor": {"User-Agent": UA_CHECK, "Accept": ACCEPT_HTML},
    "rapidee": {"User-Agent": UA_CHECK, "Accept": ACCEPT_HTML},
    "testdisk": {"User-Agent": UA_CHECK, "Accept": ACCEPT_HTML},
    "tixati": {"User-Agent": "Mozilla/5.0 gupkg-tixati-check/1"},
    "xnviewmp": {"User-Agent": "Mozilla/5.0 gupkg-xnviewmp-check/1"},
}
# The headers the download of a pinned version must send ([source.headers]); hwinfo wants its own download page as Referer.
SOURCE_HEADERS = {
    "SumatraPDF-portable": {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"},
    "hwinfo": {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124 Safari/537.36", "Referer": "https://www.hwinfo.com/download/"},
    "hwinfo-portable": {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124 Safari/537.36", "Referer": "https://www.hwinfo.com/download/"},
    "inkscape": {"User-Agent": "Mozilla/5.0"},
    "irfanview": {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124 Safari/537.36", "Referer": "https://www.irfanview.info/"},
    "shutter-encoder": {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"},
}


def test_the_trackers_carry_exactly_the_pinned_headers() -> None:
    """The packages whose tracker declares `[track.headers]` or `[source.headers]`, and the values, are the ones written in this test.

    Dropping a header from a tracker (or giving it another value) makes a vendor refuse the check or the download, so the registry
    cannot lose one unnoticed; a new or changed header is added to the lists above on purpose.
    """
    track = {name: tracker_data(name)["track"]["headers"] for name in PACKAGES if "headers" in tracker_data(name)["track"]}
    source = {name: tracker_data(name)["source"]["headers"] for name in PACKAGES if "headers" in tracker_data(name).get("source", {})}

    assert track == TRACK_HEADERS
    assert source == SOURCE_HEADERS


@pytest.mark.parametrize("package", [pytest.param(name, id=name) for name in TRACK_HEADERS])
def test_a_tracker_sends_its_pinned_headers_on_the_request_for_the_page(system: FakeSystem, tmp_path: Path, package: str) -> None:
    """The `[track.headers]` of a tracker (a browser User-Agent for a site that refuses others) are sent on its first request, in place of the default."""
    serve(system, next(case.stem for case in CASES if read_case(case)["tracker"] == package))

    run_tracker(tracker_manifest(package), environment(system, tmp_path, package=package))

    sent = {name.lower(): value for name, value in system.request_log[0].headers.items()}
    assert {name: sent.get(name.lower()) for name in TRACK_HEADERS[package]} == TRACK_HEADERS[package]


@pytest.mark.parametrize("package", [pytest.param(name, id=name) for name in SOURCE_HEADERS])
def test_the_pinned_version_keeps_the_pinned_headers_the_download_needs(system: FakeSystem, tmp_path: Path, package: str) -> None:
    """The `[source.headers]` of a tracker (for example a Referer a site demands) are written into the pinned version, so the download sends them."""
    serve(system, next(case.stem for case in CASES if read_case(case)["tracker"] == package))
    manifest = tracker_manifest(package)

    result = run_tracker(manifest, environment(system, tmp_path, package=package))

    assert dict(render_pinned(manifest, result).source.headers) == SOURCE_HEADERS[package]


@pytest.mark.parametrize("case", [pytest.param(path, id=path.stem) for path in CASES])
def test_a_tracker_finds_nothing_in_a_page_that_is_not_the_vendors(system: FakeSystem, tmp_path: Path, case: Path) -> None:
    """When the vendor's page changes beyond the tracker's pattern, the check fails with a message instead of pinning a made-up version."""
    document = read_case(case)
    for url in load_case(case.stem):
        system.urls[url] = FakeHttp(UNRELATED_PAGE)

    with pytest.raises(TrackError):
        run_tracker(tracker_manifest(document["tracker"]), environment(system, tmp_path, package=document["tracker"]))


@pytest.mark.parametrize("package", [pytest.param(name, id=name) for name in GIT_TRACKED])
def test_a_git_tracker_pins_the_commit_it_found(tmp_path: Path, package: str) -> None:
    """The version is the commit's date and short hash, the pinned source names the full commit (the integrity anchor, so no `sha256`), and it validates."""
    machine = FakeSystem(tmp_path / "machine", processes={"git": scripted_git}, real_7zip=False)
    manifest = tracker_manifest(package)

    result = run_tracker(manifest, environment(machine, tmp_path, package=package))
    folder, pinned = write_pinned(tmp_path, manifest, result)

    assert re.fullmatch(r"\d{8}-\d{6}-0123456", result.version)
    assert pinned.kind is ManifestKind.VERSION and pinned.track is None
    assert pinned.source.git is not None and pinned.source.git.commit == COMMIT
    report = check_directory(folder)
    assert report.errors == () and report.warnings == (), (report.errors, report.warnings)


def test_the_registry_lists_exactly_the_packages_whose_download_address_has_no_version() -> None:
    """`unversioned` in `_registry.toml` equals the packages whose expected download address holds no form of the version.

    The registry tool marks those packages when it writes a version: an older build of them is not installable once the vendor
    replaces the file.
    """
    listed = set(tomllib.loads((REGISTRY_ROOT / "_registry.toml").read_text(encoding="utf-8"))["unversioned"])
    computed = set()
    for case in CASES:
        document = read_case(case)
        version, url = document["expected"]["version"], document["expected"]["download_url"]
        forms = {version, version.replace(".", ""), version.replace(".", "-"), version.replace(".", "_"), version.replace("-", "").replace(".", "")}
        if not any(form in url for form in forms):
            computed.add(document["tracker"])

    assert listed == computed
