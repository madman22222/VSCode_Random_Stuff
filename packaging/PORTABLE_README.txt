CHESS STUDIO - WINDOWS PORTABLE

1. Extract the ENTIRE ZIP to a folder you own, such as Downloads or Documents.
2. Open the ChessStudio folder.
3. Double-click ChessStudio.exe.

No Python, VS Code, installation, or administrator access is needed.
Windows 10/11, 64-bit (x64).
Keep _internal beside both executables. Do not run the app from inside the ZIP.
The built-in AI, practice, review and training work offline. Stockfish is optional
and is not required or bundled.

YOUR SAVES
Preferences, unfinished games, training memory and progress go in data/ beside
this app. Keep that folder when upgrading; copy it into the new extracted app
folder. If the app folder is protected, saves fall back to
%LOCALAPPDATA%\ChessStudio. Extracting into your own folder avoids that fallback.

ChessStudio-CLI.exe is optional and supports training/comparison commands.
It is not needed for normal play or training through the GUI.

BUILD INFORMATION
See BUILD_INFO.json for the exact source revision and runtime versions.
Optional source archives and dependency license notices are in SOURCE/ and
LICENSES/. You do not need to open or install them to run the app.

Project: https://github.com/madman22222/VSCode_Random_Stuff

Full user guide: https://github.com/madman22222/VSCode_Random_Stuff/blob/main/chess/README.md
Upgrade and troubleshooting: https://github.com/madman22222/VSCode_Random_Stuff/blob/main/chess/UPGRADES_GUIDE.md

FIRST STEPS
Open Play, choose Play AI / Two players / Watch AI, then press Play.
Training has Start, Stop and save, and Resume. Compare measures saved memory
against fixed opponents; training is not a guarantee of stronger play.
Play also contains Practice puzzles and shallow Review analysis.
Settings includes larger text, high contrast, and keyboard-accessible pieces.

Keyboard: click the board, arrows move focus, Enter/Space selects, Escape clears.
Use Save to export a PGN. Keep a backup of data/ before updating or resetting.

SUPPORT & STUDY MENU
Use the header menu for backup/restore, named training profiles, comparison history,
FEN study, reviewed PGN export, puzzle-pack import, diagnostics, memory limits and
an optional online release check. Restore previews files, keeps a rollback ZIP and
closes the app; reopen afterward. Diagnostics exclude logs and game memory by default.
Training now has Dashboard, Run settings and Memory pages. Version-3 learning keeps
legacy records but learns contextual position records separately; no strength gain
is guaranteed. Back up custom CLI files outside data/ separately.
