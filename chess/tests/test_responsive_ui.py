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

    def test_practice_keeps_real_game_and_learning_unchanged(self):
        import copy
        self.app.board.push_uci('e2e4')
        original = self.app.board.fen()
        self.app.update_board(force=True)
        stats = copy.deepcopy(self.app.config.get('statistics'))
        self.app.workspace.select(self.app.practice_workspace)
        self.pump()
        self.assertEqual(self.app._activity, 'practice')
        self.app.on_click(chess.G6)
        self.app.on_click(chess.G7)
        self.assertTrue(self.app.practice_done)
        self.assertEqual(self.app.config.get('statistics'), stats)
        self.assertEqual(self.app.ai.learning_db, {})
        self.assertIn('mate-white', self.app.config.get('practice_solved'))
        self.app.workspace.select(self.app.game_workspace)
        self.pump()
        self.assertEqual(self.app.board.fen(), original)
        self.assertFalse(self.app.game_started)

    def test_review_navigation_and_analysis_do_not_change_game(self):
        for uci in ('e2e4', 'e7e5', 'g1f3'):
            self.app.board.push_uci(uci)
        original = self.app.board.fen()
        self.app.update_board(force=True)
        self.app.workspace.select(self.app.review_workspace)
        self.pump()
        self.app._review_step(-2)
        self.assertEqual(len(self.app.board.move_stack), 1)
        self.app._save_session()
        self.assertEqual(self.app.session_store.load()['board'].fen(), original)
        self.app._analyze_review()
        self.wait_until(lambda: not self.app.review_runner.running, timeout=10)
        self.pump()
        self.assertEqual(len(self.app.review_runner.rows), 3)
        self.assertEqual(self.app.ai.game_log, [])
        self.app.workspace.select(self.app.game_workspace)
        self.pump()
        self.assertEqual(self.app.board.fen(), original)

    def test_keyboard_selection_and_piece_render_cache(self):
        self.app.play_mode = 'player_vs_player'
        self.app.game_started = True
        self.root.focus_force()
        self.app.board_view.focus(chess.E2)
        self.pump()
        ids = dict(self.app.board_view.piece_items)
        self.app.update_board(force=True)
        self.assertEqual(self.app.board_view.piece_items, ids)
        for key in ('Return', 'Up', 'Return'):
            focused = self.root.focus_get()
            focused.event_generate('<KeyPress>', keysym=key)
            self.pump()
        self.assertEqual(self.app.board.peek().uci(), 'e2e3')
        self.assertEqual(self.app.board_view.piece_items[chess.A1], ids[chess.A1])

    def test_accessibility_modes_preserve_position_and_are_persisted(self):
        before = self.app.board.fen()
        self.app.text_size_var.set('Large')
        self.app.contrast_var.set(True)
        self.app.piece_style_var.set('Letters')
        self.app._apply_accessibility()
        self.pump()
        self.assertEqual(self.app.board.fen(), before)
        self.assertTrue(self.app.board_view.high_contrast)
        self.assertEqual(self.app.board_view.piece_style, 'Letters')
        self.assertEqual(sum(item is not None for item in self.app.board_view.piece_items.values()), 32)
        self.assertEqual(self.app.config.get('text_size'), 'Large')
        self.assertTrue(self.app.config.get('high_contrast'))

    def test_automatic_restore_pauses_clock_and_recovers_game(self):
        self.app.player_color_var.set('Black')
        self.app.board.push_uci('e2e4')
        self.app.clock.white_time = 123.4
        self.app.clock.black_time = 99.2
        self.app.clock_enabled = True
        self.app._save_session()
        other = tk.Tk()
        try:
            with patch('game_controller.ConfigManager', return_value=self.app.config):
                restored = GameController(other)
            other.update()
            self.assertEqual(restored.board.fen(), self.app.board.fen())
            self.assertEqual(restored.player_color_var.get(), 'Black')
            self.assertAlmostEqual(restored.clock.white_time, 123.4)
            self.assertFalse(restored.clock.running)
            self.assertFalse(restored.game_started)
            self.assertIn('restored', restored.feedback_var.get())
        finally:
            for job in other.tk.call('after', 'info'):
                other.after_cancel(job)
            other.destroy()

    def test_experimental_scoring_cannot_be_enabled_without_evidence(self):
        self.app._approve_outcome_scoring()
        self.assertFalse(self.app.ai.use_outcome_scoring)
        self.assertIn('Not enabled', self.app.benchmark_var.get())

    def test_large_text_keeps_tab_panels_visible_at_small_window(self):
        self.root.geometry('980x720')
        self.app.text_size_var.set('Large')
        self.app._apply_accessibility()
        self.pump()
        for page in self.app.control_pages:
            self.app.controls_notebook.select(page)
            self.pump()
            for child in page.winfo_children():
                if child.winfo_manager() == 'pack':
                    self.assertTrue(child.winfo_ismapped(), child.winfo_class())
                    self.assertLessEqual(child.winfo_y() + child.winfo_height(), page.winfo_height())

    def test_focus_is_safe_across_flip_resize_and_theme(self):
        from unittest.mock import Mock
        self.root.report_callback_exception = Mock()
        self.root.focus_force()
        view = self.app.board_view
        view.focus(chess.E2)
        self.pump()
        view.flip_board()
        self.pump()
        view.focus(chess.E2)
        view.resize(64)
        self.pump()
        view.set_theme('dark')
        self.pump()
        view.focus(chess.E2)
        self.pump()
        self.assertEqual(len(view.canvases), 64)
        self.root.report_callback_exception.assert_not_called()

    def test_fen_study_preserves_live_game_and_recovery(self):
        self.app.board.push_uci('e2e4')
        self.app.update_board(force=True)
        before = self.app.board.fen()
        with patch('studio_tools.simpledialog.askstring', return_value='7k/8/5KQ1/8/8/8/8/8 w - - 0 1'):
            self.app._study_fen()
        self.pump()
        self.assertEqual(self.app._activity, 'review')
        self.assertNotEqual(self.app.board.fen(), before)
        self.app._save_session()
        self.assertEqual(self.app.session_store.load()['board'].fen(), before)
        self.app._return_to_game()
        self.assertEqual(self.app.board.fen(), before)

    def test_learning_import_failure_keeps_live_and_saved_memory(self):
        path = Path(self.tmp.name) / 'import.json'
        path.write_text('{"position|e2e4": {"w": 2, "l": 0, "d": 0}}')
        before = dict(self.app.ai.learning_db)
        with patch('game_controller.filedialog.askopenfilename', return_value=str(path)), \
             patch.object(self.app.ai, '_save_learning_db', side_effect=OSError('disk full')), \
             patch('studio_tools.messagebox.showerror') as error:
            self.app.import_learning()
        self.assertEqual(self.app.ai.learning_db, before)
        error.assert_called_once()

    def test_named_profile_switch_starts_paused_without_old_game_log(self):
        self.app.ai.game_log = [('position', 'e2e4', True)]
        with patch('studio_tools.simpledialog.askstring', return_value='experiment'), \
             patch('studio_tools.messagebox.askyesno', return_value=True):
            self.app._select_profile()
        self.assertEqual(Path(self.app.ai._learning_path).parts[-3:], ('profiles', 'experiment', 'ai_learn.json'))
        self.assertEqual(self.app.ai.game_log, [])
        self.assertFalse(self.app.game_started)
        self.assertEqual(self.app.config.get('learning_profile'), 'experiment')

    def test_underpromotion_en_passant_and_castling_restrictions_in_gui(self):
        self.app.play_mode = 'player_vs_player'
        self.app.game_started = True
        self.app.board = chess.Board('7k/P7/8/8/8/8/8/7K w - - 0 1')
        self.app.update_board(force=True)
        with patch.object(self.app, 'ask_promotion', return_value=chess.KNIGHT):
            self.app.on_click(chess.A7)
            self.app.on_click(chess.A8)
        self.assertEqual(self.app.board.piece_at(chess.A8).piece_type, chess.KNIGHT)
        self.app.new_game()
        self.app.play_mode = 'player_vs_player'
        self.app.game_started = True
        self.app.board = chess.Board('k3r3/8/8/3pP3/8/8/8/4K3 w - d6 0 1')
        self.app.update_board(force=True)
        before = self.app.board.fen()
        self.app.on_click(chess.E5)
        self.app.on_click(chess.D6)
        self.assertEqual(self.app.board.fen(), before, 'En passant must not expose own king')
        self.assertNotIn(chess.Move.from_uci('e1g1'), self.app.board.legal_moves)

    def test_modal_maintenance_prevents_play_training_and_close(self):
        self.app.board.push_uci('e2e4')
        self.app._save_session()
        original = self.app.session_store.path.read_bytes()
        self.app._tools_busy = True
        self.app.board.push_uci('e7e5')
        self.app._save_session()
        self.assertEqual(self.app.session_store.path.read_bytes(), original)
        self.app.game_started = False
        self.app.toggle_game_started()
        self.app.start_training_ai()
        self.app.start_benchmark()
        self.app.on_close()
        self.assertTrue(self.root.winfo_exists())
        self.assertFalse(self.app.game_started)
        self.assertIsNone(self.app.training_ai)
        self.assertIsNone(self.app.benchmark)
        self.app._tools_busy = False

    def test_repetition_draw_survives_session_roundtrip(self):
        self.app.board = chess.Board()
        for uci in ('g1f3','g8f6','f3g1','f6g8') * 2:
            self.app.board.push_uci(uci)
        self.assertTrue(self.app.board.can_claim_threefold_repetition())
        self.app.update_board(force=True)
        self.app._save_session()
        self.assertFalse(self.app.session_store.path.exists(), 'Finished draw clears recovery slot')

    def test_puzzle_pack_import_persists_and_underpromotion_is_selectable(self):
        path = Path(__file__).resolve().parents[1] / 'assets' / 'puzzles' / 'studio-extras.json'
        with patch('studio_tools.filedialog.askopenfilename', return_value=str(path)):
            self.app._import_puzzle_pack()
        self.assertEqual(len(self.app.puzzles), 11)
        self.assertTrue((Path(self.tmp.name) / 'puzzle-packs' / 'studio-extras.json').exists())
        self.app.workspace.select(self.app.practice_workspace)
        self.pump()
        self.app.practice_index = next(i for i,p in enumerate(self.app.puzzles) if p.id.endswith(':knight-promotion'))
        self.app._load_practice()
        with patch.object(self.app, 'ask_promotion', return_value=chess.KNIGHT):
            self.app._practice_click(chess.A7)
            self.app._practice_click(chess.A8)
        self.assertTrue(self.app.practice_done)
