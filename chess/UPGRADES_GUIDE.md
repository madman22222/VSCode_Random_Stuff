# Upgrades, backups, and troubleshooting

## Upgrade the Windows portable app

1. Stop training with **Stop and save**, then close all Chess Studio processes.
2. Back up the complete old `data/` folder outside the app folder.
3. Download the [latest portable ZIP](https://github.com/madman22222/VSCode_Random_Stuff/releases/latest)
   and extract it into a new folder.
4. Copy the old `data/` contents into the new app's `data/` folder.
5. Run the new `ChessStudio.exe` and check your preferences and training totals.

Keep the previous app and backup until satisfied. Do not replace `_internal`
independently of the executables. If the old app used a protected folder, its data
may be in `%LOCALAPPDATA%\ChessStudio`; copy from there instead. An explicit
`CHESS_STUDIO_DATA_DIR` override takes precedence. Do not copy while files are
being written.

## Move from source to portable

Close the source app and trainer. Copy your runtime files from `chess/` into
portable `data/`: `chess_config.json`, `last_session.json`, learning `.json`/`.gz`,
readable exports, training/previous/benchmark companion files, and `autosaves/`
if desired. Preserve filenames and keep a backup. If you used a custom learning
path, migrate that profile separately and select the same path in CLI commands.

Both source and portable defaults avoid depending on the launch directory.
Relative custom paths do depend on the working directory. PGNs explicitly saved
through the file dialog stay wherever you chose.

## Common problems

| Symptom | What to check |
| --- | --- |
| Source ZIP does not contain an EXE | Download `ChessStudio-Windows.zip` from Releases |
| EXE cannot find a library or images | Extract the entire archive again; keep `_internal` beside both EXEs |
| Saves appear missing after upgrading | Restore the previous data folder; also check the protected-folder fallback or data override |
| Source launcher fails | Install Python 3.10+ with Tkinter; keep the launcher's error output |
| `No module named chess` or `PIL` | Install `chess/requirements.txt` using the same Python that launches the app |
| Tkinter missing on Linux | Install your distribution's Tkinter package; desktop use also requires a display |
| AI responds slowly | Lower difficulty/depth and move budget; timing depends on position and hardware |
| Board is hard to read | Try Settings → Access contrast/text/piece options and resize the window |
| Cannot save or start training | Check folder permissions and close another writer using the same memory file |
| Trainer reports memory is in use | Stop the other app/trainer or choose a separate `--learning-file`; deleting `.lock` does not release an active lock |
| No sound | Enable sound; WAV playback uses Windows winsound, with beeps for important events when files are missing |
| External engine fails | Detect/select and Verify a compatible UCI executable in Tools; built-in play needs no Stockfish |
| Review suggestion looks wrong | Review is shallow and budgeted; treat it as an estimate |
| Training gains look uncertain | Use paired comparisons, larger samples, and inspect move-limit draws and uncertainty ranges |

The sidebar uses native tabs instead of the old scrolling control canvas. If a
rendering problem remains, report the build revision, Windows display scaling,
window size, and steps needed to reproduce it.

## Recovery and damaged data

Unfinished games restore paused on next launch. Practice/review do not replace
the recovery slot. Invalid session files are retained as
`last_session.invalid-*.json` when possible. Back up files before resetting or
editing anything; resetting learning removes accumulated memory. Do not assume
that every persistence error can recover automatically.

## Report a problem

Use [GitHub Issues](https://github.com/madman22222/VSCode_Random_Stuff/issues).
Include OS/architecture, portable or source setup, `BUILD_INFO.json` revision for
portable builds (or `git rev-parse HEAD` for source), reproduction steps, expected
behavior, and error text. Share a minimal PGN or position when relevant.

Developers can run `python run_tests.py` and
`python chess/main.py --diagnostics-report diagnostics.json` from the repository
root. Diagnostics require a desktop display and use an isolated temporary
profile. Portable users can run `.\ChessStudio-CLI.exe --diagnostics-report diagnostics.json`.
See [technical documentation](DOCUMENTATION.md) for validation details.

## In-app backup and format migration

Use **Support & study → Back up data** before upgrading. **Restore data** validates
archive checksums, supported paths, sizes and runtime input formats, previews the
file list, and keeps a rollback copy under `backups/`. Restore requires idle tasks
and closes the app after success to prevent stale in-memory saves. It does not
include logs or arbitrary CLI profiles outside the GUI data folder.

Version-3 learning preserves older placement-only records without inventing turn,
castling or en-passant state. Older records remain exportable but new searches use
new contextual keys; scoring approval is reset for legacy files. Expect new data
to accumulate gradually, rather than an immediate inherited strength improvement.
Unreadable preferences/memory are left intact and cannot be silently overwritten.
Use a known-good backup or move damaged files aside before starting fresh.

## Guided-learning and checkpoint update

Keep the whole data folder, including `ai_learn.json.checkpoint.json` (and matching
files inside named profiles). It couples memory with training progress so Resume
can repair a process interruption between saves. Older profiles without a journal
remain readable. If moves were learned or imported after a checkpoint, Resume
refuses to replace that newer memory; choose Start for a new set of counters.
Back up before upgrading; journal recovery is not a hardware/power-loss guarantee.
Lesson progress stays in preferences. Both ZIPs include the same course and
evaluation resources and must be rebuilt/downloaded together to receive updates.

Coaching/adaptive update: both editions share nine lessons/21 exercises, three
review moments linked to practice, local spaced review scheduling and comparable
protocol-2 evaluation trends. Existing solved progress is retained. Preserve
`chess_config.json` with the complete data folder to keep the new practice schedule.
Physical Windows scaling, screen-reader and owner-profile upgrade checks remain
unverified; use the manual checklist and retain a backup.

Training optimization update: evaluation/pawn caches are bounded and reset per
search; bitboard calculations, legal capture/promotion generation and incremental
position accounting preserve the existing search and learned-count semantics.
Checkpoint writes use compact JSON and faster gzip compression, so compressed
memory files can be larger. Preserve the full data folder, including the journal.
Depth, time budgets and exploration defaults are retained. See the repository
`benchmarks/TRAINING_PERFORMANCE.md` for reproducible A/B checks and timing limits.
