"""Study data, fresh positions, recovery, staged upgrades and worker contracts."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
import chess
from simple_ai import SimpleAI
from training_ai import TrainingAI
from study_data import StudyStore, VariationSession, RepertoireSession, plan_session, training_health
from fresh_practice import fresh_catalogue, choose_fresh
from recovery_tools import checkpoint_choices, checkpoint_preview, restore_checkpoint, inspect_upgrade, prepare_upgrade
from parallel_training import training_factory

PGN = '[Event "Study"]\n[White "Alice"]\n[Black "Bob"]\n\n1. e4 e5 2. Nf3 (2. Bc4 Nc6) Nc6 *'


class TestStudyFoundations(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.memory = self.root / 'ai_learn.json'

    def finish(self, worker):
        worker.start(); worker.thread.join(45)
        if worker.running: worker.stop()
        self.assertFalse(worker.running)
        self.assertIsNone(worker.last_error)

    def test_game_library_search_notes_tags_and_roundtrip(self):
        store = StudyStore(self.root)
        game = store.add_game(PGN, tags='opening')
        self.assertEqual(len(store.search('Alice')), 1)
        store.edit_game(game['id'], 'Watch the center', 'lesson')
        self.assertEqual(len(store.search('center')), 1)
        store.delete('games', game['id'])
        self.assertEqual(store.search(), [])

    def test_variation_next_back_reset_and_legal_branch_preserve_original(self):
        board = chess.Board()
        session = VariationSession(board, ['e4', 'e5'])
        session.next(); self.assertEqual(session.board.peek().uci(), 'e2e4')
        session.push('c5')
        with self.assertRaises(ValueError): session.next()
        session.back(); session.next()
        session.reset()
        self.assertEqual(session.board.fen(), board.fen())
        self.assertEqual(board.move_stack, [])

    def test_repertoire_accepts_authored_branches_and_auto_replies(self):
        row = StudyStore(self.root).add_repertoire('Open games', PGN)
        session = RepertoireSession(row)
        self.assertTrue(session.attempt('e2e4'))
        self.assertEqual(session.board.peek().uci(), 'e7e5')
        self.assertTrue(session.attempt('f1c4'))
        self.assertTrue(session.done)
        self.assertEqual(session.board.peek().uci(), 'b8c6')

    def test_fresh_positions_are_valid_novel_and_cover_all_lessons(self):
        from curriculum import course_puzzles, LESSONS
        from tactical_suite import PUZZLES
        from practice_model import validate_lines
        catalogue, lessons = fresh_catalogue()
        base = {chess.Board(p.fen).board_fen() + str(chess.Board(p.fen).turn) for p in list(PUZZLES) + list(course_puzzles())}
        for lesson in LESSONS:
            self.assertGreaterEqual(len(lessons[lesson[0]]), 2, lesson[0])
        for puzzle in catalogue.values():
            board = chess.Board(puzzle.fen)
            self.assertTrue(board.is_valid())
            self.assertNotIn(board.board_fen() + str(board.turn), base)
            validate_lines(board, [list(line) for line in puzzle.lines], puzzle.goal)

    def test_session_and_health_are_read_only(self):
        from curriculum import course_puzzles
        stats = {'guided:fork': {'streak': 0, 'due': 1}}
        before = copy.deepcopy(stats)
        self.assertEqual(plan_session(course_puzzles(), stats, minutes=6, now=100)[0], 'guided:fork')
        self.assertEqual(stats, before)
        report = training_health({'position|e2e4': {'w': 1, 'l': 0, 'd': 0}},
                                 {'results': {'draw': 10}, 'move_limit_draws': 8})
        self.assertEqual(report['cutoff_draw_percent'], 80)
        self.assertEqual(report['records_below_five_samples'], 1)

    def test_rolling_checkpoints_preview_and_transactional_restore(self):
        worker = TrainingAI(SimpleAI(depth=1, learning_path=self.memory), depth=1,
                            max_games=4, max_moves=2, batch_size=1, exploration_rate=1, checkpoint_keep=2)
        self.finish(worker)
        choices = checkpoint_choices(self.memory)
        self.assertEqual(len(choices), 2)
        preview = checkpoint_preview(choices[-1])
        rollback = restore_checkpoint(self.root, self.memory, choices[-1])
        self.assertTrue(rollback.exists())
        resumed = training_factory(SimpleAI(learning_path=self.memory), resume=True, max_games=1, max_moves=2)
        self.assertEqual(resumed.games_played, preview['games'])

    def release(self, unsafe=False):
        archive = self.root / 'release.zip'
        with zipfile.ZipFile(archive, 'w') as out:
            out.writestr('ChessStudio/BUILD_INFO.json', json.dumps({'revision': 'a' * 40}))
            out.writestr('ChessStudio/ChessStudio.exe', b'test fixture')
            if unsafe: out.writestr('ChessStudio/../../escape', b'bad')
        digest = self.root / 'release.sha256'
        digest.write_text(hashlib.sha256(archive.read_bytes()).hexdigest() + '  release.zip\n')
        return archive, digest

    def test_upgrade_checks_hash_and_paths_before_migration(self):
        archive, digest = self.release(unsafe=True)
        with self.assertRaises(ValueError): inspect_upgrade(archive, digest)
        archive, digest = self.release()
        digest.write_text('0' * 64)
        with self.assertRaises(ValueError): inspect_upgrade(archive, digest)

    def test_upgrade_stages_data_and_keeps_original_and_backup(self):
        profile = self.root / 'old-data'; profile.mkdir()
        (profile / 'chess_config.json').write_text('{"schema_version":1}')
        archive, digest = self.release()
        result = prepare_upgrade(profile, archive, digest, self.root / 'new')
        self.assertTrue(Path(result['folder'], 'data', 'chess_config.json').exists())
        self.assertTrue(Path(result['backup']).exists())
        self.assertTrue((profile / 'chess_config.json').exists())

    def test_parallel_workers_merge_once_and_resume_resource_settings(self):
        worker = training_factory(SimpleAI(depth=1, learning_path=self.memory), workers=2,
                                  depth=1, max_games=3, max_moves=4, move_time_limit=.001,
                                  exploration_rate=1, batch_size=2, cpu_percent=50)
        self.finish(worker)
        self.assertEqual(worker.games_played, 3)
        self.assertEqual(sum(r['d'] for r in worker.ai.learning_db.values()), 12)
        self.assertEqual(SimpleAI(learning_path=self.memory).learning_db, worker.ai.learning_db)
        resumed = training_factory(SimpleAI(learning_path=self.memory), resume=True, max_games=1, max_moves=2)
        self.assertEqual(resumed.workers, 2)
        self.assertEqual(resumed.cpu_percent, 50)

    def test_parallel_cancellation_releases_parent_writer(self):
        worker = training_factory(SimpleAI(depth=1, learning_path=self.memory), workers=2,
                                  depth=1, max_games=10, max_moves=100, move_time_limit=.005)
        worker.start(); worker.request_stop(); worker.thread.join(45)
        self.assertFalse(worker.running)
        self.assertIsNone(worker.last_error)
        probe = SimpleAI(learning_path=self.memory); probe.acquire_writer(); probe.release_writer()
