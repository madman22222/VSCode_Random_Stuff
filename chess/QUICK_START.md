# Chess Studio quick start

## Open the app

On Windows 10/11 x64, [download the portable ZIP](https://github.com/madman22222/VSCode_Random_Stuff/releases/latest/download/ChessStudio-Windows.zip),
extract it completely, open `ChessStudio`, and run **ChessStudio.exe**.
Keep `_internal` and the executables together. Python is included.

For development, use the root `Launch_Chess.bat` after installing Python 3.10+
with Tkinter, or follow the [source setup](README.md#launch-on-windows).
The portable app and the source-code ZIP are different downloads.

## Play your first game

1. Open **Play → Game**.
2. Select **Play AI**, a difficulty, and White or Black.
3. Press **Play**. Click a piece, then its destination.
4. Use **Hint** for a suggestion; **Pause** stops play and pending moves.
5. Use **Save** to export a PGN. **Undo** in Play AI removes your move and its reply,
   pauses play, and does not refund clock time.

Choose **Two players** for local human play or **Watch AI** to watch both sides.
Difficulty controls search effort, not a measured Elo rating. Resize the window
to resize the square board. Settings contains appearance and accessibility options.

## Practice and review

**Play → Practice** offers seven puzzles with progressive hints and saved solved
progress. **Play → Review** lets you navigate and analyze the game's positions.
Review estimates come from short searches and can be wrong. Practice and review
do not overwrite the actual game or train the engine.

For keyboard play, click a square, use arrows to move focus, Enter/Space to select,
and Escape to clear selection. Tab navigates controls.

## Try training

1. Open **Training** and choose a small additional game count, such as 2.
2. Start with a modest depth and move budget for your computer.
3. Press **Start** and monitor completed games and remembered positions.
4. Use **Stop and save** to save completed games; the unfinished game is discarded.
5. Use **Resume** to reload saved totals/settings and run more games.

Training retains existing move memory. It records outcomes rather than training
a neural network. Keep backups and use **Compare** to measure results; additional
training does not automatically mean better play.

## Keep your progress

Close the app before copying files. Back up portable `data/`; source users back
up runtime files in `chess/`. A protected portable folder uses
`%LOCALAPPDATA%\ChessStudio` instead. On the next launch an unfinished game
recovers paused. Preserve the data folder when installing a newer ZIP.

See the [full guide](README.md), [reference](QUICK_REFERENCE.md), and
[upgrade/troubleshooting guide](UPGRADES_GUIDE.md).
