Download **ChessStudio-Windows.zip**, extract the entire ZIP, open the ChessStudio
folder, and double-click **ChessStudio.exe**.

No Python, VS Code, installer, or extra downloads are required. Built for 64-bit
Windows 10/11. Keep `_internal` beside the executable. Your preferences, saved
game and training data are in `data/`; preserve that folder when upgrading.

This build bundles the Python runtime, Tkinter, Pillow, python-chess and piece
images. A console companion supports optional training commands. Stockfish is
optional and is not bundled. See the included README and BUILD_INFO.json.

The SHA-256 file lets you verify the ZIP. The release workflow tests the extracted
application with Python removed from the child process PATH before publishing.

Full user guide: https://github.com/madman22222/VSCode_Random_Stuff/blob/main/chess/README.md
Upgrade and troubleshooting: https://github.com/madman22222/VSCode_Random_Stuff/blob/main/chess/UPGRADES_GUIDE.md

New support/study tools include profile backup and restore with rollback, named
training profiles, comparison history, FEN study, annotated review export, validated
puzzle packs, diagnostics and an explicit update check. Training progress separates
completed and checkpointed games. Learning version 3 adds contextual position keys
while preserving legacy records. Search/memory limits and measured evaluation tuning
are included; no chess-strength improvement is claimed. See the bundled README
before restoring data or upgrading.

Also available: **ChessStudio-VSCode.zip**, running the same `chess/main.py` with
Python and VS Code. Both ZIPs carry the same source revision. Extract the developer
ZIP, open `ChessStudio.code-workspace`, and follow `VSCODE_GUIDE.md`.

This release fixes flag/increment handling, timeout draws, training clock pause
and PGN results/validation; adds resignation/local draw agreement and an original
tactical motif pack; and includes measured search draw-check optimization. See the
reference review for PDF corrections and study/engine limits.

This revision includes nine guided lessons/21 exercises, automatic opponent
replies and authored alternatives, factual review notes with legal
continuations, and a 16-position independent comparison suite with per-game
records. Training checkpoints now have a validated memory/progress recovery pair.
Repeated training/resume/cancel tests and interrupted-save regressions are included.
Pillow/build tooling updates preserve Python 3.10 source compatibility. Physical
Windows DPI and screen-reader verification remain open; no strength gain is claimed.

Coaching now selects up to three review moments and links them to related practice.
Adaptive practice schedules missed/hinted exercises sooner and introduces harder
material. Nine lessons/21 exercises include opening principles, defense and more
endgames. Comparison history groups compatible protocol-2 runs with uncertainty,
baseline identity and cutoff draws. Native scrollable explanations keep long text
usable. Physical monitor/screen-reader checks still require hands-on verification.

Training/search optimizations reuse exact evaluation and pawn results, speed pawn
and material calculations, and generate legal tactical continuations directly.
Training position accounting and atomic checkpoint serialization are faster.
Gzip level 1 trades larger compressed memory for lower save CPU. Depth, rules,
exploration and learning counts are preserved; both editions receive the same
changes. Profiling, exact-budget comparisons, recovery tests and extended soak
reports document behavior and hardware-dependent performance.

Visual refresh: warm neutral/emerald styling, a complete dark palette, header
theme switching, and player cards with role, turn, pause and clock information.
The move list has a helpful empty state; primary actions are easier to spot.
Menus, fields, explanations and report/coaching dialogs share the same theme.
Both editions retain responsive boards and native scrolling. Preserve data/
when upgrading. Actual Windows display/screen-reader verification remains open.
