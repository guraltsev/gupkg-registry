# gupkg-registry

Package definitions for [gupkg](https://github.com/guraltsev/gupkg): one folder per
package, each with a `pkg.bootstrap` (or `v<version>`) seed and a `gupkg-tui.cmd` that opens gupkg's text interface for that package (needs gupkg installed). `gupkg manager
registry sync` clones this repository (or downloads its archive).

## Checking changes

The consistency tests and tools need a checkout of the gupkg repository, found in
the folder that contains this one, in a sibling `gupkg` folder, or in `GUPKG_REPO`.

| Script | What it does |
|---|---|
| `_scripts\test.cmd` | Run the consistency tests (manifests, `gupkg-tui.cmd` launchers, per-package update hooks). |
| `_scripts\validate.cmd` | Validate the whole registry with gupkg's own loader. |
| `_scripts\sync-launchers.cmd [--check]` | Put `gupkg-tui.cmd` (gupkg's `src\package-tui.cmd`) in every package; removes the old `gupkg.cmd`. |
