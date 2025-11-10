"""Launcher for the chess GUI.

This file is intentionally small: it only starts the Tk mainloop and
instantiates the GameController from game_controller.py which contains
application logic.
"""

import tkinter as tk
from game_controller import GameController


def main():
    root = tk.Tk()
    app = GameController(root)
    root.mainloop()


if __name__ == '__main__':
    main()
# pyright: reportMissingImports=false, reportUnknownMemberType=false
