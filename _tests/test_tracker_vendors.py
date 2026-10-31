"""Cover what the trackers of six vendors rely on in their sites: the page layouts, optional digests and fall-backs that their patterns encode.

``test_trackers.py`` runs every tracker once on one recorded answer. These vendors need more, because their pages vary or
their digests are optional, and a pattern that is right for today's page can be wrong for the next one.

Rules covered:

- shutter-encoder finds the Windows 64-bit file whatever place its link has on the home page, skips links that fail or name another
  system or an older 32-bit build, does not fetch the links after the one it found, accepts a link that is plain text, and fails
  (naming the number of candidates it tried) when no link names the Windows build;
- inkscape finds its version when the digest link is missing, dead or empty (the registry tool then computes the hash), uses the
  digest when there is one, takes a digest only as a whole 64-digit token, and still needs its download link;
- emacs takes the digest from GNU's sums file when it lists the archive, and otherwise goes on without one;
- pidgin falls back to an older folder when the newest has no offline installer;
- 7-Zip reads the x64 announcement whatever order x86, ARM64 and x64 appear in and refuses a page that has none;
- winscp sends its browser User-Agent and Accept header on both page fetches.

Real: the registry's trackers, gupkg's services and regex worker process. Replaced: the network (``FakeSystem`` serves invented pages
and the recorded cases). Out of scope: the live vendors, and how the providers work (gupkg's own tests).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gupkg.model.manifest import render_pinned
from gupkg.services.track import TrackError, run_tracker
from gupkg.system.fake import FakeHttp, FakeSystem

from _tests.support import environment, serve, tracker_manifest


def discover(system: FakeSystem, tmp_path: Path, package: str):
    """Run the live tracker of *package*; return ``(result, pinned manifest)``."""
    manifest = tracker_manifest(package)
    result = run_tracker(manifest, environment(system, tmp_path, package=package))
    return result, render_pinned(manifest, result)


def requests(system: FakeSystem, method: str | None = None) -> list[str]:
    """Return the addresses requested so far (optionally only those of one method)."""
    return [r.url for r in system.request_log if method is None or r.method == method]


# -- shutter-encoder: try each link --------------------------------------------------------------------------

SHUTTER = "https://www.shutterencoder.com/sdc_download/{}/?key={}"
LINKS = {
    "windows": (1234, "abcDEF123", 'attachment; filename="Shutter Encoder 18.4 Windows 64bits.zip"'),
    "mac": (9999, "zzzMAC999", 'attachment; filename="Shutter Encoder 18.4 Mac.dmg"'),
    "linux": (7777, "ccLINUX777", 'attachment; filename="Shutter Encoder 18.4 Linux 64bits.tar.gz"'),
    "old": (6666, "ddOLD666", 'attachment; filename="Shutter Encoder 17.0 Windows 32bits.zip"'),
    "gone": (5555, "bbbGONE555", None),
}


def shutter_system(system: FakeSystem, order: tuple[str, ...]) -> FakeSystem:
    """Make *system* serve a home page that links the systems in *order*; each link answers with its own file name (or 404)."""
    body = " ".join(f'<a href="{SHUTTER.format(LINKS[n][0], LINKS[n][1])}">{n}</a>' for n in order)
    system.urls["https://www.shutterencoder.com/"] = FakeHttp(body)
    for name in order:
        number, key, disposition = LINKS[name]
        system.urls[SHUTTER.format(number, key)] = FakeHttp("", 200, {"Content-Disposition": disposition}) if disposition else FakeHttp("", 404)
    return system


@pytest.mark.parametrize(
    "order",
    [
        pytest.param(("windows", "mac", "linux"), id="windows-first-and-the-links-after-it-are-not-fetched"),
        pytest.param(("mac", "linux", "windows"), id="windows-after-other-systems"),
        pytest.param(("gone", "mac", "windows", "linux"), id="windows-after-a-dead-link"),
        pytest.param(("old", "windows"), id="windows-after-an-older-32-bit-build"),
    ],
)
def test_shutter_encoder_finds_the_windows_build_wherever_the_page_links_it(system: FakeSystem, tmp_path: Path, order: tuple[str, ...]) -> None:
    """The Windows 64-bit link is chosen from any position, links before it that fail or name another system or build are skipped, and none after it is fetched."""
    shutter_system(system, order)

    result, pinned = discover(system, tmp_path, "shutter-encoder")

    assert result.version == "18.4"
    assert pinned.source.download_url == SHUTTER.format(1234, "abcDEF123")
    heads = requests(system, "HEAD")
    assert len(heads) == order.index("windows") + 1 and heads[-1] == SHUTTER.format(1234, "abcDEF123")


def test_shutter_encoder_also_finds_a_link_that_is_plain_text(system: FakeSystem, tmp_path: Path) -> None:
    """The tracker does not need an `href=` around the address: a bare URL in the page counts."""
    shutter_system(system, ("mac", "windows"))
    system.urls["https://www.shutterencoder.com/"] = FakeHttp(
        f"Mac {SHUTTER.format(9999, 'zzzMAC999')} and Windows {SHUTTER.format(1234, 'abcDEF123')} (also in an href)"
    )

    result, pinned = discover(system, tmp_path, "shutter-encoder")

    assert pinned.source.download_url == SHUTTER.format(1234, "abcDEF123") and result.version == "18.4"


def test_shutter_encoder_fails_when_no_link_names_the_windows_build(system: FakeSystem, tmp_path: Path) -> None:
    """With only other systems linked the check fails and says that every candidate was tried."""
    shutter_system(system, ("mac", "linux", "gone", "old"))

    with pytest.raises(TrackError, match=r"None of the 4 candidates of step 1"):
        discover(system, tmp_path, "shutter-encoder")

    assert len(requests(system, "HEAD")) == 4


# -- inkscape: the digest is optional --------------------------------------------------------------------------

DIGEST_PAGE = "https://inkscape.org/en/release/inkscape-1.4/windows/64-bit/compressed-7z/dl/"
DIGEST_FILE = "https://media.inkscape.org/dl/resources/file/inkscape-1.4_2024-10-11_86a8ad7-x64.7z.sha256"
ARCHIVE_LINK = '<a href="/gallery/item/53697/inkscape-1.4_2024-10-11_86a8ad7-x64.7z">Download</a>'


def inkscape_system(system: FakeSystem, *, page: str | None = None, digest: FakeHttp | None = None) -> FakeSystem:
    """Make *system* serve the inkscape case, with the download page and the digest file optionally replaced."""
    serve(system, "chain_inkscape")
    if page is not None:
        system.urls[DIGEST_PAGE] = FakeHttp(page)
    if digest is not None:
        system.urls[DIGEST_FILE] = digest
    return system


def test_inkscape_uses_the_published_digest_when_there_is_one(system: FakeSystem, tmp_path: Path) -> None:
    """With the digest link and file, the checksum is the vendor's."""
    _result, pinned = discover(inkscape_system(system), tmp_path, "inkscape")

    assert pinned.source.sha256 == "f9593190b7ed8fef57675e3a2d29f4d490612544bbc31de02ce784e6817b4c0c"
    assert pinned.source.sha256_from == "vendor-sums"


@pytest.mark.parametrize(
    ("page", "digest"),
    [
        pytest.param(ARCHIVE_LINK, None, id="no-digest-link"),
        pytest.param(None, FakeHttp("", 404), id="dead-digest-file"),
        pytest.param(None, FakeHttp("sorry, not available"), id="digest-file-without-a-digest"),
    ],
)
def test_inkscape_is_still_found_without_a_usable_digest(system: FakeSystem, tmp_path: Path, page: str | None, digest: FakeHttp | None) -> None:
    """A missing, dead or empty digest costs only the checksum: the version and the download are found, and no hash is invented."""
    result, pinned = discover(inkscape_system(system, page=page, digest=digest), tmp_path, "inkscape")

    assert result.version == "1.4"
    assert pinned.source.download_url == "https://inkscape.org/gallery/item/53697/inkscape-1.4_2024-10-11_86a8ad7-x64.7z"
    assert pinned.source.sha256 is None and pinned.source.sha256_from is None


def test_inkscape_takes_a_digest_only_as_a_whole_64_digit_token(system: FakeSystem, tmp_path: Path) -> None:
    """A run of 65 or more hexadecimal digits is no digest (no slice of it is taken); a real digest after other text still is one."""
    _result, pinned = discover(inkscape_system(system, digest=FakeHttp("a" * 70 + "\n")), tmp_path, "inkscape")
    assert pinned.source.sha256 is None

    _result, pinned = discover(inkscape_system(system, digest=FakeHttp("sha256:" + "b" * 64 + " (inkscape)\n")), tmp_path, "inkscape")
    assert pinned.source.sha256 == "b" * 64


def test_inkscape_still_needs_its_download_link(system: FakeSystem, tmp_path: Path) -> None:
    """Only the digest steps are optional: a page without the archive link fails the check."""
    with pytest.raises(TrackError, match="matched nothing"):
        discover(inkscape_system(system, page="<p>nothing here</p>"), tmp_path, "inkscape")


# -- emacs: the sums file when GNU publishes one -----------------------------------------------------------------

SUMS = "https://ftp.gnu.org/gnu/emacs/windows/emacs-30/emacs-30.2-sha256sums.txt"


def test_emacs_takes_the_digest_from_gnus_sums_file(system: FakeSystem, tmp_path: Path) -> None:
    """The listed archive's digest is the checksum, from the vendor's sums file."""
    _result, pinned = discover(serve(system, "index_emacs"), tmp_path, "emacs")

    assert pinned.source.sha256 == "5e1b3c8d9a7f4e2b6c0d1a8f3e7b9c4d2a6f0e8b1c3d5a7f9e2b4c6d8a0f1e3b"
    assert pinned.source.sha256_from == "vendor-sums"


@pytest.mark.parametrize(
    "sums",
    [pytest.param(FakeHttp("", 404), id="no-sums-file"), pytest.param(FakeHttp(f"{'a' * 64}  emacs-30.2-no-deps.zip\n"), id="archive-not-listed")],
)
def test_emacs_goes_on_without_a_digest_when_gnu_publishes_none(system: FakeSystem, tmp_path: Path, sums: FakeHttp) -> None:
    """A missing sums file or an unlisted archive leaves the version found and the checksum for the registry tool to compute."""
    serve(system, "index_emacs")
    system.urls[SUMS] = sums

    result, pinned = discover(system, tmp_path, "emacs")

    assert result.version == "30.2" and pinned.source.sha256 is None


# -- pidgin: older folders ----------------------------------------------------------------------------------------


def test_pidgin_falls_back_to_the_newest_folder_that_has_the_offline_installer(system: FakeSystem, tmp_path: Path) -> None:
    """2.14.14 has only a source archive, so the walk looks into it and then settles on 2.14.13."""
    serve(system, "index_pidgin")

    result, pinned = discover(system, tmp_path, "pidgin")

    assert result.version == "2.14.13"
    assert pinned.source.download_url.endswith("/2.14.13/pidgin-2.14.13-offline.exe/download")
    asked = requests(system)
    assert any(url.endswith("/Pidgin/2.14.14/") for url in asked) and any(url.endswith("/Pidgin/2.14.13/") for url in asked)


# -- 7-Zip: the x64 announcement ---------------------------------------------------------------------------------

ANNOUNCEMENTS = {
    "x86": "<B>Download 7-Zip 24.09 (2024-11-29) for Windows x86</B>",
    "arm64": "<B>Download 7-Zip 24.08 (2024-08-11) for Windows ARM64</B>",
    "x64": "<B>Download 7-Zip 25.01 (2025-08-03) for Windows x64</B>",
    "x64-tags": "<B>Download 7-Zip 25.01 (2025-08-03) for Windows</B> <B>x64</B>",
    "x64-nbsp": "<B>Download 7-Zip 25.01 (2025-08-03) for Windows&nbsp;x64:</B>",
}


@pytest.mark.parametrize(
    "order",
    [
        pytest.param(("x64", "arm64", "x86"), id="x64-first"),
        pytest.param(("arm64", "x86", "x64"), id="x64-last"),
        pytest.param(("x86", "x64-tags", "arm64"), id="x64-split-by-tags"),
        pytest.param(("arm64", "x64-nbsp", "x86"), id="x64-after-a-non-breaking-space"),
    ],
)
def test_7zip_reads_the_x64_announcement_in_whatever_order_the_builds_are_listed(system: FakeSystem, tmp_path: Path, order: tuple[str, ...]) -> None:
    """The version of the x64 announcement wins over the x86 and ARM64 ones, and the download is the x64 installer."""
    system.urls["https://www.7-zip.org/"] = FakeHttp("<html><body>" + "<P>" + "</P><P>".join(ANNOUNCEMENTS[n] for n in order) + "</P></body></html>")

    result, pinned = discover(system, tmp_path, "7zip")

    assert result.version == "25.01"
    assert pinned.source.download_url == "https://www.7-zip.org/a/7z2501-x64.exe"


def test_7zip_refuses_a_page_with_no_x64_announcement(system: FakeSystem, tmp_path: Path) -> None:
    """A page that announces only x86 and ARM64 builds is an error, never a version taken from them."""
    system.urls["https://www.7-zip.org/"] = FakeHttp(f"<P>{ANNOUNCEMENTS['x86']}</P><P>{ANNOUNCEMENTS['arm64']}</P>")

    with pytest.raises(TrackError, match="matched nothing"):
        discover(system, tmp_path, "7zip")


# -- winscp: browser headers on both fetches -----------------------------------------------------------------------


def test_winscp_sends_its_browser_headers_on_both_page_fetches(system: FakeSystem, tmp_path: Path) -> None:
    """The downloads page and the file's own page are both requested with the browser User-Agent and Accept header of the tracker."""
    serve(system, "chain_winscp")

    discover(system, tmp_path, "winscp")

    pages = [r for r in system.request_log if r.url.startswith("https://winscp.net/")]
    assert len(pages) == 2
    for request in pages:
        headers = {k.lower(): v for k, v in request.headers.items()}
        assert "gupkg-update-check" in headers["user-agent"] and headers["accept"].startswith("text/html")
