"""Give every package seed of the registry the ``gupkg-tui.cmd`` launcher.

The launcher is ``src/package-tui.cmd`` of the gupkg repository. Placed in a package
as ``gupkg-tui.cmd`` it opens gupkg's text interface for that package, using a gupkg
installed beside it or on ``PATH``, so installing needs no command line. Run without
options to copy it into each seed and delete the obsolete ``gupkg.cmd``; ``--check``
only reports seeds that are missing the launcher, have a different copy, or still
have the old file, and exits with status 1.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _tools.gupkg_location import GUPKG_REPO, REGISTRY_ROOT  # noqa: E402

ROOT = REGISTRY_ROOT
LAUNCHER = GUPKG_REPO / "src" / "package-tui.cmd"
NAME = "gupkg-tui.cmd"
OBSOLETE = "gupkg.cmd"


def seed_directories(registry: Path) -> list[Path]:
    """Return each package's version-seed directory (``pkg.bootstrap`` or ``v<version>``)."""
    seeds = []
    for selector in sorted(path for path in registry.iterdir() if path.is_dir() and not path.name.startswith((".", "_"))):
        seeds.extend(
            sorted(child for child in selector.iterdir() if child.is_dir() and (child / "pkg.toml").is_file())
        )
    return seeds


def main() -> int:
    """Copy or verify the launcher in every seed; return the process status."""
    parser = argparse.ArgumentParser()
    parser.add_argument("registry", nargs="?", type=Path, default=ROOT)
    parser.add_argument("--check", action="store_true", help="report differences instead of fixing them")
    args = parser.parse_args()

    # Compare ignoring line endings (a Windows checkout may convert them).
    expected = LAUNCHER.read_bytes().replace(b"\r\n", b"\n")
    problems = []
    for seed in seed_directories(args.registry):
        target = seed / NAME
        if not target.is_file() or target.read_bytes().replace(b"\r\n", b"\n") != expected:
            problems.append(f"{'missing or different' if args.check else 'updated'}: {target.relative_to(ROOT)}")
            if not args.check:
                shutil.copyfile(LAUNCHER, target)
        old = seed / OBSOLETE
        if old.is_file():
            problems.append(f"{'obsolete' if args.check else 'removed'}: {old.relative_to(ROOT)}")
            if not args.check:
                old.unlink()
    for line in problems:
        print(line)
    return 1 if (problems and args.check) else 0


if __name__ == "__main__":
    sys.exit(main())
