"""Convert the registry to gupkg issue 035 ("portable is a kind of package, not a mode"). Idempotent.

For every ``<name>/<version>/pkg.toml`` and ``<name>/_check_updates/pkg.toml``:

* ``modes = ["system", "user", "portable"]``: the package becomes non-portable (``modes = ["system", "user"]``, no
  ``[portable]``) and a copy ``<name>-portable`` is made (``modes = ["portable"]``, ``[portable]`` kept, description
  ends with `` (portable)``).
* any ``[user]`` / ``[system]`` step table (also in a package that already says ``["system", "user"]``): its steps move
  into the plain ``[[prepare]]`` list, once and in order, and the tables go. The portable copy never gets them.
* ``modes = ["portable"]``: ``[portable]`` keeps only ``persist`` and ``markers``.

The files are edited as text so that every comment survives (a TOML writer drops comments); each result is parsed back
and checked. The registry's fingerprints are refreshed by deleting the launchers of every changed version directory and
running the registry tool's own launcher sync (``gupkg-registry launchers``), which writes them again and recomputes
those fingerprints. Nothing is downloaded and no ``download_url``, ``sha256`` or ``[track]`` is touched.

Usage: ``python _tools/convert_035.py``
"""

from __future__ import annotations

import json
import re
import shutil
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _tools.gupkg_location import GUPKG_REPO, REGISTRY_ROOT  # noqa: E402

sys.path.insert(0, str(GUPKG_REPO / "src"))
sys.path.append(str(GUPKG_REPO / "src" / "gupkg" / "python" / "Lib" / "site-packages"))  # last: installed packages win

from gupkg_registry.layout import read_registry_file, write_registry_file  # noqa: E402
from gupkg_registry.update import sync_launchers  # noqa: E402

TRI = ["system", "user", "portable"]
LAUNCHERS = ("install.cmd", "gupkg-tui.cmd", "check-updates.cmd")
UNVERIFIED_LINE = "# UNVERIFIED upstream portable mechanism"
HEADER = re.compile(r"^\[\[?[A-Za-z_][A-Za-z0-9_.\-]*\]\]?\s*$")

COPYQ_BASE = """\
# CopyQ chooses its storage by itself (src/platform/win/winplatform.cpp, portableFolder()): when the folder of copyq.exe is
# writable and holds no unins000.exe, it keeps its settings and logs beside the program, in config\\ and logs\\; otherwise it
# uses %APPDATA%\\copyq.
#   system:  the App folder is admin-only, so CopyQ uses %APPDATA%\\copyq for every user.
#   user:    a user root is writable, so CopyQ would go portable and keep its settings in the version's App folder, which every
#            update replaces. An empty unins000.exe (all CopyQ looks for) keeps it on %APPDATA%\\copyq; it is harmless in system
#            mode, so the step runs in both modes.
#   The portable variant is the package copyq-portable (no unins000.exe, config\\ persisted).""".splitlines()
COPYQ_PORTABLE = """\
# CopyQ chooses its storage by itself (src/platform/win/winplatform.cpp, portableFolder()): when the folder of copyq.exe is
# writable and holds no unins000.exe, it keeps its settings and logs beside the program, in config\\ and logs\\; otherwise it
# uses %APPDATA%\\copyq.
#   This package is the portable variant: it creates no unins000.exe, so CopyQ keeps config\\ in App, and config\\ is kept in
#   the package's data folder across updates (logs\\ starts empty in each version).
#   The non-portable variant is the package copyq (an empty unins000.exe keeps the settings on %APPDATA%\\copyq).
# UNVERIFIED upstream portable mechanism""".splitlines()


class Block:
    """One TOML table with the comment lines directly above it."""

    def __init__(self, header: str, comments: list[str], body: list[str]) -> None:
        self.header, self.comments, self.body = header, comments, body

    @property
    def name(self) -> str:
        return self.header.strip().strip("[]")

    def lines(self) -> list[str]:
        body = list(self.body)
        while body and not body[-1].strip():
            body.pop()
        return [*self.comments, self.header, *body]


def split(text: str) -> tuple[list[str], list[Block]]:
    """Split *text* into the lines before the first table and the tables (comments stay with the table below them)."""
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    preamble: list[str] = []
    blocks: list[Block] = []
    current: list[str] = preamble
    for line in lines:
        if HEADER.match(line):
            comments: list[str] = []
            while current and current[-1].startswith("#"):
                comments.insert(0, current.pop())
            blocks.append(Block(line, comments, []))
            current = blocks[-1].body
        else:
            current.append(line)
    while preamble and not preamble[-1].strip():
        preamble.pop()
    return preamble, blocks


def join(preamble: list[str], blocks: list[Block]) -> str:
    """Render the pieces back, one blank line between tables, LF, final newline."""
    parts = ["\n".join(preamble)] + ["\n".join(b.lines()) for b in blocks]
    return "\n\n".join(parts) + "\n"


def steps_of(block: Block) -> list[list[str]]:
    """Return the old-style steps of a ``[user]`` / ``[system]`` table."""
    data = tomllib.loads("\n".join([block.header, *block.body]))[block.name]
    if set(data) != {"prepare"}:
        raise SystemExit(f"unhandled keys in [{block.name}]: {sorted(data)}")
    return data["prepare"]


def row(step: list[str]) -> list[str]:
    """Return the ``[[prepare]]`` lines of one old-style step (``remove`` and ``create`` are the only verbs used)."""
    verb, *args = step
    if verb == "remove":
        return ["[[prepare]]", f"remove = [{', '.join(json.dumps(a) for a in args)}]"]
    if verb == "create" and len(args) == 1:
        return ["[[prepare]]", f'write = {{ path = {json.dumps(args[0])}, content = "" }}']
    raise SystemExit(f"unhandled step {step}")


def set_modes(preamble: list[str], modes: list[str]) -> list[str]:
    """Return *preamble* with its ``modes`` line replaced."""
    text = "modes = [" + ", ".join(json.dumps(m) for m in modes) + "]"
    return [text if line.startswith("modes = ") else line for line in preamble]


def convert_text(text: str, package: str, portable_copy: bool) -> str:
    """Convert one ``pkg.toml`` text. With *portable_copy* the text becomes the ``-portable`` variant."""
    preamble, blocks = split(text)
    tables = {b.name for b in blocks}
    if "nonportable" in tables:
        raise SystemExit("unhandled [nonportable] table")
    modes = tomllib.loads(text).get("modes", ["system", "user"])
    mode_blocks = [b for b in blocks if b.name in ("user", "system")]
    if portable_copy:
        blocks = [b for b in blocks if b.name not in ("user", "system")]
        preamble = set_modes(preamble, ["portable"])
        preamble = [re.sub(r'^(description = ".*)"$', r'\1 (portable)"', line) for line in preamble]
        if package == "copyq" and "CopyQ chooses" in text:
            for b in blocks:
                if b.name == "portable":
                    b.comments = list(COPYQ_PORTABLE)
        return join(preamble, blocks)
    if modes == TRI:
        preamble = set_modes(preamble, ["system", "user"])
        blocks = [b for b in blocks if b.name.split(".")[0] != "portable"]
    elif not mode_blocks:
        return text
    if mode_blocks:
        existing = [b for b in blocks if b.name == "prepare"]
        have = ["\n".join(b.lines()) for b in existing]
        new: list[Block] = []
        for old in mode_blocks:
            for step in steps_of(old):
                lines = row(step)
                if "\n".join(lines) not in have:
                    have.append("\n".join(lines))
                    new.append(Block(lines[0], [], lines[1:]))
        comments = [c for c in next((b.comments for b in mode_blocks if b.comments), []) if c != UNVERIFIED_LINE]
        if package == "copyq" and "CopyQ chooses" in text:
            comments = list(COPYQ_BASE)
        if new:
            new[0].comments = comments
        kept = [b for b in blocks if b.name not in ("user", "system")]
        index = kept.index(existing[-1]) + 1 if existing else blocks.index(mode_blocks[0])
        kept[index:index] = new
        blocks = kept
    return join(preamble, blocks)


def clean_portable_only(text: str) -> str:
    """For ``modes = ["portable"]``: ``[portable]`` keeps only ``persist`` and ``markers`` (fails on anything else)."""
    extra = set(tomllib.loads(text).get("portable", {})) - {"persist", "markers"}
    if extra:
        raise SystemExit(f"[portable] has keys to remove: {sorted(extra)}; the script does not rewrite them")
    return text


def version_dirs(package: Path) -> list[Path]:
    """Return the tracker and version directories of *package* that hold a ``pkg.toml``."""
    return sorted(d for d in package.iterdir() if d.is_dir() and (d / "pkg.toml").is_file())


def write_changed(path: Path, new: str, touched: list[Path]) -> None:
    """Write *new* to *path* when it differs (LF, UTF-8) and remember the directory."""
    if path.read_bytes() != new.encode("utf-8"):
        path.write_bytes(new.encode("utf-8"))
        touched.append(path.parent)


def main() -> int:
    """Convert the registry; print what was done."""
    root = REGISTRY_ROOT
    touched: list[Path] = []
    created: list[str] = []
    packages = sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith((".", "_")))
    for package in packages:
        dirs = version_dirs(package)
        texts = {d: (d / "pkg.toml").read_text(encoding="utf-8") for d in dirs}
        modes = {tuple(tomllib.loads(t).get("modes", ["system", "user"])) for t in texts.values()}
        if modes == {tuple(TRI)} or (len(modes) > 1 and tuple(TRI) in modes):
            if modes != {tuple(TRI)}:
                raise SystemExit(f"{package.name}: mixed modes {sorted(modes)}")
            twin = root / f"{package.name}-portable"
            if twin.exists():
                raise SystemExit(f"{twin.name} exists already")
            for d in dirs:
                target = twin / d.name
                shutil.copytree(d, target, ignore=shutil.ignore_patterns(*LAUNCHERS, "__pycache__"))
                (target / "pkg.toml").write_bytes(convert_text(texts[d], package.name, True).encode("utf-8"))
                touched.append(target)
            created.append(twin.name)
        for d in dirs:
            new = convert_text(texts[d], package.name, False) if tomllib.loads(texts[d]).get("modes") != ["portable"] else clean_portable_only(texts[d])
            write_changed(d / "pkg.toml", new, touched)
    for d in dict.fromkeys(touched):
        if d.name != "_check_updates":
            for name in LAUNCHERS:
                (d / name).unlink(missing_ok=True)
    registry = read_registry_file(root)
    for key in ("unversioned",):
        extra = [f"{n}-portable" for n in created if n in registry.get(key, [])]
        if extra:
            registry[key] = [*registry[key], *extra]
            write_registry_file(root, registry)
    for line in sync_launchers(root):
        print(line)
    print(f"{len(created)} packages created: {' '.join(created)}" if created else "no package created")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
