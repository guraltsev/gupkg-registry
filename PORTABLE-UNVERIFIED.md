# Portable declarations that nobody has verified

Every `[portable]` table in this registry (each belongs to a `<name>-portable` package, or to a portable-only one) was written from the old hooks and
from knowledge of how each upstream application behaves. **None was tested against the real
application** (the migration was done offline). The schema has no `verified` key, so this file and
the comment `# UNVERIFIED upstream portable mechanism` above each table are the record. A test
(`_tests/test_registry.py`) fails when a package declares one of these tables and is not listed
here, so verifying a package means: test it, fix its table if needed, then delete its row.

How to verify a package: install it (`gupkg install <name>-portable`, user mode), run
the application, change a setting, update or reinstall, and check that (1) the setting survived,
(2) nothing was written outside `<package>\data` and `App`, and (3) the files listed below are the
ones the application really writes.

| Package | Declared | Evidence | Confidence |
| --- | --- | --- | --- |
| `copyq-portable` | persist `config`; no `unins000.exe` step, so CopyQ selects its portable storage | upstream `src/platform/win/winplatform.cpp` `portableFolder()`: portable when the folder of `copyq.exe` is writable and holds no `unins000.exe`; settings, items and state in `<App>\config` | high for the selection rule; persist of `config` through a junction untested |
| `crystaldiskinfo-portable` | persist `DiskInfo.ini` | upstream writes it beside the exe | medium-high |
| `crystaldiskmark-portable` | persist `DiskMark.ini` (the 64-bit exe may use another name) | upstream writes it beside the exe | medium-high |
| `hwinfo-portable` | persist `HWiNFO64.INI` (absent from the zip until first run) | upstream writes it beside the exe | medium |
| `keepassxc-portable` | marker and persist `keepassxc.ini` | the zip ships no ini; upstream reads one beside the exe | medium-high |
| `keypirinha-portable` | persist `portable` | the release ships that folder; the old unpack hook deleted it outside portable mode | name high; persisting a folder by junction untested |
| `notepadplusplus-portable` | marker `doLocalConf.xml`; persist config.xml, session.xml, shortcuts.xml, stylers.xml, contextMenu.xml, userDefineLangs, plugins, themes, backup | upstream's local-configuration marker | marker high; persisting `plugins` and `themes` freezes the bundled ones at first install |
| `obsstudio-portable` | marker `portable_mode.txt`; persist `config` | upstream portable mode | medium-high |
| `rufus-portable` | marker and persist `rufus.ini` | an ini beside the exe selects portable settings | medium-high |
| `serviwin-portable` | persist `serviwin.cfg` | NirSoft tools keep their settings in a `.cfg` beside the program (the tracker's own comment) | medium |
| `sqlitebrowser` | marker and persist `DB4S-settings.ini` | recalled from DB Browser for SQLite's source | medium-low |
| `SumatraPDF-portable` | persist `SumatraPDF-settings.txt` | settings file beside the exe | medium-high |
| `systeminformer-portable` | marker and persist `amd64/SystemInformer.exe.settings.xml` | upstream uses a settings file beside the exe | medium (the empty marker file is the least certain part) |
| `tixati` | marker `tixati_portable_mode.txt`; no persist | the old package shipped the marker | marker high; nobody knows what else Tixati writes beside the exe, so its settings are lost on update until someone lists the files |
| `vscode-portable` | persist `data` | a `data` folder beside `Code.exe` makes it portable | upstream high; how gupkg persists a folder named `data` inside `data` untested |
| `winmerge-portable` | marker and persist `WinMerge.ini` | an ini beside the exe | medium-low (the exact file name is not confirmed) |
| `winscp-portable` | marker and persist `WinSCP.ini` | WinSCP uses an ini beside the exe when one exists | medium-high |

`sqlitebrowser` is portable-only (as in 0.17). `tixati` still declares only the marker: what else Tixati writes
beside the program is unknown (nothing was invented), so its settings do not survive an update until someone
runs it portable once and lists the new files in its `persist`.
