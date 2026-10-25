"""VS Code Test Explorer bridge to the same suite used by run_tests.py."""
from pathlib import Path
import unittest
import run_tests  # Sets the local-module path without shadowing python-chess.


def load_tests(loader, tests, pattern):
    directory = str(Path(run_tests.chess_dir) / 'tests')
    return unittest.TestLoader().discover(directory, pattern='test_*.py', top_level_dir=directory)
