"""Learning schedules, teaching coverage and comparable longitudinal reports."""
import copy
from pathlib import Path
import tempfile
import unittest
import chess
from adaptive_practice import record, recommend
from coaching import coaching_moments
from comparison_trends import observations, trend_text
from curriculum import course_puzzles, LESSONS
from data_validation import configuration
from practice_model import PuzzleSession
from tactical_suite import PUZZLES


class TestCoachingLearning(unittest.TestCase):
    def test_failed_and_assisted_work_returns_before_new_harder_material(self):
        puzzles = list(PUZZLES) + list(course_puzzles())
        original = {}
        stats = record(original, 'guided:fork', False, now=100)
        chosen, reason = recommend(puzzles, stats, now=100)
        self.assertEqual(chosen.id, 'guided:fork')
        self.assertEqual(original, {})
        stats = record(stats, chosen.id, True, assisted=True, now=110)
        self.assertEqual(stats[chosen.id]['streak'], 0)
        self.assertEqual(stats[chosen.id]['due'], 110 + 86400)
        self.assertNotEqual(recommend(puzzles, stats, now=120)[0].id, chosen.id)
        self.assertEqual(recommend(puzzles, stats, now=110 + 86400)[0].id, chosen.id)
        configuration({'practice_stats': stats})

    def test_unassisted_review_intervals_grow_and_mistake_resets_schedule(self):
        stats = {}
        now = 100
        for days in (1, 3, 7, 14, 30, 30):
            stats = record(stats, 'guided:fork', True, now=now)
            self.assertEqual(stats['guided:fork']['due'], now + days * 86400)
            now = stats['guided:fork']['due']
        failed = record(stats, 'guided:fork', False, now=now)
        self.assertEqual(failed['guided:fork']['streak'], 0)
        self.assertEqual(failed['guided:fork']['due'], now)

    def test_catalogue_covers_every_lesson_and_authored_alternative(self):
        puzzles = list(PUZZLES) + list(course_puzzles())
        self.assertEqual(len(puzzles), 21)
        self.assertEqual(len(LESSONS), 9)
        self.assertTrue({id for lesson in LESSONS for id in lesson[3]} <= {p.id for p in puzzles})
        for puzzle in course_puzzles():
            for line in puzzle.lines:
                session = PuzzleSession(puzzle)
                # Force the authored defense being tested, including non-first alternatives.
                for index in range(0, len(line), 2):
                    if index + 1 < len(line):
                        prefix = tuple(line[:index + 1])
                        replies = list(dict.fromkeys(x[index + 1] for x in puzzle.lines if x[:index + 1] == prefix))
                        session.variant = replies.index(line[index + 1])
                    response = session.attempt(chess.Move.from_uci(line[index]))
                    self.assertTrue(response['accepted'], (puzzle.id, line))
                self.assertTrue(session.done)

    def test_schedule_validation_preserves_unreadable_preferences(self):
        bad = ({'x': {'successes': -1}}, {'x': {'successes': 1, 'mistakes': 0, 'streak': 0, 'last': 1, 'due': float('nan')}})
        for stats in bad:
            with self.assertRaises(ValueError): configuration({'practice_stats': stats})
        from config_manager import ConfigManager
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'chess_config.json'
            path.write_text('{"practice_stats": {"x": {"successes": -1}}}')
            original = path.read_bytes()
            config = ConfigManager(str(path))
            self.assertIsNotNone(config.load_error)
            with self.assertRaises(ValueError): config.save_config()
            self.assertEqual(path.read_bytes(), original)

    def test_coaching_selects_three_distinct_positions_and_links_available_exercises(self):
        rows = [dict(san='Nf3', suggested='Nc3', estimated_loss_cp=20, facts=[]),
                dict(san='Bb5', suggested='Nd5+', estimated_loss_cp=200, facts=['Attacks multiple pieces.']),
                dict(san='Kg8', suggested='Kh7', estimated_loss_cp=None, facts=['Absolute pin on c6.'], side='black', move_number=32),
                dict(san='Ra8', suggested='Ra7', estimated_loss_cp=10, facts=[])]
        before = copy.deepcopy(rows)
        moments = coaching_moments(rows)
        self.assertEqual(len(moments), 3)
        self.assertEqual(moments[0]['index'], 1)
        self.assertEqual(len({m['index'] for m in moments}), 3)
        self.assertIn('32...', next(m['text'] for m in moments if m['index'] == 2))
        ids = {p.id for p in list(PUZZLES) + list(course_puzzles())}
        self.assertTrue(all(m['puzzle_id'] in ids for m in moments))
        self.assertEqual(rows, before)
        self.assertEqual(coaching_moments([]), [])
        self.assertEqual(len(coaching_moments(rows[:1])), 1)

    def report(self, **updates):
        row = dict(state='completed', evaluation_protocol=2, completed_pairs=20, evaluation_suite={'sha256': 'abc', 'remembered_roots': 0},
                   depth=2, nodes_per_move=500, max_plies=120, opponent='untrained', candidate_outcome_scoring=False,
                   baseline_memory_fingerprint='empty', baseline_outcome_scoring=False,
                   seed=2026, memory_fingerprint='model-a', score_percent=50, ci95_score_percent=[30, 70], move_limit_draws=3)
        row.update(updates)
        return row

    def test_trends_separate_budget_seed_baseline_corpus_and_ignore_partial_runs(self):
        reports = [('1', self.report()), ('2', self.report(memory_fingerprint='model-b', score_percent=55))]
        for key, value in (('depth', 3), ('seed', 7), ('baseline_memory_fingerprint', 'old-model'), ('evaluation_suite', {'sha256': 'different'})):
            reports.append((str(len(reports) + 1), self.report(**{key: value})))
        reports.extend([('cancelled', self.report(state='cancelled')), ('legacy', self.report(evaluation_protocol=1))])
        self.assertEqual(len({r['signature'] for r in observations(reports)}), 5)
        text = trend_text(reports)
        self.assertIn('+5.0 percentage points', text)
        self.assertIn('not proof of improvement', text)
        self.assertIn('intervals are not pooled', text)
        self.assertNotIn('cancelled:', text)

    def test_old_profile_upgrade_retains_progress_and_backup_round_trips_schedule(self):
        import json
        from config_manager import ConfigManager
        from profile_store import ProfileStore
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'chess_config.json'
            path.write_text(json.dumps({'schema_version': 1, 'practice_solved': ['mate-white']}))
            config = ConfigManager(str(path))
            self.assertEqual(config.get('practice_solved'), ['mate-white'])
            config.set('practice_stats', record({}, 'mate-white', True, now=100))
            archive = Path(temp) / 'backup.zip'
            store = ProfileStore(temp); store.backup(archive)
            config.set('practice_stats', {})
            store.restore(archive)
            restored = ConfigManager(str(path))
            self.assertEqual(restored.get('practice_solved'), ['mate-white'])
            self.assertEqual(restored.get('practice_stats')['mate-white']['due'], 86500)

    def test_malformed_trend_rows_are_skipped_without_crashing_history(self):
        for key, value in (('depth', []), ('score_percent', float('nan')), ('ci95_score_percent', [80, 20]), ('baseline_memory_fingerprint', {}), ('candidate_outcome_scoring', [])):
            self.assertEqual(observations([('invalid', self.report(**{key: value}))]), [])
