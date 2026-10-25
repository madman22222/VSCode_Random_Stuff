# Chess Studio

## Portable download: no Python required

For Windows 10/11 x64, download **ChessStudio-Windows.zip** from the repository's
[latest release](https://github.com/madman22222/VSCode_Random_Stuff/releases/latest),
extract the entire ZIP, and double-click **ChessStudio.exe** in the ChessStudio
folder. Keep `_internal` beside the executable. No installer, Python, pip,
VS Code, or network connection is needed for the built-in chess features.

Portable saves go in `data/` next to the executable. If the app is in a protected
folder, saves fall back to `%LOCALAPPDATA%\ChessStudio`. To upgrade, preserve the
old `data/` and copy it into the newly extracted folder. Existing source users
can migrate their learning JSON/gzip, training/previous/benchmark JSON, preferences,
and `last_session.json` from `chess/` into portable `data/`.

The optional **ChessStudio-CLI.exe** accepts the same training/comparison flags as
`python chess/main.py`. The normal GUI executable needs no terminal. The ZIP also
contains license notices, optional source archives, and exact build information.

Maintainers build on Windows with `python -m pip install -r packaging/requirements-build.txt`
then `python packaging/build_windows.py`. The Windows portable workflow builds
on pull requests and publishes a ready-to-run release on main only after source
regressions and an extracted-bundle smoke check pass. That check removes Python
from the child PATH and runs from an unrelated directory, testing assets, Tk/Pillow,
play, saves, practice, training, comparison, review, conversion, and the console
companion. The adjacent `.zip.sha256` file records the exact ZIP checksum.

The source-code setup below remains available for development.

Desktop chess with a resizable board, a built-in AI, optional hints, self-play
training, and comparisons against an untrained version of the same engine.
Stockfish is optional; a GPU is not needed.

## Launch on Windows

Double-click **Launch_Chess.bat** in the repository root. On its first run it
creates `.venv` and installs the Python dependencies. Later launches reuse that
environment. Install Python 3.10+ with Tkinter first. If startup fails, the
launcher keeps the error visible.

Or use the VS Code terminal from the repository root:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r chess/requirements.txt
.\.venv\Scripts\python.exe chess/main.py
```

On macOS/Linux, use `python3 -m venv .venv`, then `.venv/bin/python` in place of
the Windows Python path above. The desktop requires Tkinter (Ubuntu/Debian:
`sudo apt install python3-tk`). Headless training and comparison do not need it.

## Play

The **Play** tab groups mode, difficulty, side, and the Play button together.
Choose Play AI, Two players, or Watch AI. You can play White or Black; choosing
Black flips the board and the AI opens as White after you press Play.

Difficulty presets adjust search depth and move time; they are not Elo ratings.
Advanced depth and timing controls are in Settings. Pause cancels pending moves;
Play resumes. Hint analyzes without moving a piece or recording a training game.
Click a piece to see legal squares, then its destination. Illegal moves get a
short explanation. The last move remains highlighted. Status shows thinking
time, check, checkmate, and draw reasons.

Undo in Play AI takes back your move and its reply and pauses the clocks. It
also removes the undone decisions from the game log. Undoing a finished game
reverses that game's memory/statistics update. Clock time is not rewound. Save
and Load support standard PGN, including a nonstandard starting position.

The square board and cached piece images resize with the window. Native Play,
Training, Settings, Tools, and Compare pages replace the old scrolling canvas
of controls to avoid stale child-window redraws on Windows.

## Training dashboard

Open **Training** and set the number of additional games for the run (0 means
unlimited). Start begins a fresh set of counters while retaining learned move
memory. Stop and save finishes the current search, discards an unfinished game,
and saves completed games. Resume reloads saved totals, elapsed time, and search/
exploration settings; the Games field limits additional games in this run.

The dashboard reports completed games, wins/losses/draws by color, elapsed time,
remembered positions/moves, the current move count, and move-limit draws. It
keeps final results visible. Gameplay and training use independent search state.

Varied opening positions and modest early-game exploration expose the AI to more
positions. Exploration chooses among four moves ranked by the engine's ordering
heuristic and is limited to the first 20 played half-moves. It is configurable
and can be disabled. Games reaching their half-move limit are counted as draws.

From the repository root (use your environment's Python executable):

```powershell
python chess/main.py --training --games 10 --depth 2 --move-ms 100 --batch-size 5
python chess/main.py --training --resume --games 10
```

| Option | Meaning |
| --- | --- |
| `--games 10` | Additional completed games; 0 trains until Ctrl+C |
| `--depth 2` | Maximum search depth |
| `--move-ms 100` | Search time per move |
| `--batch-size 5` | Save every 5 games and on exit |
| `--max-plies 300` | Draw after 300 played half-moves |
| `--exploration 0.10` | Early exploration probability, 0–1 |
| `--no-varied-starts` | Train only from the initial position |
| `--seed 42` | Opening/exploration seed |
| `--resume` | Restore checkpoint counters/settings; limit is additional games |
| `--snapshot-batches 2` | Export readable memory every 2 batches |
| `--learning-file path/to/learn.json` | Separate memory file |
| `--no-compress` | Plain JSON instead of gzip |

Resume restores saved depth, move time, exploration, varied starts, and seed;
it does not continue the unfinished game. Time budgets can produce different
search depths on different hardware, so training is not bit-for-bit reproducible.

## Measure learning

The **Compare** tab runs a frozen copy of the saved AI against an identical
engine with learning disabled and, by default, the saved previous version. Each seeded opening is played twice with colors
swapped. Both sides use equal depth/node budgets. Neither engine learns during
the comparison. Results are saved and shown again next launch; cancellation
retains completed games but marks the result cancelled.

```powershell
python chess/main.py --benchmark --games 4 --depth 2 --nodes 500 --max-plies 120
```

The report includes wins, losses, draws, score percentage, move-limit draws,
seed, memory entry count, and search settings. Score is `(wins + draws/2)/games`.
Small samples and many move-limit draws are weak evidence. This is a comparison
under the reported settings, not an Elo estimate or proof of improvement. There
is also a 5-second search ceiling for unusually slow positions/hardware.

## What is learned and saved

This is a search engine with outcome-based move memory, not a neural network.
It records wins, losses, and draws for played position/move pairs, then uses
those records in move ordering. Training does **not** guarantee stronger play.

Default files in portable `data/` or, when running from source, `chess/`
(independent of the working directory):

- `ai_learn.json.gz`: move memory (or `ai_learn.json` without compression).
- `ai_learn_readable.json`: readable memory export.
- `ai_learn.json.training.json`: counters and training settings.
- `ai_learn.json.benchmark.json`: latest comparison result.
- `ai_learn.json.previous.json`: pre-training memory snapshot.
- `last_session.json`: unfinished-game recovery.
- `autosaves/`: PGNs when automatic game-end saving is enabled.
- `chess_config.json`: preferences, saved atomically independent of launch folder.

Checkpoints replace files atomically. An OS-held writer lock rejects competing
trainers/saves against one learning file; the lock releases on process exit.
A remaining `.lock` file is normal. Use separate `--learning-file` paths for
simultaneous trainers. Hints and comparisons operate on frozen copies.

## Checks

```powershell
python run_tests.py
```

Desktop integration tests need a display; on Linux use
`xvfb-run -a python run_tests.py`. They cover resizing, scaled clicks, themes,
Black-side openings, Watch AI start/pause, stale-search cancellation, hints,
paired undo, and dashboard resume. They skip in a headless run. Unit tests also
cover legal moves, persistence, writer locking, budgets, exploration, resume,
paired comparisons, failure reporting, and the CLI.

## Tactical checks and practice

The **Play → Practice** page contains seven hand-built puzzles: mate in one for
both colors, winning a queen, promoting before a pawn is lost, escaping check,
saving an attacked queen, and preventing mate. Legal alternatives that meet the
puzzle goal are accepted. Hints are progressive; solved progress is saved in
preferences. The game and clocks remain paused and untouched while practicing.

Run the same tactical regressions from the repository root:

```powershell
python chess/tactical_suite.py --depth 2 --nodes 12000
```

## Game review

Open **Play → Review** during or after a game. Use the first/previous/next/last
buttons or Left/Right to inspect positions. Analyze game runs in the background
and shows the played move, a suggested alternative, an estimated change in pawn
units, and possible mistakes. Analysis is budgeted and shallow: suggestions can
be wrong, and uncertain/mate scores are not presented as precise guarantees.
Cancel stops after the current bounded search. Returning to Game restores the
original board and learning log; review never trains the AI.

## Recover an unfinished game

`last_session.json` is written atomically after position changes, periodically
for clock updates, and on close. The next launch restores move history, mode,
side, orientation, learning log, and remaining clock time. Clocks stay paused
until Play. Practice/review positions are never saved over the actual game.
Finished games clear the recovery file. Invalid recovery files are retained as
`last_session.invalid-*.json` when possible, and the app reports the problem.
There is one recovery slot per preferences folder.

## Accessibility

Settings now has Appearance, Access, AI, and Files pages. **Access** offers
Normal/Large text, a high-contrast board/highlights, and image, symbol, or letter
pieces. Click the board, then use arrows to move visible focus and Enter/Space
to select a piece or destination. Escape clears selection; Tab navigates normal
controls. The board follows its orientation when moving keyboard focus. Form
fields keep their normal editing keys.

## Stronger comparisons and experimental scoring

Before a new training run, the current move memory and scoring setting are saved
as `ai_learn.json.previous.json`. Resume retains that previous-version reference.
Newly trained data resets outcome scoring to off until revalidated.

Comparison now defaults to 20 games **per opponent**, against both the untrained
engine and that previous snapshot. Both use the same seeded opening pairs and
node/depth budgets. Missing snapshots are reported. The conservative 95% range
uses one color-swapped pair as the sampling unit and Hoeffding's bounded-mean
inequality. Small samples produce wide ranges; this measures performance on the
sampled opening distribution, not all chess positions or an Elo rating.

```powershell
python chess/main.py --benchmark --games 20 --against both
python chess/main.py --benchmark --games 20 --against both --experiment
```

The optional experiment tests a root move-score prior from remembered outcomes.
At least five observations are required, results are smoothed with neutral
prior weight, and the adjustment is capped at 25 centipawns (a quarter-pawn).
It cannot override checkmate scores. Ordinary play keeps this **off by default**.
A completed experiment must have at least 20 pairs per opponent, a conservative
lower score bound above 50% against both opponents, no majority of move-limit
draws, and all tactical cases passing before the UI recommends enabling it.
The Enable button also checks that the memory has not changed since evaluation.
A small smoke experiment does not meet this bar and does not enable the feature.

Reports retain settings, uncertainty ranges, tactical results, and a memory
fingerprint. The 5-second search ceiling still applies on unusually slow
positions/hardware. Tests and comparisons do not establish that training has
improved strength without sufficient results.

## Rendering and clock fixes

Unchanged board squares retain their piece items; only changed pieces are
recreated. Scaled image and focus-render caches avoid repeated graphics work.
A local microbenchmark compares repeated unchanged redraws; it is not an FPS or
cross-machine guarantee. Search-score priors are skipped entirely when inactive.
Clocks use monotonic time, settle partial ticks on stop/switch, and cancel the
old timer before starting another one.

## Tools and troubleshooting

**Tools** contains optional Stockfish detection/download/verification, the engine
toggle, metrics export, and batch PGN conversion. Downloads require a connection;
the built-in engine does not. Stockfish is a separate optional executable.

See [Quick start](QUICK_START.md), [Quick reference](QUICK_REFERENCE.md), and
[Upgrade and troubleshooting guide](UPGRADES_GUIDE.md). Developer information is
in [Technical documentation](DOCUMENTATION.md), [AI notes](AI_IMPROVEMENTS.md),
and the [Windows packaging guide](../packaging/README.md).

Portable console examples (PowerShell, from the extracted ChessStudio folder):

```powershell
.\ChessStudio-CLI.exe --training --games 10 --depth 2 --move-ms 100 --batch-size 5
.\ChessStudio-CLI.exe --training --resume --games 10
.\ChessStudio-CLI.exe --benchmark --games 20 --against both
```

Use `--help` for the full argument list. `--learning-file` selects a separate
memory database for that command; use it again on later commands for that profile.
Relative custom paths resolve against the command's working directory.
`CHESS_STUDIO_DATA_DIR` overrides the default writable folder for a process.
Close other writers and back up data before moving or replacing a profile.
