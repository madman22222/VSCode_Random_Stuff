# Chess Studio · VSCode Random Stuff

A home chess project exploring how far AI-assisted development can go. Play
against the built-in search engine, practice tactics, review games, and experiment
with outcome-based move memory and self-play training.

## Download and play

**[Download ChessStudio-Windows.zip](https://github.com/madman22222/VSCode_Random_Stuff/releases/latest/download/ChessStudio-Windows.zip)**

For **Windows 10/11, 64-bit (x64)**:

1. Extract the **entire ZIP** to a folder you own.
2. Open the extracted `ChessStudio` folder.
3. Double-click **ChessStudio.exe**.

No Python, VS Code, installer, or extra downloads are required. Built-in play,
training, practice, and review work offline. Keep `_internal` beside the
executables. Preserve `data/` when upgrading; it contains your preferences,
unfinished game, and training progress. See the [upgrade guide](chess/UPGRADES_GUIDE.md).

The green **Code → Download ZIP** button downloads development source code.
Use [Releases](https://github.com/madman22222/VSCode_Random_Stuff/releases/latest)
for the ready-to-run app. macOS/Linux users currently run from source.

## What is included

- A resizable board; Play AI, Two players, and Watch AI modes; hints and PGN save/load.
- Seven tactical practice puzzles, budgeted game review, and unfinished-game recovery.
- Themes, larger text, high contrast, image/symbol/letter pieces, and keyboard play.
- A training dashboard with checkpoints, resume, exploration, and varied openings.
- Paired comparisons against untrained and previous versions, with uncertainty ranges.
- Optional Stockfish tools, PGN conversion, and a console companion.

Training records move outcomes; this is not a neural network. Difficulty settings
are search budgets, not Elo ratings, and training does not guarantee stronger play.

## Project planning

Follow the [Chess Studio Kanban board](KANBAN.md) for completed work, prioritized
improvements, and issue acceptance checklists.

## Documentation

| Guide | Use it for |
| --- | --- |
| [Chess README](chess/README.md) | Full user guide and source setup |
| [Quick start](chess/QUICK_START.md) | First game and first training run |
| [Quick reference](chess/QUICK_REFERENCE.md) | Controls, keyboard input, and commands |
| [Upgrade and troubleshooting guide](chess/UPGRADES_GUIDE.md) | Backups, migration, and common problems |
| [Technical documentation](chess/DOCUMENTATION.md) | Architecture, persistence, and development |
| [AI notes](chess/AI_IMPROVEMENTS.md) | Search, learning, and evaluation limits |
| [Feature history](chess/IMPLEMENTATION_COMPLETE.md) | Delivered improvements and validation scope |
| [Windows packaging](packaging/README.md) | Build, smoke test, and release process |

## Run from source

Install Python 3.10+ with Tkinter. On Windows, double-click
[Launch_Chess.bat](Launch_Chess.bat); it creates a virtual environment and installs
requirements on its first run. Or follow the [manual setup](chess/README.md#launch-on-windows).
Run all source commands from the repository root, including `python run_tests.py`.

This project uses substantial AI assistance as an experiment in building and
improving a complex home project. It is a work in progress; please include your
platform, build revision, and reproduction steps when reporting an issue on
[GitHub](https://github.com/madman22222/VSCode_Random_Stuff/issues).
