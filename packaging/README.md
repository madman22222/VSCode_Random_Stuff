# Windows portable build and release

The end-user download is [ChessStudio-Windows.zip](https://github.com/madman22222/VSCode_Random_Stuff/releases/latest/download/ChessStudio-Windows.zip).
It targets Windows 10/11 x64 and needs no separate Python installation.
For setup and migration see the [user guide](../chess/README.md) and
[upgrade guide](../chess/UPGRADES_GUIDE.md).

## Build locally

Use a Windows x64 machine, Git, and Python 3.11 x64. From a clean checkout at the
repository root, preferably in a dedicated virtual environment:

```powershell
python -m pip install -r packaging/requirements-build.txt
python run_tests.py
python packaging/build_windows.py
python packaging/smoke_windows.py --zip dist/ChessStudio-Windows.zip --report portable-smoke-report.json
```

Build dependencies and dependency source downloads require a connection.
PyInstaller cannot build this Windows app from Linux. The build script rejects
unsupported hosts. `--output` selects the output directory and `--version`
sets the recorded revision; default revision is `git rev-parse HEAD`. Build a
clean checkout so recorded revision and included source describe the same files.

## Outputs

| Output | Purpose |
| --- | --- |
| `dist/ChessStudio/` | Unpacked app folder |
| `dist/ChessStudio-Windows.zip` | Distributable archive with a single ChessStudio root |
| `dist/ChessStudio-Windows.zip.sha256` | Archive checksum |
| `dist/ChessStudio-Windows.build-info.json` | Revision, runtime/package versions, size, checksum |

The archive contains `ChessStudio.exe`, `ChessStudio-CLI.exe`, shared `_internal`
runtime/assets, writable `data/`, `README.txt`, `BUILD_INFO.json`, `LICENSES/`,
and `SOURCE/`. The latter folders retain dependency notices and source archives;
they are not installation steps. Stockfish is optional and is not bundled.
`ChessStudio.spec` defines both entry points and resource/hidden-import inclusion.

## Test the actual package

The smoke script extracts the ZIP to a new path containing spaces, launches from
an unrelated directory, removes Python from the child's PATH, and clears runtime
and data overrides. It checks frozen runtime paths and assets, drives isolated
GUI diagnostics, and trains through the console companion. A successful source
test run alone does not replace this check. Inspect the JSON report and process
exit status; retain reports when diagnosing failures.

To verify a downloaded archive in PowerShell:

```powershell
Get-FileHash .\ChessStudio-Windows.zip -Algorithm SHA256
Get-Content .\ChessStudio-Windows.zip.sha256
```

Compare the hash strings; filename formatting and hex letter case may differ.

## Automated releases

`.github/workflows/windows-portable.yml` runs for relevant `chess/`, `packaging/`,
and workflow changes on pull requests and pushes to main, and supports manual
workflow dispatch. A Windows runner installs build dependencies, runs source and
desktop regressions, builds, tests the extracted bundle, and uploads artifacts.
Pull requests do not publish public releases.

On main, a successful build feeds a separate publish job. It creates a latest
GitHub Release tagged `windows-RUNNUMBER-SHORTSHA`, targeting the exact revision,
with ZIP/checksum/build metadata and `release-notes.md`. Failure blocks publication.
The diagnostic artifact is uploaded when available even on failure. The stable
latest-download link in the READMEs follows new releases automatically.

Update `PORTABLE_README.txt` for instructions inside future ZIPs and
`release-notes.md` for future release descriptions. Already published archives
remain tied to their build revision; repository edits do not modify old ZIPs.

## Dependency review and other platforms

`constraints-build.txt` records the reviewed package set used for portable builds;
Dependabot proposes updates for review. The existing source and extracted-bundle
checks still gate publication. Update constraints and retained notices together.
See [portability/signing plan](PORTABILITY_PLAN.md) for work that still needs native
hosts and owner-provided signing accounts. No macOS/Linux portable release or
signed Windows build is currently claimed.

The workflow now builds `ChessStudio-VSCode.zip` and its SHA-256 alongside the
Windows ZIP. The source edition includes the workspace/debug/test configuration
and excludes runtime profiles. Both are built at the same commit and smoke-tested
after extraction before publication. `build_source.py` supplies the file selection
for both the source download and embedded corresponding-source archive.

```powershell
python packaging/build_source.py
python packaging/smoke_source.py --zip dist/ChessStudio-VSCode.zip --revision (git rev-parse HEAD)
```

Use a clean committed checkout for release builds. `worktree_dirty` records local
changes; untracked new modules are not release sources. Setup uses reviewed runtime
constraints; Python/VS Code are required only for the developer edition.

Pillow 13 requires Python 3.11+. Conditional constraints retain Pillow 12.3 on
Python 3.10 while the Python 3.11 Windows build uses Pillow 13; setuptools is
pinned to 84.2.1. Source CI installs these same constraints. Assets include both
guided-course and evaluation JSON resources; extracted source/frozen diagnostics
exercise their loading, automatic replies, lesson progress, evaluation ledger,
and the training recovery journal. Physical monitor scaling and screen-reader
behavior require separate hands-on checks.

Coaching/adaptive update: both editions share nine lessons/21 exercises, three
review moments linked to practice, local spaced review scheduling and comparable
protocol-2 evaluation trends. Existing solved progress is retained. Preserve
`chess_config.json` with the complete data folder to keep the new practice schedule.
Physical Windows scaling, screen-reader and owner-profile upgrade checks remain
unverified; use the manual checklist and retain a backup.
