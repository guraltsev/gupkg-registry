# gupkg-registry

Package definitions for [gupkg](https://github.com/guraltsev/gupkg) 1.0 (registry format 2).
`gupkg registry sync` clones this repository (or downloads its archive).

## Layout

```text
<name>/
  _check_updates/   pkg.toml (+ support files)   the tracker: how to find the newest version
  <version>/        pkg.toml, install.cmd, gupkg-tui.cmd   a pinned version: fully resolved, with sha256
_registry.toml      format = 2, name, description, unpinned, [fingerprints] "<name>/<version>" = "<sha256>"
```

- **Every version is kept.** A version is a small `pkg.toml`; deleting one is a manual maintainer
  action. The registry tool never deletes anything.
- **Every pinned version carries a `sha256`** (`sha256_from` says where it came from: a vendor
  checksum, or `"registry"` when the vendor publishes none and the registry tool computed it,
  which a maintainer reviews) **and a fingerprint** in `_registry.toml`: one SHA-256 over the
  version directory's files, so a copy of the directory (a distribution folder) can be verified
  without a download. The algorithm is documented in `gupkg/services/fingerprint.py` (sorted
  relative paths, file bytes hashed as they are, no timestamps, links refused).
- **Git stores every byte unchanged** (`.gitattributes` has `* -text`), so a checkout, a ZIP export
  and any `core.autocrlf` give the same fingerprints. Launchers are CRLF, everything else LF.
- `ignore_checksum` does not exist any more. No package is installed without a checksum under the
  default policy; versions whose vendor publishes none carry the registry's own hash.
- Packages use the built-in services (providers, unpack kinds, `[[prepare]]`, `[source.checksum]`).
  Hook files (`pkg.local`) remain only where no service can express the package; each says
  `Why no service: ...` in its docstring and the whole registry keeps at most 13. Today there are none.

## Tools

All need a checkout of the gupkg repository (found through `GUPKG_REPO`, a sibling `gupkg` folder,
or a `gupkg` folder inside this checkout).

| Script | What it does |
|---|---|
| `_scripts\validate.cmd` | The package checker (`gupkg pkg check`'s library) on every tracker and version, then the registry rules. What CI runs. |
| `_scripts\test.cmd` | The registry tests (`_tests`). Needs pytest. |
| `_scripts\registry-tool.cmd update [PACKAGE ...] [--sandbox DIR] [--auto-push]` | Runs the trackers and writes new `<name>/<version>/` directories with `sha256` and fingerprint. **Network required.** Commits nothing unless `--auto-push`. |
| `_scripts\registry-tool.cmd pin NAME/VERSION` | Gives an existing version that has no hash its first one. |

The tests and `_tools/pkg_check.py` validate through gupkg's public checker: `_tools/pkg_check.py`
calls `gupkg.pkgcheck.check_directory`, the library behind `gupkg pkg check`. When the unified CLI
(gupkg issue 029) ships, replace `check()` in that one file with a call of `gupkg pkg check
<directory> --json`; nothing else changes.

## First population (manual: needs the network)

Nobody could run the tool offline, so the registry holds trackers but (apart from one version) no
pinned versions yet. The maintainer runs, once:

```text
_scripts\registry-tool.cmd update --sandbox C:\temp\registry-sandbox
```

reviews the new directories (especially every version with `sha256_from = "registry"`, marked
`[REVIEW]` in the output), then commits and pushes. Packages that fail are reported and skipped;
fix their tracker and run `update <name>` again. The one existing legacy version `qbittorrent/5.2.3`
has no hash and is listed under `unpinned` in `_registry.toml`; run
`_scripts\registry-tool.cmd pin qbittorrent/5.2.3` to hash it (the tool then removes it from the list).

## Not yet verified (manual)

- Every package installing on a clean Windows runner under the strict CLI default.
- The portable mechanism of each package: see `PORTABLE-UNVERIFIED.md`.
- The vendor pages behind each tracker: the HTTP fixtures in the gupkg repository are synthetic
  (`recorded: null`) until `tools/record_http_fixtures.py` records them.
