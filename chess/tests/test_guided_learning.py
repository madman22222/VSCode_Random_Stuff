"""Validate authored branches, isolation, held-out roots and interrupted saves."""
import copy
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch
import chess
from curriculum import course_puzzles, LESSONS, lesson_status
from practice_model import PuzzleSession, validate_lines
from evaluation_corpus import load_corpus
from game_review import ReviewRunner, annotated_pgn
from simple_ai import SimpleAI
from training_ai import TrainingAI, ComparisonSeries, OPENINGS
from training_journal import fingerprint


class TestGuidedLearning(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'ai_learn.json'
        self.ai = SimpleAI(depth=1, learning_path=self.path)

    def finish(self, worker):
        worker.start()
        worker.thread.join(15)
        self.assertFalse(worker.thread.is_alive())
        self.assertIsNone(worker.last_error)

    def test_all_authored_lines_and_opponent_branches_complete(self):
        for puzzle in course_puzzles():
            self.assertEqual(validate_lines(chess.Board(puzzle.fen), [list(x) for x in puzzle.lines], puzzle.goal), puzzle.lines)
            for variant in range(len(puzzle.lines)):
                session = PuzzleSession(puzzle, variant)
                while not session.done:
                    line = next(x for x in puzzle.lines if x[:len(session.prefix)] == session.prefix)
                    result = session.attempt(chess.Move.from_uci(line[len(session.prefix)]))
                    self.assertTrue(result['accepted'], puzzle.id)
                self.assertTrue(session.done)
        self.assertEqual(self.ai.learning_db, {})
        self.assertFalse(self.path.exists())

    def test_wrong_move_preserves_position_and_explains_without_false_verdict(self):
        puzzle = next(p for p in course_puzzles() if p.id == 'guided:fork')
        session = PuzzleSession(puzzle)
        before = session.board.fen()
        result = session.attempt(chess.Move.from_uci('g1h1'))
        self.assertFalse(result['accepted'])
        self.assertIn('Legal, but outside', result['message'])
        self.assertNotIn('blunder', result['message'].lower())
        self.assertEqual(session.board.fen(), before)
        self.assertEqual(session.prefix, ())

    def test_alternative_mate_is_accepted_and_lesson_counts_are_idempotent(self):
        puzzle = next(p for p in course_puzzles() if p.id == 'guided:queen-mate')
        session = PuzzleSession(puzzle)
        session.attempt(chess.Move.from_uci('f6g6'))
        mate = next(m for m in session.board.legal_moves if self.mates(session.board, m))
        self.assertTrue(session.attempt(mate)['completed'])
        self.assertEqual(lesson_status(LESSONS[2], [puzzle.id, puzzle.id]), (1, 1))

    @staticmethod
    def mates(board, move):
        probe = board.copy(); probe.push(move)
        return probe.is_checkmate()

    def test_malformed_lines_are_rejected(self):
        for lines in ([['e2e5']], [['e2e4', 'e7e5']], [['e2e4'], ['e2e4']], [['e2e4'], ['e2e4', 'e7e5', 'g1f3']]):
            with self.assertRaises(ValueError):
                validate_lines(chess.Board(), lines, 'line')
        with self.assertRaises(ValueError):
            validate_lines(chess.Board(), [['e2e4']], 'mate')

    def test_evaluation_roots_are_disjoint_from_every_training_seed_prefix(self):
        positions, meta = load_corpus(self.ai)
        from learning_keys import position_key
        training = set()
        for line in OPENINGS:
            board = chess.Board()
            for move in line.split():
                board.push_uci(move)
                training.add(position_key(board))
        self.assertEqual(len(positions), 16)
        self.assertFalse(training & {position_key(chess.Board(p['fen'])) for p in positions})
        self.assertEqual(meta['remembered_roots'], 0)
        board = chess.Board(positions[0]['fen'])
        self.ai.learning_db[position_key(board) + '|' + next(iter(board.legal_moves)).uci()] = {'w': 1, 'l': 0, 'd': 0}
        self.assertEqual(load_corpus(self.ai)[1]['remembered_roots'], 1)
        series = ComparisonSeries(self.ai, games=2, depth=1, node_limit=10, max_moves=2, against='untrained')
        self.finish(series)
        report = series.reports[0]
        ledger = report['games_ledger']
        self.assertEqual(ledger[0]['position'], ledger[1]['position'])
        self.assertNotEqual(ledger[0]['candidate_color'], ledger[1]['candidate_color'])
        self.assertEqual(sum(sum(c.values()) for c in report['categories'].values()), 2)
        self.assertEqual(report['evaluation_suite']['sha256'], meta['sha256'])

    def test_review_continuation_is_legal_and_exports_factual_notes(self):
        board = chess.Board(); board.push_uci('e2e4'); board.push_uci('e7e5')
        before = board.fen()
        runner = ReviewRunner(board, self.ai, depth=2, nodes=100)
        self.finish(runner)
        position = board.root()
        for row, played in zip(runner.rows, board.move_stack):
            probe = position.copy()
            for san in row['continuation']:
                probe.push_san(san)
            self.assertIn('not a forced line', row['uncertainty'])
            position.push(played)
        self.assertEqual(board.fen(), before)
        self.assertEqual(self.ai.learning_db, {})
        self.assertIn('Continuation:', annotated_pgn(runner))

    def test_interrupted_checkpoint_recovers_memory_and_counters(self):
        trainer = TrainingAI(self.ai, depth=1, max_games=1, max_moves=2, exploration_rate=1)
        self.finish(trainer)
        original = copy.deepcopy(self.ai.learning_db)
        self.ai.learning_db['position|e2e4'] = {'w': 2, 'l': 0, 'd': 0}
        trainer.games_played += 1; trainer.results['draw'] += 1
        with patch.object(self.ai, '_save_learning_db', side_effect=OSError('interrupted before memory publication')):
            with self.assertRaises(OSError): trainer._checkpoint()
        self.assertEqual(SimpleAI(learning_path=self.path).learning_db, original)
        resumed = TrainingAI(SimpleAI(learning_path=self.path), max_games=1, max_moves=2, resume=True)
        self.assertEqual(resumed.games_played, 2)
        self.finish(resumed)
        self.assertEqual(resumed.games_played, 3)
        self.assertIn('position|e2e4', SimpleAI(learning_path=self.path).learning_db)

    def test_resume_rejects_external_memory_changes_without_overwriting(self):
        trainer = TrainingAI(self.ai, depth=1, max_games=1, max_moves=2, exploration_rate=1)
        self.finish(trainer)
        self.ai.learning_db['position|e2e4'] = {'w': 5, 'l': 0, 'd': 0}
        self.ai._save_learning_db()
        before = fingerprint(self.ai.learning_db)
        with self.assertRaisesRegex(ValueError, 'changed since'):
            TrainingAI(SimpleAI(learning_path=self.path), resume=True)
        self.assertEqual(fingerprint(SimpleAI(learning_path=self.path).learning_db), before)

    def test_journal_is_validated_by_backup_and_restore(self):
        from profile_store import ProfileStore
        trainer = TrainingAI(self.ai, depth=1, max_games=1, max_moves=2, exploration_rate=1)
        self.finish(trainer)
        store = ProfileStore(self.tmp.name)
        backup = Path(self.tmp.name) / 'backup.zip'
        store.backup(backup)
        store.restore(backup)
        resumed = TrainingAI(SimpleAI(learning_path=self.path), resume=True)
        self.assertEqual(resumed.games_played, 1)

    def test_abrupt_process_exit_between_journal_and_memory_is_recoverable(self):
        import subprocess
        import sys
        script = '''
import os, sys
from simple_ai import SimpleAI
from training_ai import TrainingAI
ai = SimpleAI(depth=1, learning_path=sys.argv[1])
worker = TrainingAI(ai, depth=1, max_games=1, max_moves=2, exploration_rate=1)
worker.start(); worker.thread.join(10)
assert worker.last_error is None
worker.games_played += 1; worker.results['draw'] += 1
ai.learning_db['position|e2e4'] = {'w': 9, 'l': 0, 'd': 0}
ai._save_learning_db = lambda: os._exit(17)
worker._checkpoint()
'''
        env = dict(__import__('os').environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]))
        child = subprocess.run([sys.executable, '-c', script, str(self.path)], env=env, timeout=20, capture_output=True)
        self.assertEqual(child.returncode, 17, child.stderr.decode(errors='replace'))
        resumed = TrainingAI(SimpleAI(learning_path=self.path), max_games=1, max_moves=2, resume=True)
        self.assertEqual(resumed.games_played, 2)
        self.finish(resumed)
        self.assertEqual(resumed.ai.learning_db['position|e2e4']['w'], 9)

    def test_interrupted_progress_write_and_race_before_resume_start(self):
        trainer = TrainingAI(self.ai, depth=1, max_games=1, max_moves=2, exploration_rate=1)
        self.finish(trainer)
        trainer.games_played += 1; trainer.results['draw'] += 1
        from training_ai import atomic_json
        def interrupt_progress(path, data, **kwargs):
            if str(path) == trainer.state_path:
                raise OSError('interrupted progress publication')
            return atomic_json(path, data, **kwargs)
        with patch('training_ai.atomic_json', side_effect=interrupt_progress):
            with self.assertRaises(OSError): trainer._checkpoint()
        pending = TrainingAI(SimpleAI(learning_path=self.path), resume=True)
        self.assertEqual(pending.games_played, 2)
        external = SimpleAI(learning_path=self.path)
        external.learning_db['position|e2e4'] = {'w': 3, 'l': 0, 'd': 0}
        external._save_learning_db()
        with self.assertRaisesRegex(ValueError, 'changed since'):
            pending.start()
        external.acquire_writer(); external.release_writer()
        self.assertEqual(SimpleAI(learning_path=self.path).learning_db, external.learning_db)

    def test_invalid_saved_lesson_preferences_are_rejected_before_use(self):
        from data_validation import configuration
        for data in ({'practice_solved': 1}, {'practice_solved': [None]}, {'selected_lesson': []}):
            with self.assertRaises(ValueError): configuration(data)
        self.assertEqual(configuration({'practice_solved': ['guided:fork'], 'selected_lesson': 'tactics'})['selected_lesson'], 'tactics')
