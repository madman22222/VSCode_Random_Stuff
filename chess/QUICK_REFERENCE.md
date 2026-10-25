# Chess Studio quick reference

## Navigation

| Location | Controls and purpose |
| --- | --- |
| Play | Mode, difficulty, side, Play/Pause, Hint |
| Play → Game | Move list, Save/Load PGN, Undo, New, Restart |
| Play → Practice | Seven puzzles, progressive hints, saved solved progress |
| Play → Review | Position navigation, Analyze game, Cancel |
| Training | Start, Stop and save, Resume, settings, memory import/export/reset |
| Settings → Appearance | Theme, flip board, sound, clock |
| Settings → Access | Larger text, contrast, image/symbol/letter pieces |
| Settings → AI | Advanced depth, delay, and move budget |
| Settings → Files | PGN autosaving, compression, statistics |
| Tools | Optional external engine, metrics CSV, batch PGN converter |
| Compare | Paired evaluation, cancellation, optional scoring experiment |

## Board input

| Input | Action |
| --- | --- |
| Click piece, then destination | Select and move; legal squares are highlighted |
| Arrow keys after clicking board | Move board focus, following orientation |
| Enter or Space | Select focused piece/destination |
| Escape | Clear selection |
| Tab | Navigate ordinary controls |
| Left/Right in Review | Navigate reviewed positions |

Form fields retain their normal editing keys. Promotion opens a piece chooser.
Undo in Play AI removes a move pair and pauses clocks; elapsed time is not refunded.

## Commands

From the repository root, use your virtual environment's Python:

```powershell
python chess/main.py
python chess/main.py --training --games 10 --depth 2 --move-ms 100 --batch-size 5
python chess/main.py --training --resume --games 10
python chess/main.py --benchmark --games 20 --against both --depth 2 --nodes 500
python chess/main.py --help
python chess/tactical_suite.py --depth 2 --nodes 12000
python run_tests.py
```

Portable users replace `python chess/main.py` with `.\ChessStudio-CLI.exe`
from the extracted app folder. Use **ChessStudio.exe** for the GUI.
See the [full training options](README.md#training-dashboard).

Training `--games 0` runs until stopped; comparison defaults to 20 games per
opponent and requires an even count of at least 2. `--against` accepts `both`,
`untrained`, or `previous`. `--experiment` tests scoring without enabling it.

## Files

| File/folder | Contents |
| --- | --- |
| `ai_learn.json.gz` | Compressed move memory (plain `.json` without compression) |
| `ai_learn_readable.json` | Readable memory export |
| `ai_learn.json.training.json` | Training checkpoint |
| `ai_learn.json.previous.json` | Previous memory snapshot |
| `ai_learn.json.benchmark.json` | Comparison report |
| `chess_config.json` | Preferences, statistics, and practice progress |
| `last_session.json` | Unfinished-game recovery |
| `autosaves/` | Optional automatic PGNs |

Defaults live in portable `data/` or source `chess/`. Protected-folder fallback:
`%LOCALAPPDATA%\ChessStudio` on Windows. Custom learning paths change companion
filenames. An idle `.lock` file can remain; the active OS lock controls ownership.

See [troubleshooting and upgrades](UPGRADES_GUIDE.md) before replacing data.
