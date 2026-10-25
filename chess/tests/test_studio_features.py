"""Behavioral coverage for tactics, experiments, session recovery and review."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import chess
from chess_clock import ChessClock
from game_review import ReviewRunner
from session_store import SessionStore
from simple_ai import SimpleAI
from tactical_suite import PUZZLES, run_suite
from training_ai import TrainingAI, ComparisonSeries, paired_interval


class TestStudioFeatures(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'learn.json'
        self.ai = SimpleAI(depth=2, learning_path=self.path)

    def test_tactical_cases_are_valid_and_engine_solves_them(self):
        for puzzle in PUZZLES:
            self.assertTrue(chess.Board(puzzle.fen).is_valid(), puzzle.id)
        result = run_suite(self.ai)
        self.assertEqual(result['passed'], result['total'], result['positions'])
        self.assertEqual(self.ai.game_log, [])
        self.ai.use_outcome_scoring = True
        result = run_suite(self.ai)
        self.assertEqual(result['passed'], result['total'])

    def test_scoring_is_smoothed_bounded_and_off_by_default(self):
        board = chess.Board()
        key = board.board_fen()
        self.ai.learning_db[key + '|e2e4'] = {'w': 1000, 'l': 0, 'd': 0}
        self.assertEqual(self.ai.outcome_adjustment(key, 'e2e4'), 0)
        self.ai.use_outcome_scoring = True
        self.assertLessEqual(self.ai.outcome_adjustment(key, 'e2e4'), 25)
        self.assertGreater(self.ai.outcome_adjustment(key, 'e2e4'), 0)
        self.ai.learning_db[key + '|e2e4'] = {'w': 4, 'l': 0, 'd': 0}
        self.assertEqual(self.ai.outcome_adjustment(key, 'e2e4'), 0)
        self.ai.learning_db[key + '|e2e4'] = {'w': 0, 'l': 50, 'd': 0}
        self.assertLess(self.ai.outcome_adjustment(key, 'e2e4'), 0)

    def test_prior_does_not_override_a_queen_loss(self):
        board = chess.Board(next(p.fen for p in PUZZLES if p.id == 'save-queen'))
        self.ai.learning_db[board.board_fen() + '|g1h2'] = {'w': 100000, 'l': 0, 'd': 0}
        self.ai.use_outcome_scoring = True
        move = self.ai.choose_move_iterative(board, 3, record=False, node_limit=10000)
        puzzle = next(p for p in PUZZLES if p.id == 'save-queen')
        self.assertTrue(puzzle.accepts(board, move))

    def test_previous_snapshot_and_new_training_reset_scoring(self):
        self.ai.learning_db['test|a1a2'] = {'w': 10, 'l': 0, 'd': 0}
        self.ai.use_outcome_scoring = True
        trainer = TrainingAI(self.ai, max_games=1, max_moves=2, exploration_rate=1)
        trainer.start()
        trainer.thread.join(10)
        self.assertIsNone(trainer.last_error)
        previous = json.loads(Path(str(self.path) + '.previous.json').read_text())
        self.assertTrue(previous['meta']['outcome_scoring'])
        self.assertEqual(previous['data']['test|a1a2']['w'], 10)
        self.assertFalse(self.ai.use_outcome_scoring)

    def test_series_compares_both_versions_and_rejects_tiny_sample(self):
        previous_path = Path(str(self.path) + '.previous.json')
        previous_path.write_text(json.dumps({'meta': {'version': 2}, 'data': {}}))
        before = copy.deepcopy(self.ai.learning_db)
        series = ComparisonSeries(self.ai, games=2, depth=1, node_limit=20,
                                  max_moves=4, experimental=True)
        series.start()
        series.thread.join(15)
        self.assertFalse(series.running)
        self.assertIsNone(series.last_error)
        self.assertEqual([r['opponent'] for r in series.reports], ['untrained', 'previous'])
        self.assertTrue(all(r['completed'] == 2 for r in series.reports))
        self.assertFalse(series.eligible)
        self.assertEqual(self.ai.learning_db, before)
        self.assertFalse(self.ai.use_outcome_scoring)
        self.assertTrue(all(r['tactics']['candidate']['passed'] == len(PUZZLES) for r in series.reports))

    def test_uncertainty_accounts_for_pairs_and_small_samples(self):
        self.assertEqual(paired_interval([]), [0, 100])
        lo, hi = paired_interval([1])
        self.assertLess(lo, 50)
        self.assertEqual(hi, 100)
        lo, hi = paired_interval([1] * 100)
        self.assertGreater(lo, 50)
        self.assertEqual(hi, 100)
        lo, hi = paired_interval([.5] * 100)
        self.assertLess(lo, 50)
        self.assertGreater(hi, 50)

    def test_session_round_trip_preserves_history_clock_and_side(self):
        board = chess.Board()
        log = []
        for uci in ('e2e4', 'a7a6', 'e4e5', 'd7d5'):
            log.append((board.board_fen(), uci, board.turn))
            board.push_uci(uci)
        store = SessionStore(Path(self.tmp.name) / 'session.json')
        clock = {'white': 123.4, 'black': 99.2, 'increment': 2, 'enabled': True}
        store.save(board, 'player_vs_ai', 'Black', clock, log, True)
        loaded = store.load()
        self.assertEqual(loaded['board'].fen(), board.fen())
        self.assertEqual(loaded['board'].move_stack, board.move_stack)
        self.assertEqual(loaded['clock'], clock)
        self.assertEqual(loaded['side'], 'Black')
        self.assertEqual(loaded['log'], log)
        self.assertTrue(loaded['board'].has_legal_en_passant())

    def test_session_rejects_illegal_history_and_invalid_clock(self):
        store = SessionStore(Path(self.tmp.name) / 'session.json')
        store.save(chess.Board(), 'player_vs_ai', 'White', {}, [])
        data = json.loads(store.path.read_text())
        data['moves'] = ['e2e5']
        store.path.write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            store.load()
        data['moves'] = []
        data['clock'] = {'white': float('nan')}
        store.path.write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            store.load()

    def test_review_finds_missed_queen_without_training(self):
        board = chess.Board(next(p.fen for p in PUZZLES if p.id == 'free-queen'))
        board.push_uci('e4e5')
        before = board.fen()
        runner = ReviewRunner(board, self.ai, depth=2, nodes=5000)
        runner.start()
        runner.thread.join(10)
        self.assertFalse(runner.running)
        self.assertIsNone(runner.last_error)
        self.assertEqual(len(runner.rows), 1)
        row = runner.rows[0]
        self.assertEqual(row['suggested'], 'exd5')
        self.assertGreaterEqual(row['estimated_loss_cp'], 150)
        self.assertIn('Possible mistake', row['note'])
        self.assertEqual(board.fen(), before)
        self.assertEqual(self.ai.game_log, [])
        self.assertEqual(self.ai.learning_db, {})

    def test_clock_settles_partial_ticks_and_cancels_previous_timer(self):
        clock = ChessClock(increment=2)
        root = Mock()
        root.after.return_value = 'timer'
        with patch('chess_clock.time.monotonic', return_value=0) as now:
            clock.start(root)
            now.return_value = .9
            clock.stop()
            self.assertAlmostEqual(clock.white_time, 599.1)
            now.return_value = 2
            clock.start(root)
            now.return_value = 2.15
            clock.switch()
            self.assertAlmostEqual(clock.white_time, 600.95)
            now.return_value = 3.15
            clock.stop()
            self.assertAlmostEqual(clock.black_time, 599)
        self.assertGreaterEqual(root.after_cancel.call_count, 2)
