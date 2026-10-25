# Chess Studio technical documentation

For installation and gameplay see the [user guide](README.md). Commands here run
from the repository root with the project's Python environment.

## Architecture

| Module | Responsibility |
| --- | --- |
| `main.py` | GUI/CLI entry point, argument validation, headless training/comparison |
| `game_controller.py` | Game state, Tk controls, tasks, AI integration, PGN and tools |
| `studio_features.py` | Practice, review, accessibility, recovery, comparison evidence |
| `enhanced_board_view.py` | Scaled board rendering, cached pieces, focus and input |
| `simple_ai.py` | Bounded search, evaluation, move memory and serialization |
| `training_ai.py` | Self-play, checkpoints, writer leases, comparison series |
| `game_review.py` | Budgeted position analysis for game review |
| `tactical_suite.py` | Shared tactical fixtures and engine regression runner |
| `session_store.py` | Validation and storage of unfinished sessions |
| `config_manager.py` | Preferences and statistics with atomic writes |
| `app_paths.py` | Writable profile paths versus bundled immutable resources |
| `engine_manager.py` | Optional UCI engine discovery and execution |
| `chess_clock.py` | Monotonic elapsed time and timer lifecycle |
| `sound_manager.py` | Optional Windows sound playback |
| `tools/batch_pgn_converter.py` | Batch PGN conversion, also imported by the GUI |
| `diagnostics.py` | Isolated end-to-end diagnostic run and JSON report |

`python-chess` provides the board model, legal moves, PGN, and UCI support.
Tkinter provides the desktop; Pillow handles piece images. Runtime requirements
are in `requirements.txt`. Source Python is 3.10+; Windows bundles use Python 3.11.
The directory name `chess/` can conflict with imports if tests are launched
incorrectly; use the root `run_tests.py` runner.

## State and background work

The controller owns the live board and UI. Gameplay, hints, training, comparison,
and review use independent search state/frozen copies where appropriate.
Workers return UI work through the main-thread `_post_ui` queue. Stale searches
are discarded after mode/position changes or pause. New background features must
preserve these boundaries and never update Tk widgets directly from a worker.

The live game's move log supplies outcome learning. Undo removes undone choices
and rolls back a completed game's learning/statistics update. Practice/review
use separate positions and do not replace live game history or recovery data.
Clock elapsed time is not rolled back by Undo.

The UI has native notebook pages; do not reintroduce a scrolling canvas containing
native child controls without checking Windows redraw behavior. Board rendering
retains unchanged piece items, caches scaled assets, and follows actual square
size for clicks and keyboard focus. Clocks use monotonic time and cancel old
timers before starting replacements.

## Paths and persistence

`resource_dir()` resolves source resources or PyInstaller's `_MEIPASS` directory.
`data_dir()` chooses an explicit `CHESS_STUDIO_DATA_DIR`, portable EXE-adjacent
`data/`, or source `chess/`. A non-writable default falls back to
`%LOCALAPPDATA%/ChessStudio`, or `~/.local/share/ChessStudio` if LOCALAPPDATA is
unavailable. An invalid explicit override reports an error rather than silently
selecting another profile. The chosen directory is cached for the process.

Configuration and session paths follow the writable profile. Learning companion
files follow the selected memory path. Atomic replacement protects checkpoints
from partially written files. OS-held writer leases reject concurrent writers
for the same memory; a leftover lock filename alone is not an active lease.
See the [file reference](QUICK_REFERENCE.md#files) and [migration guide](UPGRADES_GUIDE.md).

Session recovery validates replayed move history, learning log, and clock state.
Restored games remain paused. Invalid recovery files are preserved when possible.
Training checkpoints restore counters and settings, not a half-finished game.

## Engine behavior

See [AI implementation notes](AI_IMPROVEMENTS.md). Distinguish move ordering
from the optional experimental root-score prior. Ordering changes which moves
are explored first; finite budgets mean it can still change selected moves.
Do not infer proven strength gains from training counts or one short comparison.

## Development checks

```powershell
python -m pip install -r chess/requirements.txt
python run_tests.py
python chess/tactical_suite.py --depth 2 --nodes 12000
python chess/main.py --diagnostics-report diagnostics.json
```

Desktop integration tests and diagnostics require a display. On Linux with Xvfb:

```bash
xvfb-run -a python run_tests.py
xvfb-run -a python chess/main.py --diagnostics-report diagnostics.json
```

Without a display, desktop tests skip; a passing headless run does not verify
rendering. Tests cover search legality/budgets, persistence/locking, CLI training,
resume, paired comparison, review/practice/recovery, accessibility, clock and
redraw behavior, and portable paths. Diagnostics use an isolated temporary
profile and exercise assets, gameplay, saves, training, comparison, review,
practice, and conversion. Inspect the report's success field and failures.

The source CI workflow runs Linux and Windows checks. The
[portable workflow](../packaging/README.md) additionally tests the actual extracted
Windows ZIP and console companion with Python removed from the child PATH.
These checks cannot establish chess strength or cover every display/driver setup.

## Extending the app

Keep rules in python-chess, use independent bounded searches for background work,
and route resources and mutable files through `app_paths`. Add regression checks
for changed behavior, especially cancellation, profile isolation, and recovery.
When changing CLI flags, update the quick reference and user guide. When changing
packaged imports or resources, rerun the extracted-bundle smoke test.

Third-party notices and source archives travel in portable `LICENSES/` and
`SOURCE/`. Inspect those files for the exact versions and license texts shipped.

## Backlog implementation additions

`training_controls.py` separates dashboard/comparison callbacks from game controls.
`studio_tools.py` owns support/profile/study dialogs and blocks conflicting UI work
with a modal maintenance task while workers return results through `_post_ui`.
`profile_store.py` provides bounded, checksummed archives, writer leases, restore
validation and rollback; runtime inputs are checked by `data_validation.py`.
`support_tools.py` provides metadata-only reports and explicit release lookup.
`puzzle_packs.py` validates attributed JSON packs; `learning_keys.py` defines the
version-3 state key and deliberate retention of unmappable legacy records.

Comparison series append immutable timestamped reports per profile. Search tables
use bounded FIFO replacement; learning pruning remains a soft cap with a cooldown.
Training snapshots distinguish elapsed/session time, checkpointed totals and recent
results. Logs rotate locally and support exports omit logs/games by default.

Benchmark commands and raw A/B/smoke reports are in `benchmarks/`. The retained
reference evaluation permits repeatable comparisons. The small migration smoke
uses cutoff-heavy games and cannot establish playing-strength improvement.
See [manual verification](MANUAL_VERIFICATION.md) for real DPI/screen-reader work.
