````markdown
# VSCode_Random_Stuff — chess demo
This repository contains a small Python chess demo (GUI + basic AI) under the `chess/` folder.

Files in `chess/`:
- `main.py` — a tkinter-based chess GUI that uses `python-chess` for game logic and a small negamax AI.
- `requirements.txt` — lists `python-chess` and `Pillow`.
- `assets/` — optional piece images and `assets/README.md` describing filenames.
- `tools/check_engine.py` — CLI helper to verify or download a Stockfish engine and test it.

How to run (Windows PowerShell):

1. Create and activate a virtual environment (recommended):

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. Run the GUI:

```powershell
py main.py
```

Controls: click a piece, then click destination. After your move the AI will reply.

Features

- Move list and PGN save/load: save the current game to a PGN file or load a PGN file into the board (use the Save PGN / Load PGN buttons in the UI).
- Piece images: the GUI supports PNG piece images placed in `assets/` (see `assets/README.md` for filenames). If images are not present, the GUI falls back to Unicode pieces.
- Stockfish engine integration: you can toggle using an external UCI engine (Stockfish) from the UI. The app will try to auto-detect `stockfish` in your PATH; otherwise provide the path in the Engine box and click Detect/Use Engine.
- **Polyglot opening book support**: Load standard Polyglot .bin opening books for stronger opening play. The AI will consult the book before searching. Use the "Load Book" button in the "Opening Book (Polyglot)" panel to select a .bin file.

Downloader and verification

- The GUI includes a "Download" button to fetch Stockfish releases and an optional automatic downloader when verification fails.
- The GUI also exposes verification controls (Retries/Timeout/Backoff/Max wait) and a Verify button which will test the configured engine binary.
- The CLI `tools/check_engine.py` supports verifying an engine, retry/backoff, and optional `--download` to fetch a release into `engines/`.

Notes

- If you want me to bundle sample PNG pieces or integrate Stockfish automatically (download and configure), I can add that, but it requires network access or that you provide the binary.

## About Polyglot Opening Books

Polyglot (.bin) is a standard opening book format used by many chess engines and GUIs. The format was created by Michel Van den Bergh and is widely adopted in the chess programming community.

**Where to find Polyglot books:**
- Public domain books are available from various chess programming sites
- Popular books include Performance.bin, Cerebellum.bin, and others
- Books can be created from PGN game collections using tools like `polyglot make-book`

**How it works:**
- The AI checks the Polyglot book before starting its search
- If the current position is in the book, it plays a move from the book (weighted random selection)
- If not in the book, it falls back to the hardcoded opening book or begins its search
- This provides much stronger opening play than the small hardcoded book

**Note:** This implementation was inspired by Polyglot support found in repositories like Stockfish, Cute Chess, and other open-source chess projects in the broader chess programming community.
````
