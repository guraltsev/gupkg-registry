"""Validate registry directories with gupkg's own package checker (the stand-in for ``gupkg pkg check``).

This registry validates its packages with the same check as ``gupkg pkg check``: the public
library function ``gupkg.pkgcheck.check_directory``, called here and only here. The command
itself arrives with gupkg's unified CLI (issue 029); then replace ``check()`` below with a call
of ``gupkg pkg check <directory> --json`` and nothing else in this repository changes: the tests
and the CI job use only this script's command line and its JSON output.

Usage
-----
``python _tools/pkg_check.py --all [--json]`` checks every tracker and every pinned version.
``python _tools/pkg_check.py PATH [PATH ...]`` checks the named directories.
Exit status is 1 when any directory has an error or a warning.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _tools.gupkg_location import GUPKG_REPO, REGISTRY_ROOT  # noqa: E402

sys.path.insert(0, str(GUPKG_REPO / "src"))
sys.path.append(str(GUPKG_REPO / "src" / "gupkg" / "python" / "Lib" / "site-packages"))  # last: installed packages win

from gupkg.pkgcheck import check_directory  # noqa: E402  (the public library behind `gupkg pkg check`)


def check(directory: Path) -> dict[str, object]:
    """Check one directory and return ``{"path", "errors", "warnings"}`` (the whole swap point)."""
    report = check_directory(directory)
    return {"path": directory.relative_to(REGISTRY_ROOT).as_posix(), "errors": list(report.errors), "warnings": list(report.warnings)}


def every_directory() -> list[Path]:
    """Return each package's tracker and pinned version directories."""
    found = []
    for package in sorted(p for p in REGISTRY_ROOT.iterdir() if p.is_dir() and not p.name.startswith((".", "_"))):
        found.extend(sorted(c for c in package.iterdir() if c.is_dir() and (c / "pkg.toml").is_file()))
    return found


def main() -> int:
    """Check the directories and print the results; return the process status."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("paths", nargs="*", type=Path)
    parser.add_argument("--all", action="store_true", help="check every tracker and pinned version")
    parser.add_argument("--json", action="store_true", help="print the results as JSON")
    args = parser.parse_args()
    directories = every_directory() if args.all else [p.resolve() for p in args.paths]
    if not directories:
        parser.error("name a directory or use --all")
    results = [check(directory) for directory in directories]
    if args.json:
        print(json.dumps(results, indent=1))
    else:
        for result in results:
            for line in result["errors"]:
                print(f"{result['path']}: error: {line}")
            for line in result["warnings"]:
                print(f"{result['path']}: warning: {line}")
        print(f"{len(results)} directories checked")
    return 1 if any(r["errors"] or r["warnings"] for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
