"""Cover the rules the packages' own files must follow, which the package checker does not judge: portable packages, six
packages that are written in a particular way on purpose, and the patterns of every tracker.

Rules covered:

- every package has a tracker;
- a package declares `modes = ["portable"]` exactly when it has a `[portable]` table, and a portable package lists no other mode;
- qbittorrent launches `$App\\qbittorrent.exe` in its tracker and in every pinned version, with no template leftovers or forward slash;
- zotero removes the installer debris from `App`; sqlitebrowser keeps its settings file when it is updated;
- msys2 is unpacked from its `.tar.xz` with the `tar` kind and keeps no file manifest; GIMP runs its vendor installer and says so;
- volta is told the `$App` folder that is on the PATH as its install folder, and its pnpm support is on, in its tracker and every pinned version;
- zotero, nano, qbittorrent, msys2 and gimp keep no hook (`pkg.local`);
- every pattern of every tracker passes the pattern guard, so a pattern that could run for ever is refused before any request.

Real: the registry's package files and gupkg's pattern guard. Out of scope: running the trackers (`test_trackers.py`) and checking
each package against the format (`test_registry.py`).
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any

import pytest

from gupkg.model.patterns import compile_pattern

from _tests.conftest import REGISTRY_ROOT
from _tests.support import PACKAGES, tracker_data

PATTERN_KEYS = {"match", "asset_pattern", "tag_pattern", "page_match"}
PORTABLE_ONLY = (
    "SumatraPDF-portable", "copyq-portable", "crystaldiskinfo-portable", "crystaldiskmark-portable", "hwinfo-portable",
    "keepassxc-portable", "keypirinha-portable", "notepadplusplus-portable", "obsstudio-portable", "rufus-portable",
    "serviwin-portable", "sqlitebrowser", "systeminformer-portable", "tixati", "vscode-portable", "winmerge-portable",
    "winscp-portable",
)
SPECIAL_PACKAGES = ["qbittorrent", "zotero", "msys2", "gimp", "nano"]


def test_every_package_has_a_tracker() -> None:
    """Each package folder holds a `_check_updates/pkg.toml`, so `check-updates` can find its newest version."""
    folders = sorted(p.name for p in REGISTRY_ROOT.iterdir() if p.is_dir() and not p.name.startswith(("_", ".")) and any(p.glob("*/pkg.toml")))

    assert folders == PACKAGES


def test_the_portable_only_packages_are_exactly_the_ones_named_here_and_each_says_so() -> None:
    """Only the packages named in `PORTABLE_ONLY` list `portable` in their modes or carry a `[portable]` table, and each lists no other mode.

    A package that is only offered as a portable copy (tixati, SumatraPDF-portable, sqlitebrowser, and the `-portable` twins of
    the ordinary packages) declares `modes = ["portable"]` and a `[portable]` table saying how it enters portable mode. Turning one
    into an ordinary package, or making another package portable-only, is an explicit edit of `PORTABLE_ONLY`.
    """
    claimed = sorted(name for name in PACKAGES if "portable" in tracker_data(name)["modes"])
    tabled = sorted(name for name in PACKAGES if "portable" in tracker_data(name))

    assert claimed == tabled == sorted(PORTABLE_ONLY)
    assert {name: tracker_data(name)["modes"] for name in PORTABLE_ONLY} == {name: ["portable"] for name in PORTABLE_ONLY}
    assert all(tracker_data(name)["portable"] for name in PORTABLE_ONLY)


def test_qbittorrent_has_no_template_leftovers_and_no_forward_slash() -> None:
    """The tracker and every pinned version launch `$App\\qbittorrent.exe`, and carry no generated-file boilerplate."""
    paths = sorted((REGISTRY_ROOT / "qbittorrent").glob("*/pkg.toml"))
    assert len(paths) >= 2

    for path in paths:
        text = path.read_text(encoding="utf-8")
        data = tomllib.loads(text)

        assert [row["target"] for row in data["shortcut"]] == ["$App\\qbittorrent.exe"], path
        assert "Auto-generated" not in text and "Example" not in text and "$App/" not in text, path


def test_zotero_removes_the_installer_debris_from_app() -> None:
    """The NSIS leftovers are removed by a prepare step."""
    data = tracker_data("zotero")

    removed = [item for step in data["prepare"] if "remove" in step for item in step["remove"]]
    assert {"$PLUGINSDIR", "uninstall.exe", "setup.exe"} <= set(removed)


def test_sqlitebrowser_declares_how_its_settings_survive_an_update() -> None:
    """The portable-only package keeps its settings file `DB4S-settings.ini` across updates (an unverified declaration, listed as such in PORTABLE-UNVERIFIED.md)."""
    data = tracker_data("sqlitebrowser")

    assert data["modes"] == ["portable"] and data["portable"]["persist"] == ["DB4S-settings.ini"]
    assert "`sqlitebrowser`" in (REGISTRY_ROOT / "PORTABLE-UNVERIFIED.md").read_text(encoding="utf-8")


def test_msys2_uses_the_tar_release_and_opts_out_of_the_file_manifest() -> None:
    """MSYS2 is unpacked from its `.tar.xz` with the `tar` kind, not by running the vendor self-extractor, and records no per-file manifest (it has about 14,000 files)."""
    data = tracker_data("msys2")

    assert data["source"]["kind"] == "tar" and data["source"]["strip"] == 1
    assert data["track"]["asset"].endswith(".tar.xz") and data["record_manifest"] is False
    assert "sfx" not in json.dumps(data["source"])


def test_gimp_runs_its_vendor_installer_and_the_package_says_so() -> None:
    """GIMP's official download is an Inno Setup installer that no bundled tool can unpack, so its tracker runs the vendor installer explicitly."""
    data = tracker_data("gimp")

    assert data["source"]["kind"] == "exe" and data["source"]["installer"]["run"]


@pytest.mark.parametrize("manifest", sorted((REGISTRY_ROOT / "volta").glob("*/pkg.toml")), ids=lambda path: path.parent.name)
def test_volta_is_told_the_install_folder_the_path_names(manifest: Path) -> None:
    """Volta drops its install folder from the PATH by exact text, and its own guess is `current`'s target, so `$App` is stated."""
    data = tomllib.loads(manifest.read_text(encoding="utf-8"))

    assert [entry["value"] for entry in data["path"]] == ["$App"]
    assert {entry["name"]: entry["value"] for entry in data["env"]} == {"VOLTA_INSTALL_DIR": "$App", "VOLTA_FEATURE_PNPM": "1"}


@pytest.mark.parametrize("package", [pytest.param(name, id=name) for name in SPECIAL_PACKAGES])
def test_a_package_the_services_can_express_keeps_no_hook(package: str) -> None:
    """The package is written with trackers and `[[prepare]]` steps only: no `pkg.local` folder."""
    assert not list((REGISTRY_ROOT / package).glob("*/pkg.local"))


def test_every_pattern_in_every_tracker_passes_the_pattern_guard() -> None:
    """All regular expressions of all trackers compile under gupkg's pattern guard (patterns with a `${...}` template are checked after expansion, when the tracker runs)."""
    checked = 0

    def walk(value: Any) -> None:
        nonlocal checked
        if isinstance(value, dict):
            for key, item in value.items():
                if key in PATTERN_KEYS and isinstance(item, str) and "${" not in item:
                    compile_pattern(item)
                    checked += 1
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    for name in PACKAGES:
        data = tracker_data(name)
        walk(data.get("track", {}))
        walk(data.get("source", {}).get("checksum", {}))

    assert checked >= 40
