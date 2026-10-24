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

## Publishing with `--auto-push`

`registry-tool update ... --auto-push` commits only the paths the run wrote (`git commit -- <paths>`, so
anything you already staged stays out) and pushes the current branch's upstream; `--remote NAME` and
`--branch NAME` choose another target (`git push NAME HEAD:BRANCH`). It never forces and never skips hooks.
**It refuses to publish a hash the tool computed itself** (`sha256_from = "registry"`, shown as `[REVIEW]`:
trust on first use) unless `--allow-computed` is also given. A commit-message note is not a review: review the
versions, then commit by hand, or accept the risk for a scheduled job with the flag.

## Unversioned download addresses

For these packages the vendor serves every release at one address, so a pinned version verifies only until the
vendor replaces the file; afterwards its `sha256` fails for ever and that version cannot be installed. The
registry keeps the directory anyway (deletion is a maintainer action) and lists the packages under
`unversioned` in `_registry.toml`; the tool prints `[UNVERSIONED]` for them. To keep an old build installable,
host the file yourself and change that version's `download_url` and `sha256` by hand.

`autoruns`, `dontsleep`, `ffmpeg`, `processexplorer`, `shutter-encoder`, `xnviewmp`.

## Known differences from the 0.17 hooks

Where the services cannot express exactly what a hook did, or a fix changed behaviour on purpose:

- **backrest:** the shortcut icon is the program itself; the 0.17 `Icons\backrest.ico` never existed in the registry.
- **hwinfo:** a Start Menu shortcut is added (0.17 had none, so the package could not be started).
- **graphviz, testdisk:** shorter descriptions. testdisk no longer picks a `-WIP` build.
- **emacs:** the digest comes from `emacs-<version>-sha256sums.txt` when GNU publishes it (`optional = true`);
  the older `sha256sum.txt` spelling is not followed, so those builds get the registry's own hash for review.
- **inkscape:** the `.sha256` link is optional (`optional = true`): a release without it is still found and the
  hash is computed by the registry tool.
- **shutter-encoder:** the home page links several systems; `select = "each"` tries the links in page order (at most
  20) and keeps the first whose answer names `Shutter Encoder <version> Windows 64bits.zip`, like the 0.17 loop.
- **7zip:** the version comes from the x64 announcement (tolerating tags between "Windows" and "x64"); the download
  address is built from it (`7z<dotless version>-x64.exe`), which is the file the 0.17 hook found by link.
- **pidgin:** no `probe` is needed: the index walk backtracks to an older folder when the newest has no offline
  installer (the fixture has a newest folder with a source archive only).
- **winscp:** the browser User-Agent and Accept headers are sent on both page fetches, as before.
- **keypirinha, mogan, systeminformer:** the 0.17 hooks always deleted the portable marker or settings file; now
  `[nonportable] remove` does it and the engine (gupkg issue 028) applies it outside portable mode.
- **crystaldiskinfo, crystaldiskmark:** the redirect check no longer sends a browser User-Agent.
- **msys2:** `config.default/configure_nsswitch.*` is kept as a support file; nothing runs it (no service edits a file
  in place). **GIMP:** the engine does not run `[source.installer]` yet.
- **latex-toolkit, overleaf-sync:** still `git@github.com:` SSH addresses, as in 0.17 (they may be private). They are
  pinned by commit, not by `sha256`. Switch them to `https://` if the repositories are public.
- **tixati:** only the marker file is declared; what else Tixati writes beside the program is not known, so its
  settings are lost on update until someone lists the files. **sqlitebrowser:** `DB4S-settings.ini` is recalled
  from the source, untested.

## CI

`validate.yml` runs on `windows-latest` with a read-only token and no secret, for pushes to `main`, pull requests and
by hand (`gupkg_ref` chooses the gupkg branch, default `main`). The two actions are pinned by full version tag
(`actions/checkout@v4.2.2`, `actions/setup-python@v5.6.0`). Replace each by the commit SHA of that tag before relying
on the workflow for more than checks (look the SHAs up on GitHub; they could not be verified offline).

## Not yet verified (manual)

- Every package installing on a clean Windows runner under the strict CLI default.
- The portable mechanism of each package: see `PORTABLE-UNVERIFIED.md`.
- The vendor pages behind each tracker: the HTTP fixtures in the gupkg repository are synthetic
  (`recorded: null`) until `tools/record_http_fixtures.py` records them.
