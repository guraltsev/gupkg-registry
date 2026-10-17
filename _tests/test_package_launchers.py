"""Cover the text-interface launcher shipped inside every registry package.

Behavior covered: each package in the registry carries ``gupkg-tui.cmd``, identical
to gupkg's ``src/package-tui.cmd`` (ignoring line endings), has no leftover
``gupkg.cmd``, and the registry validates with gupkg's own loader.
Real: this repository's packages and the registry validator. Out of scope: what the
launcher does when run (covered in the gupkg repository).
"""

from __future__ import annotations

from gupkg.registry import validate_registry_tree

from _tests.registry_root import GUPKG_REPO, REGISTRY_ROOT


def _seeds():
    """Return every package seed folder of the registry."""
    return sorted(path.parent for path in REGISTRY_ROOT.glob("*/*/pkg.toml") if not path.parts[-3].startswith(("_", ".")))


def test_every_registry_package_ships_the_tui_launcher() -> None:
    """Each package seed has a gupkg-tui.cmd identical to gupkg's package-tui.cmd."""
    expected = (GUPKG_REPO / "src" / "package-tui.cmd").read_bytes().replace(b"\r\n", b"\n")
    seeds = _seeds()

    assert seeds
    wrong = [
        f"{seed.parent.name}/{seed.name}"
        for seed in seeds
        if not (seed / "gupkg-tui.cmd").is_file()
        or (seed / "gupkg-tui.cmd").read_bytes().replace(b"\r\n", b"\n") != expected
    ]
    assert wrong == []


def test_no_package_keeps_the_obsolete_gupkg_launcher() -> None:
    """The old per-package gupkg.cmd is gone: gupkg is either installed or comes with a local install."""
    assert [seed.parent.name for seed in _seeds() if (seed / "gupkg.cmd").exists()] == []


def test_checked_in_registry_validates() -> None:
    """The registry passes validation, launchers included."""
    assert validate_registry_tree(REGISTRY_ROOT)
