"""Real Tk layout regressions. Run with a desktop or virtual DISPLAY."""
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import chess
import tkinter as tk
from config_manager import ConfigManager
from game_controller import GameController


@unittest.skipUnless(os.environ.get('DISPLAY') or os.name == 'nt',
                     'Needs a desktop display')
class TestResponsiveUI(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = tk.Tk()
        self.addCleanup(self.close_root)
        config = ConfigManager(str(Path(self.tmp.name) / 'config.json'))
        with patch('game_controller.ConfigManager', return_value=config):
            self.app = GameController(self.root)
        self.pump()

    def close_root(self):
        for callback in self.root.tk.call('after', 'info'):
            self.root.after_cancel(callback)
        self.root.destroy()

    def pump(self):
        for _ in range(8):
            self.root.update()
            time.sleep(0.015)

    def test_layout_grows_without_clipping_pages(self):
        sizes = []
        for geometry in ('980x720', '1220x820', '1600x1000'):
            self.root.geometry(geometry)
            self.pump()
            view = self.app.board_view
            sizes.append(view.square_size)
            self.assertLessEqual(view.square_size * 8 + 24,
                                 min(self.app.board_area.winfo_width(),
                                     self.app.board_area.winfo_height()))
            for page in self.app.control_pages:
                self.app.controls_notebook.select(page)
                self.pump()
                for child in page.winfo_children():
                    if child.winfo_ismapped():
                        self.assertLessEqual(child.winfo_y() + child.winfo_height(),
                                             page.winfo_height())
        self.assertLess(sizes[0], sizes[-1])
        self.assertEqual(len(self.app.controls_notebook.tabs()), 4)
        # Native pages replace the scrolling canvas of child windows.
        self.assertFalse(any(w.winfo_class() == 'Canvas'
                             for w in self.app.ctrl_frame.winfo_children()))

    def test_resize_and_flip_keep_pieces_and_widgets(self):
        view = self.app.board_view
        self.app.board.push_uci('e2e4')
        self.app.update_board(force=True)
        before = self.app.board.fen()
        canvases = dict(view.canvases)
        view.resize(48)
        view.resize(84)
        self.assertEqual(view.canvases, canvases)
        self.assertEqual(len(view._scaled_images), 12)
        self.assertEqual(sum(item is not None for item in view.piece_items.values()), 32)
        view.flip_board()
        self.assertEqual(view._board.fen(), before)
        self.assertEqual(sum(item is not None for item in view.piece_items.values()), 32)
        self.assertEqual(self.app.board.fen(), before)

    def test_resized_clicks_and_theme_keep_position(self):
        self.root.geometry('1600x1000')
        self.pump()
        self.app.game_started = True
        view = self.app.board_view
        for square in (chess.E2, chess.E4):
            canvas = view.canvases[square]
            canvas.event_generate('<Button-1>', x=10, y=10)
            canvas.event_generate('<ButtonRelease-1>', x=10, y=10)
            self.pump()
        self.assertEqual(self.app.board.peek().uci(), 'e2e4')
        self.app.change_theme('dark')
        self.pump()
        self.assertEqual(view._board.fen(), self.app.board.fen())
        self.assertEqual(len(view.canvases), 64)
