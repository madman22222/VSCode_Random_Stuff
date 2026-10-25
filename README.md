## Ready-to-run Windows app

Download [ChessStudio-Windows.zip](https://github.com/madman22222/VSCode_Random_Stuff/releases/latest/download/ChessStudio-Windows.zip),
extract the entire ZIP, then open **ChessStudio.exe** inside the ChessStudio folder.
No Python, VS Code, installer, or extra downloads are needed (Windows 10/11 x64).
Keep `_internal` beside the executable and preserve `data/` when upgrading.

The green **Code → Download ZIP** button contains source code, not the portable app.
Use the [Releases page](https://github.com/madman22222/VSCode_Random_Stuff/releases/latest)
for the ready-to-run download. See [chess/README.md](chess/README.md) for features.

# VSCode Random Stuff

This repository contains a small Python chess project located in the `chess/` folder.

P.S. this project is don almost solely with AI so this is not a show of my skills but more of my thougght prosses and yes a lot has been done between editions. I have forgoten a few times to push till after somethings have been done.

See `chess/README.md` for usage, installation instructions, and details about the GUI, AI, and engine integration.

If you want to run the chess app, open a terminal in the `chess/` directory and follow the steps in that README.

Enjoy!
# VSCode_Random_Stuff
There is a lot of AI use in this project mainly to see how far I can push it with something as complicated as Chess.
This repository currently contains a small Python chess demo (GUI + basic AI).

Files added:
- `main.py` — a tkinter-based chess GUI that uses `python-chess` for game logic and a small negamax AI.
- `requirements.txt` — lists `python-chess`.
- `.gitignore` — ignores virtualenv and cache files.

How to run (Windows PowerShell):

1. Create and activate a virtual environment (recommended):
# VSCode_Random_Stuff

This workspace contains multiple small experiments. The chess demo and framework have been moved into the `chess/` folder so you can reuse it as a template for other projects.

Open `chess/README.md` for full instructions on running the chess demo and using the engine downloader / verifier.
