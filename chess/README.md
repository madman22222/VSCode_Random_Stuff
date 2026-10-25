# Chess Studio

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
engine with learning disabled. Each seeded opening is played twice with colors
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

Default files beside the code:

- `ai_learn.json.gz`: move memory (or `ai_learn.json` without compression).
- `ai_learn_readable.json`: readable memory export.
- `ai_learn.json.training.json`: counters and training settings.
- `ai_learn.json.benchmark.json`: latest comparison result.
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
