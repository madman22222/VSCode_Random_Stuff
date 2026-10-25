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
from simple_ai import SimpleAI


@unittest.skipUnless(os.environ.get('DISPLAY') or os.name == 'nt',
                     'Needs a desktop display')
class TestResponsiveUI(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = tk.Tk()
        self.root.maxsize(2000, 1400)
        self.addCleanup(self.close_root)
        config = ConfigManager(str(Path(self.tmp.name) / 'config.json'))
        with patch('game_controller.ConfigManager', return_value=config):
            self.app = GameController(self.root)
        self.app.ai = SimpleAI(depth=1, learning_path=Path(self.tmp.name) / 'memory.json')
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
        self.assertEqual(len(self.app.controls_notebook.tabs()), 5)
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
        self.app.play_mode = 'player_vs_player'
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

    def wait_until(self, predicate, timeout=5):
        deadline = time.monotonic() + timeout
        while not predicate() and time.monotonic() < deadline:
            self.root.update()
            time.sleep(.01)
        self.assertTrue(predicate())

    def test_play_as_black_triggers_white_ai_opening(self):
        self.app.player_color_var.set('Black')
        self.app._choose_side()
        self.app.mode_var.set('player_vs_ai')
        self.app.change_mode()
        self.app.depth_var.set(1)
        self.app.gui_move_time_var.set(30)
        self.app.toggle_game_started()
        self.wait_until(lambda: len(self.app.board.move_stack) == 1)
        self.assertEqual(self.app.board.turn, chess.BLACK)
        self.assertTrue(self.app.board_view.flipped)
        self.assertFalse(self.app.ai_thinking)

    def test_undo_takes_back_ai_reply_and_removes_learning_log(self):
        self.app.play_mode = 'player_vs_ai'
        self.app.game_started = True
        self.app.board.push_uci('e2e4')
        self.app.ai._log_choice(self.app.board.board_fen(), 'e7e5', chess.BLACK)
        self.app.board.push_uci('e7e5')
        self.app.undo_move()
        self.assertEqual(self.app.board.fen(), chess.STARTING_FEN)
        self.assertEqual(self.app.ai.game_log, [])
        self.assertFalse(self.app.game_started)

    def test_cancelled_search_cannot_apply_stale_move(self):
        self.app._launch_ai_thread(1)
        self.app.new_game()
        self.pump()
        self.pump()
        self.assertEqual(self.app.board.fen(), chess.STARTING_FEN)
        self.assertEqual(self.app.ai.game_log, [])

    def test_watch_ai_starts_and_pause_prevents_more_moves(self):
        self.app.play_mode = 'ai_vs_ai'
        self.app.depth_var.set(1)
        self.app.gui_move_time_var.set(20)
        self.app.ai_delay_var.set(100)
        self.app.toggle_game_started()
        self.wait_until(lambda: bool(self.app.board.move_stack))
        self.app.toggle_game_started()
        count = len(self.app.board.move_stack)
        self.pump()
        self.pump()
        self.assertEqual(len(self.app.board.move_stack), count)

    def test_hint_does_not_move_or_record_learning(self):
        before = self.app.board.fen()
        self.app.request_hint()
        self.wait_until(lambda: not self.app._hint_thinking)
        self.assertIn('Suggestion:', self.app.feedback_var.get())
        self.assertEqual(self.app.board.fen(), before)
        self.assertEqual(self.app.ai.game_log, [])

    def test_training_dashboard_retains_final_progress_and_resumes(self):
        self.app.training_games_var.set(1)
        self.app.training_move_time_var.set(1)
        self.app.depth_var.set(1)
        self.app.start_training_ai()
        # Keep this GUI integration check short; normal training uses 300.
        self.app.training_ai.max_moves = 4
        self.wait_until(lambda: not self.app.training_ai.running)
        self.pump()
        self.assertIn('1 completed games', self.app.training_dashboard_var.get())
        self.assertTrue(self.app.ai.learning_db)
        self.app.start_training_ai(resume=True)
        self.app.training_ai.max_moves = 4
        self.wait_until(lambda: not self.app.training_ai.running)
        self.pump()
        self.assertIn('2 completed games', self.app.training_dashboard_var.get())

    def test_undo_finished_game_reverses_memory_update(self):
        for uci in ('f2f3', 'e7e5', 'g2g4'):
            self.app.board.push_uci(uci)
        key = self.app.board.board_fen()
        self.app.ai._log_choice(key, 'd8h4', chess.BLACK)
        self.app.board.push_uci('d8h4')
        self.app.update_board(force=True)
        self.assertTrue(self.app._learn_finalized)
        self.assertIn(key + '|d8h4', self.app.ai.learning_db)
        self.app.undo_move()
        self.assertNotIn(key + '|d8h4', self.app.ai.learning_db)
        self.assertFalse(self.app.board.is_game_over())
        self.assertEqual(self.app.config.get('statistics')['games_played'], 0)

    def test_nonstandard_position_renders_and_saves_pgn(self):
        import chess.pgn
        from unittest.mock import patch
        self.app.board = chess.Board('4k3/8/8/8/8/8/4P3/4K3 w - - 0 1')
        self.app.board.push_uci('e2e4')
        self.app.update_board(force=True)
        target = str(Path(self.tmp.name) / 'custom.pgn')
        with patch('game_controller.filedialog.asksaveasfilename', return_value=target), patch('game_controller.messagebox'):
            self.app.save_pgn()
        with open(target) as stream:
            game = chess.pgn.read_game(stream)
        loaded = game.end().board()
        self.assertEqual(loaded.fen(), self.app.board.fen())
