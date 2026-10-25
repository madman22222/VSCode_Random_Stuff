"""Training/evaluation contracts using isolated temporary learning files."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import chess
from simple_ai import SimpleAI
from training_ai import TrainingAI, BenchmarkRunner, starting_board
from chess_coach import describe_move, illegal_move_message
import random


class TestTrainingWorkflows(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'memory.json'
        self.ai = SimpleAI(depth=1, learning_path=self.path)

    def finish(self, worker):
        worker.start()
        worker.thread.join(15)
        self.assertFalse(worker.thread.is_alive())
        self.assertIsNone(worker.last_error)

    def test_resume_adds_games_and_restores_saved_settings(self):
        first = TrainingAI(self.ai, depth=1, max_games=2, max_moves=4,
                           move_time_limit=.005, exploration_rate=1, seed=7)
        self.finish(first)
        second = TrainingAI(SimpleAI(learning_path=self.path), depth=4, max_games=1,
                            max_moves=4, resume=True)
        self.assertEqual(second.games_played, 2)
        self.assertEqual(second.depth, 1)
        self.assertEqual(second.seed, 7)
        self.assertEqual(second.exploration_rate, 1)
        self.finish(second)
        self.assertEqual(second.games_played, 3)
        self.assertEqual(sum(second.results.values()), 3)
        data = json.loads(Path(second.state_path).read_text())
        self.assertEqual(data['games'], 3)
        self.assertEqual(data['state'], 'completed')
        self.assertGreaterEqual(data['elapsed_seconds'], first.snapshot()['elapsed_seconds'])

    def test_exploration_is_legal_and_logged(self):
        trainer = TrainingAI(self.ai, max_games=1, max_moves=8, exploration_rate=1,
                             move_time_limit=.001)
        with patch.object(self.ai, 'choose_move_iterative', side_effect=AssertionError('No search needed')):
            self.finish(trainer)
        self.assertTrue(self.ai.learning_db)
        self.assertEqual(trainer.move_limit_draws, 1)
        self.assertEqual(sum(record['d'] for record in self.ai.learning_db.values()), 8)

    def test_opening_generation_is_varied_valid_and_seeded(self):
        rng = random.Random(5)
        boards = [starting_board(rng) for _ in range(15)]
        self.assertGreater(len({board.fen() for board in boards}), 5)
        self.assertTrue(all(board.is_valid() and 2 <= len(board.move_stack) <= 6 for board in boards))
        self.assertEqual(starting_board(random.Random(8)).fen(), starting_board(random.Random(8)).fen())
        self.assertEqual(starting_board(rng, False).fen(), chess.STARTING_FEN)

    def test_node_budget_and_nonrecording_search(self):
        board = chess.Board()
        self.ai.depth = 6
        before = board.fen()
        move = self.ai.choose_move_iterative(board, 5, record=False, node_limit=20)
        self.assertIn(move, board.legal_moves)
        self.assertEqual(board.fen(), before)
        self.assertLessEqual(self.ai.nodes_searched, 20)
        self.assertEqual(self.ai.game_log, [])

    def test_fork_copies_memory_without_sharing_mutable_records(self):
        self.ai.learning_db['position|e2e4'] = {'w': 2, 'l': 0, 'd': 0}
        clone = self.ai.fork()
        clone.learning_db['position|e2e4']['w'] = 99
        self.assertEqual(self.ai.learning_db['position|e2e4']['w'], 2)
        baseline = self.ai.fork(learning=False)
        self.assertFalse(baseline.use_learning)
        self.assertEqual(baseline.learning_db, {})

    def test_paired_baseline_is_repeatable_and_does_not_train(self):
        before = copy.deepcopy(self.ai.learning_db)
        result = []
        for _ in range(2):
            runner = BenchmarkRunner(self.ai, games=2, depth=2, node_limit=30, max_moves=6)
            self.finish(runner)
            result.append(copy.deepcopy(runner.result))
        self.assertEqual(result[0], result[1])
        self.assertEqual(result[0]['completed'], 2)
        self.assertEqual(result[0]['score_percent'], 50)
        self.assertEqual(self.ai.learning_db, before)
        self.assertEqual(self.ai.game_log, [])
        self.assertFalse(self.path.exists())
        self.assertFalse(Path(str(self.path) + '.gz').exists())
        self.assertTrue(Path(runner.result_path).exists())

    def test_comparison_rejects_unpaired_games(self):
        with self.assertRaises(ValueError):
            BenchmarkRunner(self.ai, games=3)

    def test_save_failure_is_visible(self):
        trainer = TrainingAI(self.ai, max_games=1, max_moves=2, exploration_rate=1)
        with patch.object(self.ai, '_save_learning_db', side_effect=OSError('disk full')):
            trainer.start()
            trainer.thread.join(5)
        self.assertIsInstance(trainer.last_error, OSError)
        self.assertEqual(trainer.state, 'error')
        self.assertFalse(trainer.running)

    def test_hint_and_illegal_move_explanations_are_factual(self):
        board = chess.Board()
        self.assertIn('Nf3', describe_move(board, chess.Move.from_uci('g1f3')))
        self.assertIn('cannot move there', illegal_move_message(board, chess.Move.from_uci('e2e5')))
        board = chess.Board('4r1k1/8/8/8/8/8/4R3/4K3 w - - 0 1')
        self.assertIn('king in check', illegal_move_message(board, chess.Move.from_uci('e2d2')))

    def test_writer_lease_rejects_competing_saves_and_releases(self):
        self.ai.acquire_writer()
        competitor = SimpleAI(learning_path=self.path)
        try:
            with self.assertRaisesRegex(RuntimeError, 'already in use'):
                competitor._save_learning_db()
        finally:
            self.ai.release_writer()
        competitor._save_learning_db()
        self.assertTrue(Path(str(self.path) + '.gz').exists())
