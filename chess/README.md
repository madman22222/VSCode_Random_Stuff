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

Checkpoints publish a validated recovery record before updating memory and
counters. Resume can recover an interrupted publication; unreadable inputs remain
preserved. If gameplay/imports changed memory after the checkpoint, exact resume
is refused: Start a new run retains the newer memory. Keep the entire profile
when upgrading or backing up, including `.checkpoint.json`. This protects process
interruptions; it is not a guarantee against hardware/power-loss corruption.

Resume restores saved depth, move time, exploration, varied starts, and seed;
it does not continue the unfinished game. Time budgets can produce different
search depths on different hardware, so training is not bit-for-bit reproducible.

## Measure learning

The **Compare** tab runs a frozen copy of the saved AI against an identical
engine with learning disabled and, by default, the saved previous version. Each seeded position from an independent 16-position catalogue is played twice with colors
swapped. Both sides use equal depth/node budgets. Neither engine learns during
the comparison. Results are saved and shown again next launch; cancellation
retains completed games but marks the result cancelled.

```powershell
python chess/main.py --benchmark --games 4 --depth 2 --nodes 500 --max-plies 120
```

The report includes wins, losses, draws, score percentage, move-limit draws,
seed, memory entry count, search settings, corpus version/checksum, remembered root count,
category totals and a per-game ledger. Evaluation roots are disjoint from all
training opening seed prefixes; self-play may later encounter them, so memory
overlap is reported rather than assuming a permanent holdout. Score is `(wins + draws/2)/games`.
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
- `ai_learn.json.checkpoint.json`: atomic recovery pair of memory and training progress.
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

The **Play → Practice** page contains nine guided lessons and 21 built-in exercises.
The original seven hand-built puzzles cover mate in one for
both colors, winning a queen, promoting before a pawn is lost, escaping check,
saving an attacked queen, and preventing mate. Six new exercises cover forks, pins,
queen/rook mates, king-and-pawn play, and calculation against different defenses.
Eight additional exercises cover opening principles, defensive replies, reversed-color
endings and avoiding stalemate.
The opponent replies automatically; Restart cycles authored defenses. Choose a
lesson or Continue recommended lesson; solved progress and lesson selection are saved.
See [guided learning and pack version 2](GUIDED_LEARNING.md). Legal alternatives that meet the
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
units, and possible mistakes. A short legal continuation follows exact cached
search entries when available. Factual notes describe checks, absolute pins,
multiple attacks and unprotected pieces to inspect; they do not prove a gain.
The separate annotated PGN export includes the line and uncertainty notice. Analysis is budgeted and shallow: suggestions can
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

## Support, backups, and study tools

The header's **Support & study** menu provides:

- **Back up data / Restore data**: checksum-verified ZIP archives of GUI profiles,
  preferences, unfinished sessions, autosaves, puzzle packs and comparison history.
  Restore previews the files and keeps a `backups/before-restore-*.zip` rollback
  archive. Close other app instances and stop background tasks first. Restore
  closes the app after success; reopen it to load the restored state. Logs,
  executables and arbitrary CLI memory files outside this data folder are excluded.
- **Select/create training profile**: a separate `profiles/NAME/ai_learn.json`
  database and companion files. Switching starts a new paused game and does not
  transfer the old game's learning log. Save a PGN before switching if needed.
- **Comparison history**: view/export or explicitly delete an individual historical
  report. Deletion leaves memory and the latest comparison file intact.
- **Memory limits**: configure a bounded FIFO search table and move-memory soft cap.
  Reducing learning limits can discard records after completed games; back up first.
- **Study a FEN / Copy FEN**: validate a position and analyze it in the isolated
  Review workspace. Returning to Game restores the real board and recovery slot.
- **Export reviewed PGN**: save shallow review annotations, preserving the starting
  position. Quick and Deeper review budgets are selectable; neither is definitive.
- **Import puzzle pack**: load a validated, attributed local JSON pack. Packs and
  solved IDs persist; different packs use separate IDs. An example with four extra
  themed puzzles is in `assets/puzzles/studio-extras.json` (portable:
  `_internal/assets/puzzles/studio-extras.json`). The pack format requires version,
  ID, author, puzzles with valid FENs, hints and legal UCI solutions; see that example.
  Version 2 accepts validated multi-move lines and goals; see [the format guide](GUIDED_LEARNING.md).
- **About / export diagnostics**: show revision, runtime, active paths and memory
  counts. The export excludes logs, games and move memory; review paths before sharing.
  Local logs rotate in `logs/application.log` (three retained backups).
- **Check for updates**: explicitly opt in to one GitHub request and compare the
  published revision. Offline use works normally. No executable is downloaded,
  replaced, or installed automatically. Back up data before changing ZIP versions.

Training now has **Dashboard**, **Run settings**, and **Memory** subpages. Its
summary separates games completed from checkpointed totals, shows recent outcomes
and games/minute, and estimates remaining time only for bounded runs with enough
completed games. The estimate can vary substantially with game length/hardware.

### Learning-format migration

New memory uses **version 3** position keys with piece placement, side to move,
castling rights and legal en-passant rights. Versions 1/2 and readable exports are
accepted after bounded validation. Legacy placement-only counts are retained for
backup/export but do not bias new contextual positions: missing state cannot be
reconstructed reliably. New games accumulate contextual records alongside them.
Legacy scoring approval is reset; experimental scoring needs fresh evidence.
Keys still omit repetition history and draw counters, so this is not a complete
representation of all chess history. More data does not establish stronger play.

Invalid or future-format preferences/memory are preserved and normal saves refuse
to overwrite them. Restore a known-good backup or move the damaged file aside
before starting a fresh profile. JSON inputs have a 32 MiB decompressed limit;
backups allow at most 2,000 runtime files and 128 MiB uncompressed archive contents.
Custom CLI learning paths remain your responsibility to back up separately.

For remaining hardware/accessibility checks see [manual verification](MANUAL_VERIFICATION.md).
Contributors can use [CONTRIBUTING.md](../CONTRIBUTING.md) and the
[benchmark harness](../benchmarks/README.md).

## Reference material and VS Code

See the [PDF compatibility review](REFERENCE_REVIEW.md) for verified rules, known
reference simplifications, supported tactics/study inputs and limits. Support &
study now includes Resign and local draw agreement. Timeouts account for the
nonflagging side's mating material; PGN results/headers persist. Claimable draws
are auto-accepted as a casual-play policy, rather than requiring tournament claims.

A second optional original practice pack, `assets/puzzles/reference-themes.json`,
demonstrates forks, pins, skewers and discovered check. Import it with Support &
study → Import puzzle pack. It is not a copy of the PDF diagrams or an exhaustive
course. PDFs themselves cannot be imported as training memory.

[The VS Code edition](../VSCODE_GUIDE.md) runs this same source with F5/Test Explorer
configuration. Both editions are released from one commit; compiled EXEs need the
new ZIP to pick up source changes. User profiles do not synchronize automatically.

## Coaching and scheduled review

After a game, choose Review → Analyze game → Coaching moments. Inspect up to three
useful positions or open a related authored exercise. Practice → Adaptive practice
prioritizes missed/due exercises and introduces progressively harder material.
Hints and mistakes shorten the review schedule; success intervals grow to 30 days.
Nine lessons/21 exercises include opening principles, defensive play and endings
with either color. Long explanations scroll in native text areas.

Comparison history now offers trends across saved versions, grouping only matching
protocol-2 corpus, search budgets, seed, baseline and scoring mode. It displays
uncertainty and cutoff draws alongside descriptive score changes. Older raw
reports remain available. See [the full guide and limitations](GUIDED_LEARNING.md).

Training optimization update: evaluation/pawn caches are bounded and reset per
search; bitboard calculations, legal capture/promotion generation and incremental
position accounting preserve the existing search and learned-count semantics.
Checkpoint writes use compact JSON and faster gzip compression, so compressed
memory files can be larger. Preserve the full data folder, including the journal.
Depth, time budgets and exploration defaults are retained. See the repository
`benchmarks/TRAINING_PERFORMANCE.md` for reproducible A/B checks and timing limits.

The [visual refresh](UI_GUIDE.md) adds a header theme toggle, player/clock cards,
consistent light/dark controls and dialogs, clearer primary actions and an empty
move-history hint. Your theme preference is saved; resizing and native text
scrolling remain available.
