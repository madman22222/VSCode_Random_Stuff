# AI chess and self-play training

A desktop chess game using Python, Tkinter, and `python-chess`. The built-in AI
works without Stockfish or a GPU. Stockfish integration remains optional.

## Start in VS Code (Windows)

Open the repository folder, then open **Terminal → New Terminal** and run:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r chess/requirements.txt
.\.venv\Scripts\python.exe chess/main.py
```

In the window, choose **Player vs AI**, then press **Start Game**. You play White.
Click your piece, then its destination. Other modes include Player vs Player,
AI vs AI, and Training AI. The board and pieces resize with the window. Use the Play, Training, Settings,
and Tools tabs to find controls. The old scrolling control panel has been
replaced by native tabs to avoid stale redraws while scrolling on Windows.

On macOS/Linux, create the environment with `python3 -m venv .venv`, install with
`.venv/bin/python -m pip install -r chess/requirements.txt`, and launch with
`.venv/bin/python chess/main.py`. The desktop requires Tkinter (Ubuntu/Debian:
`sudo apt install python3-tk`). Training works without a display or Tkinter.

## Train from the terminal

From the repository root:

```powershell
.\.venv\Scripts\python.exe chess/main.py --training --games 10 --depth 2 --move-ms 100 --batch-size 5
```

The AI plays both sides, prints a result after each game, and stops after exactly
10 completed games. Use `--games 0` to keep training until Ctrl+C. Stopping saves
completed games; an interrupted game is discarded because it has no result.

Options:

| Option | Meaning |
| --- | --- |
| `--games 10` | Complete 10 games; 0 means run until stopped |
| `--depth 2` | Maximum search depth in half-moves |
| `--move-ms 100` | Time budget for each move in milliseconds |
| `--batch-size 5` | Save after every 5 games; also save on exit |
| `--max-plies 300` | End a game as a draw after 300 half-moves |
| `--snapshot-batches 2` | Export readable learning after every 2 batches |
| `--learning-file path/to/learn.json` | Use a separate learning database |
| `--no-compress` | Save plain JSON instead of gzip |

The GUI's **Training AI** mode uses the same training module, including its
Games limit, batch size, move time, and snapshot settings. Press Pause to stop.
Closing the window also stops training and saves it.

## What the AI learns

This is a small search engine with outcome-based move memory, not a neural
network. It records wins, losses, and draws for moves in positions it has played.
On later searches, those results influence which moves it examines first.
Self-play does not guarantee stronger play, and games stopped by the move limit
are recorded as draws. More training is not a measured strength improvement.

By default, learning is stored beside the code in `chess/ai_learn.json.gz`, with
a readable summary in `chess/ai_learn_readable.json`. The app reloads that memory
when launched again. Writes replace the database atomically, and switching
compression removes the stale alternate format. Custom `--learning-file` data
is used only by runs that specify that path. Avoid training in two processes
against the same learning file at once.

## Checks

```powershell
.\.venv\Scripts\python.exe run_tests.py
```

The suite covers legal moves, promotion, castling heuristics, timed-search board
restoration, exact training limits, interrupted training, error reporting, saved
learning reloads, compression switching, and the headless CLI.

For real desktop layout checks (including resize, tabs, themes, and scaled
clicks), run `python run_tests.py` with a desktop display. On Linux CI, use
`xvfb-run -a python run_tests.py`. These three tests skip when no display exists.
