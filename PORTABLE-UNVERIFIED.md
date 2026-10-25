# Portable declarations that nobody has verified

Every `[portable]` and `[nonportable]` table in this registry was written from the old hooks and
from knowledge of how each upstream application behaves. **None was tested against the real
application** (the migration was done offline). The schema has no `verified` key, so this file and
the comment `# UNVERIFIED upstream portable mechanism` above each table are the record. A test
(`_tests/test_registry.py`) fails when a package declares one of these tables and is not listed
here, so verifying a package means: test it, fix its table if needed, then delete its row.

How to verify a package: install it in portable mode (`gupkg install <name> --mode portable`), run
the application, change a setting, update or reinstall, and check that (1) the setting survived,
(2) nothing was written outside `<package>\data` and `App`, and (3) the files listed below are the
ones the application really writes.

| Package | Declared | Evidence | Confidence |
| --- | --- | --- | --- |
| `crystaldiskinfo` | persist `DiskInfo.ini` | upstream writes it beside the exe | medium-high |
| `crystaldiskmark` | persist `DiskMark.ini` (the 64-bit exe may use another name) | upstream writes it beside the exe | medium-high |
| `hwinfo` | persist `HWiNFO64.INI` (absent from the zip until first run) | upstream writes it beside the exe | medium |
| `keepassxc` | marker and persist `keepassxc.ini` | the zip ships no ini; upstream reads one beside the exe | medium-high |
| `keypirinha` | persist `portable`; nonportable removes `portable` | the old unpack hook deleted that folder | name high; persisting a folder by junction untested |
| `mogan` | nonportable removes `.portable` | the old unpack hook | high |
| `notepadplusplus` | marker `doLocalConf.xml`; persist config.xml, session.xml, shortcuts.xml, stylers.xml, contextMenu.xml, userDefineLangs, plugins, themes, backup | upstream's local-configuration marker | marker high; persisting `plugins` and `themes` freezes the bundled ones at first install |
| `obsstudio` | marker `portable_mode.txt`; persist `config` | upstream portable mode | medium-high |
| `rufus` | marker and persist `rufus.ini` | an ini beside the exe selects portable settings | medium-high |
| `sqlitebrowser` | marker and persist `DB4S-settings.ini` | recalled from DB Browser for SQLite's source | medium-low |
| `SumatraPDF-portable` | persist `SumatraPDF-settings.txt` | settings file beside the exe | medium-high |
| `systeminformer` | marker and persist `amd64/SystemInformer.exe.settings.xml`; nonportable removes `*/SystemInformer.exe.settings.xml` | the old `remove_settings.py` hook; upstream uses a settings file beside the exe | medium (the empty marker file is the least certain part) |
| `tixati` | marker `tixati_portable_mode.txt`; no persist | the old package shipped the marker | marker high; nobody knows what else Tixati writes beside the exe, so its settings are lost on update until someone lists the files |
| `vscode` | persist `data` | a `data` folder beside `Code.exe` makes it portable | upstream high; how gupkg persists a folder named `data` inside `data` untested |
| `winmerge` | marker and persist `WinMerge.ini` | an ini beside the exe | medium-low (the exact file name is not confirmed) |
| `winscp` | marker and persist `WinSCP.ini` | WinSCP uses an ini beside the exe when one exists | medium-high |

`sqlitebrowser` is portable-only (as in 0.17). `tixati` still declares only the marker: what else Tixati writes
beside the program is unknown (nothing was invented), so its settings do not survive an update until someone
runs it portable once and lists the new files in its `persist`.
