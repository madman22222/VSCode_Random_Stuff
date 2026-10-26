"""Exact evaluation/search semantics, bounded caches, and optimized training persistence."""
import copy
import gzip
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch
import chess
from simple_ai import SimpleAI
from training_ai import TrainingAI


def reference_pawns(ai, board, color):
    score = 0
    pawns = board.pieces(chess.PAWN, color)
    for square in pawns:
        file, rank = chess.square_file(square), chess.square_rank(square)
        if ai.is_passed_pawn(board, square, color):
            score += 20 + (rank if color else 7 - rank) * 10
        if sum(chess.square_file(other) == file for other in pawns) > 1:
            score -= 15
        if ai.is_isolated_pawn(board, square, color):
            score -= 20
        if ai.is_backward_pawn(board, square, color):
            score -= 10
    return score


class TestTrainingOptimization(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'memory.json'
        self.ai = SimpleAI(depth=2, learning_path=self.path)

    def finish(self, worker):
        worker.start(); worker.thread.join(15)
        self.assertFalse(worker.running)
        self.assertIsNone(worker.last_error)

    def test_pawn_masks_match_reference_for_seeded_positions_and_both_colors(self):
        rng = random.Random(449)
        board = chess.Board()
        for _ in range(300):
            if board.is_game_over(claim_draw=True):
                board = chess.Board()
            for color in chess.COLORS:
                self.assertEqual(self.ai.evaluate_pawn_structure(board, color),
                                 reference_pawns(self.ai, board, color), board.fen())
            board.push(rng.choice(list(board.legal_moves)))

    def test_cache_separates_phase_rights_ep_and_is_bounded(self):
        self.ai.evaluation_cache_limit = 4
        board = chess.Board()
        for _ in range(5):
            board.push_uci('g1f3'); board.push_uci('g8f6')
            board.push_uci('f3g1'); board.push_uci('f6g8')
        variants = [board.root(), board, chess.Board('r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1'),
                    chess.Board('r3k2r/8/8/8/8/8/8/R3K2R w - - 0 1'),
                    chess.Board('7k/8/8/3pP3/8/8/8/K7 w - d6 0 1'),
                    chess.Board('7k/8/8/3pP3/8/8/8/K7 w - - 0 1')]
        for position in variants:
            expected = self.ai.evaluate(position)
            self.assertEqual(self.ai._evaluate_cached(position), expected)
            self.assertEqual(self.ai._evaluate_cached(position), expected)
            self.assertLessEqual(len(self.ai._evaluation_cache), 4)
        self.ai.choose_move_iterative(chess.Board(), 1, record=False, node_limit=20)
        self.assertLessEqual(len(self.ai._evaluation_cache), 4)

    def test_cached_and_uncached_search_have_identical_metrics_and_keep_history(self):
        board = chess.Board()
        for move in ('g1f3', 'g8f6', 'f3g1', 'f6g8', 'g1f3', 'g8f6'):
            board.push_uci(move)
        before = board.fen(), list(board.move_stack)
        metrics = []
        for limit in (0, 4096):
            ai = SimpleAI(depth=3, learning_path=self.path)
            ai.evaluation_cache_limit = limit
            ai.choose_move_iterative(board, 10, record=False, node_limit=300)
            metrics.append({k: ai.last_move_metrics[k] for k in ('move', 'depth', 'nodes', 'score_cp')})
        self.assertEqual(metrics[0], metrics[1])
        self.assertEqual((board.fen(), board.move_stack), before)

    def test_fast_compression_and_single_write_retain_every_learning_record(self):
        self.ai.learning_db = {f'position-{n}|e2e4': {'w': n, 'l': 1, 'd': 2} for n in range(300)}
        self.ai._save_learning_db()
        self.assertEqual(SimpleAI(learning_path=self.path).learning_db, self.ai.learning_db)
        self.ai.compress_learning = False
        self.ai._save_learning_db()
        self.assertFalse(Path(str(self.path) + '.gz').exists())
        self.assertEqual(SimpleAI(learning_path=self.path).learning_db, self.ai.learning_db)

    def test_position_index_handles_duplicate_positions_pruning_and_resume(self):
        self.ai.learning_max_entries = 2
        self.ai.learning_min_keep = 1
        self.ai._last_prune_time = 0
        worker = TrainingAI(self.ai, depth=1, batch_size=2, max_games=3,
                            max_moves=4, move_time_limit=.001, exploration_rate=1)
        self.finish(worker)
        actual = len({key.split('|', 1)[0] for key in self.ai.learning_db})
        self.assertEqual(worker.snapshot()['positions'], actual)
        resumed = TrainingAI(SimpleAI(learning_path=self.path), max_games=1, max_moves=2, resume=True)
        self.finish(resumed)
        self.assertEqual(resumed.snapshot()['positions'],
                         len({key.split('|', 1)[0] for key in resumed.ai.learning_db}))

    def test_published_fingerprint_is_reused_only_while_writer_is_owned(self):
        from training_journal import disk_records
        worker = TrainingAI(self.ai, depth=1, max_games=3, max_moves=2,
                            exploration_rate=1, batch_size=1)
        with patch('training_journal.disk_records', wraps=disk_records) as reads:
            self.finish(worker)
            self.assertEqual(reads.call_count, 1)
        external = SimpleAI(learning_path=self.path)
        external.learning_db['external|e2e4'] = {'w': 1, 'l': 0, 'd': 0}
        external._save_learning_db()
        with patch('training_journal.disk_records', wraps=disk_records) as reads:
            worker._checkpoint()
            self.assertEqual(reads.call_count, 1)

    def test_failed_atomic_serialization_preserves_previous_file(self):
        from training_ai import atomic_json
        path = Path(self.temp.name) / 'state.json'
        atomic_json(path, {'safe': True})
        original = path.read_bytes()
        with self.assertRaises(TypeError):
            atomic_json(path, {'bad': object()})
        self.assertEqual(path.read_bytes(), original)

    def test_terminal_reuse_and_custom_evaluator_keep_public_contract(self):
        mate = chess.Board('k7/1Q6/2K5/8/8/8/8/8 b - - 0 1')
        self.assertEqual(self.ai.evaluate(mate), -9999999)
        normal = chess.Board()
        self.assertEqual(self.ai.evaluate(normal), self.ai.evaluate(normal, _terminal_checked=True))
        self.ai.evaluate = lambda board: 123
        self.ai._evaluation_cache.clear()
        self.assertEqual(self.ai._evaluate_cached(normal, _terminal_checked=True), 123)

    def test_pawn_cache_is_exact_after_pawn_moves_and_remains_bounded(self):
        self.ai.pawn_cache_limit = 2
        board = chess.Board()
        for uci in ('e2e4', 'd7d5', 'e4d5', 'e7e6'):
            board.push_uci(uci)
            for color in chess.COLORS:
                self.assertEqual(self.ai.evaluate_pawn_structure(board, color),
                                 reference_pawns(self.ai, board, color))
                self.assertLessEqual(len(self.ai._pawn_cache), 2)

    def test_masked_quiescence_keeps_capture_promotion_ep_and_evasion_order(self):
        rng = random.Random(713)
        board = chess.Board()
        positions = [chess.Board('7k/P7/8/8/8/8/7p/K7 w - - 0 1'),
                     chess.Board('7k/P7/8/8/8/8/7p/K7 b - - 0 1'),
                     chess.Board('7k/8/8/3pP3/8/8/8/K7 w - d6 0 1'),
                     chess.Board('4r1k1/8/8/8/8/8/3B4/4K3 w - - 0 1')]
        for _ in range(300):
            if board.is_game_over(claim_draw=True): board = chess.Board()
            positions.append(board.copy())
            board.push(rng.choice(list(board.legal_moves)))
        for position in positions:
            check = position.is_check()
            expected = [m for m in position.legal_moves if check or position.is_capture(m) or m.promotion]
            self.assertEqual(self.ai._quiescence_moves(position, check), expected, position.fen())
