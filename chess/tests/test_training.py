"""Regression tests for bounded search and real self-play persistence."""
import gzip
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import chess
from simple_ai import SimpleAI
from training_ai import TrainingAI


class TestTraining(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'learn.json'
        self.ai = SimpleAI(depth=2, learning_path=self.path)

    def test_search_preserves_board_and_depth_when_timed_out(self):
        board = chess.Board()
        board.push_uci('e2e4')
        before = board.fen(), list(board.move_stack)
        self.ai.depth = 8
        start = time.monotonic()
        move = self.ai.choose_move_iterative(board, 0.02)
        self.assertIn(move, board.legal_moves)
        self.assertLess(time.monotonic() - start, 1.0)
        self.assertEqual((board.fen(), board.move_stack), before)
        self.assertEqual(self.ai.depth, 8)
        self.assertEqual(len(self.ai.game_log), 1)

    def test_tables_and_mate_score_for_both_colors(self):
        for name in ('PAWN', 'KNIGHT', 'BISHOP', 'ROOK', 'QUEEN',
                     'KING_MIDDLEGAME', 'KING_ENDGAME'):
            self.assertEqual(len(getattr(self.ai, name + '_TABLE')), 64)
        board = chess.Board('k7/1Q6/2K5/8/8/8/8/8 b - - 0 1')
        self.assertLess(self.ai.evaluate(board), 0)
        self.assertLess(self.ai.evaluate(board.mirror()), 0)

    def test_training_completes_exact_count_and_reloads(self):
        trainer = TrainingAI(self.ai, depth=1, batch_size=2,
                             move_time_limit=0.005, max_games=2, max_moves=6)
        trainer.start()
        trainer.thread.join(timeout=10)
        self.assertFalse(trainer.thread.is_alive())
        self.assertIsNone(trainer.last_error)
        self.assertEqual(trainer.games_played, 2)
        self.assertEqual(sum(trainer.results.values()), 2)
        self.assertTrue(self.ai.learning_db)
        reloaded = SimpleAI(learning_path=self.path)
        self.assertEqual(reloaded.learning_db, self.ai.learning_db)
        self.assertFalse(self.ai.defer_persistence)
        # Switching format must not reload an older compressed snapshot.
        reloaded.compress_learning = False
        reloaded.learning_db['test|e2e4'] = {'w': 1, 'l': 0, 'd': 0}
        reloaded._save_learning_db()
        self.assertFalse(Path(str(self.path) + '.gz').exists())
        self.assertEqual(SimpleAI(learning_path=self.path).learning_db,
                         reloaded.learning_db)

    def test_stop_joins_worker_and_discards_unfinished_game(self):
        trainer = TrainingAI(self.ai, move_time_limit=0.01)
        trainer.start()
        trainer.stop()
        self.assertFalse(trainer.thread.is_alive())
        self.assertFalse(trainer.running)
        self.assertEqual(self.ai.game_log, [])

    def test_worker_failure_is_reported(self):
        trainer = TrainingAI(self.ai, max_games=1)
        with patch.object(self.ai, 'choose_move_iterative', side_effect=RuntimeError('broken')):
            trainer.start()
            trainer.thread.join(timeout=5)
        self.assertIsInstance(trainer.last_error, RuntimeError)
        self.assertFalse(trainer.running)

    def test_headless_cli_without_display(self):
        env = dict(os.environ)
        env.pop('DISPLAY', None)
        command = [sys.executable, str(Path(__file__).resolve().parents[1] / 'main.py'),
                   '--training', '--games', '1', '--depth', '1', '--max-plies', '4',
                   '--move-ms', '5', '--learning-file', str(self.path)]
        completed = subprocess.run(command, env=env, capture_output=True, text=True, timeout=10)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        with gzip.open(str(self.path) + '.gz', 'rt') as stream:
            self.assertTrue(json.load(stream)['data'])
        self.assertIn('1 games', completed.stdout)
