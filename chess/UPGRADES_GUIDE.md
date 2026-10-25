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
