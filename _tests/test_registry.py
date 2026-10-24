"""Cover the registry as a whole: every package passes the format 2 checker, and the registry rules hold.

Behavior covered: each tracker and pinned version has no error and no warning from the package
checker (``gupkg pkg check``'s library, run through ``_tools/pkg_check.py``); the registry tool's
``validate`` finds no problem (fingerprints, hashes, launchers, hook notes); no manifest says
``ignore_checksum``; ``.gitattributes`` stores every byte unchanged; every portable declaration is
listed in ``PORTABLE-UNVERIFIED.md``; at most 13 hook files remain.
Real: this repository's packages and the two scripts, run as child processes. Out of scope:
downloading anything (the tracker fixtures run in the gupkg repository and in the CI job).
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from _tests.conftest import REGISTRY_ROOT, run_script

MANIFESTS = sorted(
    path for path in REGISTRY_ROOT.glob("*/*/pkg.toml") if not path.parts[-3].startswith(("_", "."))
)
DIRECTORIES = [path.parent.relative_to(REGISTRY_ROOT).as_posix() for path in MANIFESTS]


def test_the_registry_is_not_empty() -> None:
    """There are 79 packages, so a glob that silently finds nothing cannot make the checks below pass."""
    assert len({path.split("/")[0] for path in DIRECTORIES}) == 79


@pytest.mark.parametrize("directory", [pytest.param(path, id=path) for path in DIRECTORIES])
def test_the_directory_passes_the_package_checker_with_no_warning(
    pkg_check_results: dict[str, dict[str, list[str]]], directory: str
) -> None:
    """The tracker or pinned version has zero errors and zero warnings."""
    result = pkg_check_results[directory]
    assert result["errors"] == [] and result["warnings"] == []


def test_the_registry_tool_finds_no_problem() -> None:
    """``validate`` accepts the registry: hashes, fingerprints, launchers, modes, hook notes."""
    process = run_script("registry_tool.py", "validate")
    assert process.returncode == 0, process.stdout + process.stderr


def test_no_manifest_mentions_ignore_checksum() -> None:
    """The bypass is gone from every manifest and every script."""
    offenders = [
        path.relative_to(REGISTRY_ROOT).as_posix()
        for pattern in ("*/*/pkg.toml", "*/*/pkg.local/*")
        for path in REGISTRY_ROOT.glob(pattern)
        if "ignore_checksum" in path.read_text(encoding="utf-8", errors="replace")
    ]
    assert offenders == []


def test_no_manifest_value_contains_a_control_character() -> None:
    """Escaped-backslash mistakes such as ``"$App\\npbackup.exe"`` are caught before release."""

    def control(value: object, where: str = ""):
        if isinstance(value, str):
            if any(ord(char) < 32 for char in value):
                yield where, value
        elif isinstance(value, dict):
            for key, item in value.items():
                yield from control(item, f"{where}.{key}")
        elif isinstance(value, list):
            for index, item in enumerate(value):
                yield from control(item, f"{where}[{index}]")

    problems = [
        f"{path.parent.parent.name}/{path.parent.name}{where}: {text!r}"
        for path in MANIFESTS
        for where, text in control(tomllib.loads(path.read_text(encoding="utf-8")))
    ]
    assert problems == []


def test_git_stores_every_byte_unchanged() -> None:
    """Fingerprints hash exact bytes, so ``.gitattributes`` must turn text conversion off for every file."""
    lines = [line.strip() for line in (REGISTRY_ROOT / ".gitattributes").read_text(encoding="utf-8").splitlines()]
    assert "* -text" in lines


def test_every_portable_declaration_is_listed_as_unverified() -> None:
    """A package with ``[portable]`` or ``[nonportable]`` appears in ``PORTABLE-UNVERIFIED.md`` until someone verifies it."""
    listed = (REGISTRY_ROOT / "PORTABLE-UNVERIFIED.md").read_text(encoding="utf-8")
    declared = [
        path.parent.parent.name
        for path in MANIFESTS
        if path.parent.name == "_check_updates"
        and {"portable", "nonportable"} & set(tomllib.loads(path.read_text(encoding="utf-8")))
    ]
    assert declared
    assert [name for name in declared if f"`{name}`" not in listed] == []


def test_few_hook_files_remain() -> None:
    """The migration leaves at most 13 hook files; each is justified in its docstring (the tool checks the note)."""
    hooks = [p for p in REGISTRY_ROOT.glob("*/*/pkg.local/**/*.py")]
    assert len(hooks) <= 13
