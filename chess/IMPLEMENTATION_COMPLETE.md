# Delivered features and validation scope

This document records delivered work, not a claim that the project is finished
or that the AI has a measured playing strength. For current instructions use the
[README](README.md), [quick start](QUICK_START.md), and [technical guide](DOCUMENTATION.md).

## Play and UI

- Working GUI and command-line entry points; optional Stockfish integration.
- Guided Play AI, Two players, and Watch AI setup, including playing Black.
- Resizable square board and scaled hit detection; native sidebar tabs replace
  the scrolling canvas responsible for stale child-window redraws.
- Background search, thinking status, hints, cancellation, and illegal-move feedback.
- Paired Undo, completed-game learning/statistics rollback, and standard/custom-start PGN support.
- Seven practice puzzles, progressive hints, and saved solved progress.
- Position navigation and shallow background game review with cancellation.
- Atomic unfinished-game recovery, validated histories, and paused restoration.
- Larger text, contrast, multiple piece styles, and keyboard board focus.
- Cached unchanged piece/focus rendering and monotonic clock/timer fixes.

## Training and evaluation

- Training dashboard, bounded or unlimited runs, Stop and save, and Resume.
- Batched atomic checkpoints, compressed move memory, optional readable exports,
  pruning, writer leases, varied starts, and configurable early exploration.
- Paired comparisons against untrained and previous versions, fixed budgets,
  outcome reports, cutoff-draw counts, and conservative uncertainty ranges.
- Optional smoothed/capped root-score experiment with tactical, sample-size,
  outcome, and memory-fingerprint gates; off by default.

## Portable distribution

- Windows 10/11 x64 ZIP with bundled Python/Tk/Pillow/python-chess and piece assets.
- GUI and console executables sharing `_internal`; writable `data/` profiles,
  protected-folder fallback, build metadata, checksums, notices, and source archives.
- Automated Windows build, extracted-ZIP smoke check without Python on the child
  PATH, and GitHub Release publishing after successful validation.

## Evidence and limits

The portable implementation was validated with 76 source tests, Windows desktop
checks, and an actual extracted-package smoke run covering assets, gameplay,
persistence, practice, training, comparison, review, conversion, and CLI training.
The [workflows](../.github/workflows) record checks for each subsequent revision.
Desktop tests require a display and skip when unavailable. Check current CI
results rather than treating this historical test count as a permanent total.

These checks verify selected behavior. They do not prove improved chess strength,
absence of every bug, or identical rendering/performance on all computers.
Portable distribution currently targets Windows x64; other platforms use source.
