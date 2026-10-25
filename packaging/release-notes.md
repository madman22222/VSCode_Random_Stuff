Download **ChessStudio-Windows.zip**, extract the entire ZIP, open the ChessStudio
folder, and double-click **ChessStudio.exe**.

No Python, VS Code, installer, or extra downloads are required. Built for 64-bit
Windows 10/11. Keep `_internal` beside the executable. Your preferences, saved
game and training data are in `data/`; preserve that folder when upgrading.

This build bundles the Python runtime, Tkinter, Pillow, python-chess and piece
images. A console companion supports optional training commands. Stockfish is
optional and is not bundled. See the included README and BUILD_INFO.json.

The SHA-256 file lets you verify the ZIP. The release workflow tests the extracted
application with Python removed from the child process PATH before publishing.
