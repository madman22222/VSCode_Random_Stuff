# Chess Studio in VS Code

There is one application source tree (`chess/`) and one entry point
(`chess/main.py`). The portable Windows app compiles that tree; VS Code runs it
directly. There is no second copy of the game to keep synchronized manually.

## Download the developer edition

Download [ChessStudio-VSCode.zip](https://github.com/madman22222/VSCode_Random_Stuff/releases/latest/download/ChessStudio-VSCode.zip)
and extract it completely, or clone this repository. This edition requires
**Python 3.10+ with Tkinter and VS Code**. For no separate Python installation,
use [the Windows portable app](https://github.com/madman22222/VSCode_Random_Stuff/releases/latest/download/ChessStudio-Windows.zip).

1. Open `ChessStudio.code-workspace` and trust it only if you trust this project.
2. Install the recommended Python and Python Debugger extensions if prompted.
3. Run **Terminal → Run Task → Chess: create development environment**. It creates
   `.venv`, installs the reviewed runtime dependencies locally, and checks Tkinter.
   Alternatively run `py tools/setup_dev.py` on Windows or
   `python3 tools/setup_dev.py` on Linux/macOS. Setup needs a connection; normal
   built-in play works offline afterward. On Linux your system may need `python3-tk`.
4. Run **Python: Select Interpreter** and choose `.venv`.
5. Select **Chess Studio: play (shared source)** in Run and Debug, then press **F5**.

Other launch configurations run a two-game training smoke test (isolated in
`dev-data/`) and the full regression suite. Test Explorer uses `vscode_tests.py`
to discover the same tests as `python run_tests.py`, without the local directory
name hiding the installed python-chess library. Desktop tests require a display.

## Keeping both editions aligned

Edit the files under `chess/` once. Source runs pick up the changes on restart;
an already-downloaded EXE is a built snapshot and cannot change itself when you
edit Python. Commit/push the changes and merge after CI: the release workflow
builds **both ZIPs from the same commit**, tests the extracted source edition and
actual Windows package, then publishes them together. Each carries `BUILD_INFO.json`;
compare `revision` to confirm they match. Download the new portable ZIP to use
those updates there. Updates do not silently replace a running app.

To build locally on Windows x64, from a clean committed checkout:

```powershell
python -m pip install -r packaging/requirements-build.txt
python packaging/build_source.py
python packaging/build_windows.py
python packaging/smoke_source.py --zip dist/ChessStudio-VSCode.zip --revision (git rev-parse HEAD)
python packaging/smoke_windows.py --zip dist/ChessStudio-Windows.zip
```

The source ZIP excludes runtime profiles, learning databases and generated output.
Commit new source files before packaging; untracked files are not release sources.
Dirty working trees are recorded as such and are unsuitable as exact-revision releases.

## Saves and training profiles

Code synchronization is separate from personal data. Source defaults save in
`chess/`; portable defaults save in its adjacent `data/` (with a protected-folder
fallback). Transfer with Support & study → backup/restore. A common
`CHESS_STUDIO_DATA_DIR` can deliberately select one profile folder, but do not run
competing writers simultaneously. Back up data before upgrading or moving it.
