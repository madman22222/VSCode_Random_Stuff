"""Behavioral regressions for backups, validated input, review and study tools."""
import gzip
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import chess
import chess.pgn
from config_manager import ConfigManager
from data_validation import configuration, learning_records, read_json, validated_fen
from game_review import ReviewRunner, annotated_pgn
from learning_storage import writer_lease
from profile_store import ProfileStore, profile_path
from puzzle_packs import load_pack
from simple_ai import SimpleAI
from training_ai import TrainingAI, ComparisonSeries


class ProfileTools(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve() / 'data'
        self.root.mkdir()
        self.store = ProfileStore(self.root)
        self.config = self.root / 'chess_config.json'
        self.config.write_text('{"ai_depth": 2}')
        self.backup = self.root.parent / 'backup.zip'

    def test_backup_restore_exact_contents_and_retains_rollback(self):
        (self.root / 'ai_learn.json').write_text('{}')
        self.store.backup(self.backup)
        self.config.write_text('{"ai_depth": 4}')
        (self.root / 'ai_learn.json.gz').write_bytes(gzip.compress(b'{}'))
        rollback = self.store.restore(self.backup)
        self.assertEqual(json.loads(self.config.read_text())['ai_depth'], 2)
        self.assertFalse((self.root / 'ai_learn.json.gz').exists())
        self.assertTrue(rollback.exists())
        self.assertEqual(json.loads(self.store.inspect(rollback)['chess_config.json'])['ai_depth'], 4)

    def test_restore_rolls_back_if_write_fails(self):
        self.store.backup(self.backup)
        self.config.write_text('{"ai_depth": 3}')
        replace = self.store._replace
        count = 0
        def failure_once(files):
            nonlocal count
            count += 1
            if count == 1:
                self.config.write_text('{"ai_depth": 5}')
                raise OSError('disk failed')
            replace(files)
        with patch.object(self.store, '_replace', side_effect=failure_once):
            with self.assertRaises(OSError):
                self.store.restore(self.backup)
        self.assertEqual(json.loads(self.config.read_text())['ai_depth'], 3)

    def test_checksum_and_traversal_rejection_preserve_data(self):
        original = self.config.read_bytes()
        for name in ('../escape.json', 'chess_config.json'):
            with zipfile.ZipFile(self.backup, 'w') as archive:
                archive.writestr(name, '{}')
                archive.writestr('MANIFEST.json', json.dumps({'version': 1, 'files': {name: 'wrong'}}))
            with self.assertRaises(ValueError):
                self.store.restore(self.backup)
            self.assertEqual(self.config.read_bytes(), original)

    def test_competing_writer_blocks_backup_and_restore(self):
        self.store.backup(self.backup)
        with writer_lease(self.root / 'ai_learn.json'):
            with self.assertRaises(RuntimeError):
                self.store.backup(self.backup)
            with self.assertRaises(RuntimeError):
                self.store.restore(self.backup)

    def test_named_profiles_and_archives_are_isolated(self):
        a, b = profile_path(self.root, 'first'), profile_path(self.root, 'second')
        a.parent.mkdir(parents=True)
        a.write_text('{}')
        self.store.backup(self.backup)
        self.assertIn('profiles/first/ai_learn.json', self.store.inspect(self.backup))
        self.assertFalse(b.exists())
        for name in ('../bad', '', 'x/y', 'a' * 41):
            with self.assertRaises(ValueError):
                profile_path(self.root, name)

    def test_history_does_not_create_spurious_writer_locks(self):
        folder = self.root / 'profiles' / 'study' / 'comparison-history'
        folder.mkdir(parents=True)
        (folder / 'report.json').write_text('{}')
        (self.root / 'last_session.invalid-1.json').write_bytes(b'bad historical recovery bytes')
        self.store.backup(self.backup)
        self.assertFalse((folder / 'report.json.lock').exists())
        self.assertIn('last_session.invalid-1.json', self.store.inspect(self.backup))

    def test_learning_validation_supports_formats_rejects_invalid_before_mutation(self):
        records = {'position|e2e4': {'w': 2, 'l': 0, 'd': 1, 'ts': 12}}
        self.assertEqual(learning_records({'meta': {'version': 2}, 'data': records}), records)
        readable = {'meta': {'version': 1}, 'positions': {'position': {'moves': {
            'e2e4': {'wins': 2, 'losses': 0, 'draws': 1}}}}}
        self.assertEqual(learning_records(readable)['position|e2e4']['w'], 2)
        for data in ({'meta': {'version': 99}, 'data': records},
                     {'position|not-a-move': {'w': 1, 'l': 0, 'd': 0}},
                     {'position|e2e4': {'w': -1, 'l': 0, 'd': 0}}):
            with self.assertRaises(ValueError):
                learning_records(data)

    def test_corrupt_learning_and_config_cannot_be_silently_overwritten(self):
        path = self.root / 'ai_learn.json'
        path.write_text('{bad')
        ai = SimpleAI(learning_path=path)
        self.assertTrue(ai.load_error)
        with self.assertRaises(ValueError):
            ai._save_learning_db()
        self.assertEqual(path.read_text(), '{bad')
        self.config.write_text('{"ai_depth": "bad"}')
        config = ConfigManager(self.config)
        self.assertTrue(config.load_error)
        with self.assertRaises(ValueError):
            config.save_config()
        self.assertEqual(self.config.read_text(), '{"ai_depth": "bad"}')

    def test_failed_preference_write_rolls_back_in_memory_value(self):
        config = ConfigManager(self.config)
        with patch.object(config, 'save_config', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                config.set('learning_profile', 'wrong-profile')
        self.assertIsNone(config.get('learning_profile'))

    def test_bounded_gzip_input_and_future_config(self):
        path = self.root / 'big.json.gz'
        with gzip.open(path, 'wb') as stream:
            stream.write(b' ' * 1000)
        with patch('data_validation.MAX_JSON_BYTES', 100):
            with self.assertRaises(ValueError):
                read_json(path)
        with self.assertRaises(ValueError):
            configuration({'schema_version': 2})

    def test_custom_start_review_export_preserves_original_and_mate_uncertainty(self):
        board = validated_fen('7k/8/5KQ1/8/8/8/8/8 w - - 0 1')
        board.push_san('Qg7#')
        before = board.fen()
        runner = ReviewRunner(board, SimpleAI(load_learning=False), nodes=100)
        runner._run()
        exported = chess.pgn.read_game(io.StringIO(annotated_pgn(runner)))
        self.assertEqual(exported.end().board().fen(), before)
        self.assertEqual(board.fen(), before)
        self.assertIn('Shallow estimate', exported.end().comment)

    def test_fen_and_puzzle_pack_validation(self):
        with self.assertRaises(ValueError):
            validated_fen('8/8/8/8/8/8/8/8 w - - 0 1')
        pack = {'version': 1, 'id': 'test', 'author': 'Hand-built test', 'puzzles': [{
            'id': 'mate', 'title': 'Mate', 'fen': '7k/8/5KQ1/8/8/8/8/8 w - - 0 1',
            'hints': ['Use the queen'], 'solutions': ['g6g7']}]}
        path = self.root / 'puzzles.json'
        path.write_text(json.dumps(pack))
        puzzle = load_pack(path)[0]
        self.assertTrue(puzzle.accepts(chess.Board(puzzle.fen), chess.Move.from_uci('g6g7')))
        pack['puzzles'][0]['solutions'] = ['a1a2']
        path.write_text(json.dumps(pack))
        with self.assertRaises(ValueError):
            load_pack(path)

    def test_checkpoint_and_recent_results_summary(self):
        ai = SimpleAI(learning_path=self.root / 'learn.json')
        trainer = TrainingAI(ai, max_games=2, max_moves=2, depth=1, move_time_limit=.001)
        trainer.start()
        trainer.thread.join(10)
        self.assertIsNone(trainer.last_error)
        snap = trainer.snapshot()
        self.assertEqual(snap['saved_games'], 2)
        self.assertEqual(len(snap['recent_results']), 2)
        self.assertIn('games/min', trainer.progress_summary())

    def test_comparison_history_is_retained_separately_from_latest(self):
        ai = SimpleAI(learning_path=self.root / 'learn.json')
        for _ in range(2):
            runner = ComparisonSeries(ai, games=2, depth=1, node_limit=20, max_moves=2, against='untrained')
            runner.start()
            runner.thread.join(10)
            self.assertIsNone(runner.last_error)
        self.assertEqual(len(list((self.root / 'comparison-history').glob('*.json'))), 2)


class ContextualKeys(unittest.TestCase):
    def test_side_castling_and_en_passant_do_not_share_memory(self):
        from learning_keys import position_key
        board = chess.Board()
        other = board.copy()
        other.turn = not board.turn
        self.assertNotEqual(position_key(board), position_key(other))
        other = board.copy()
        other.castling_rights = 0
        self.assertNotEqual(position_key(board), position_key(other))
        board = chess.Board('7k/8/8/3pP3/8/8/8/K7 w - d6 0 1')
        other = board.copy()
        other.ep_square = None
        self.assertNotEqual(position_key(board), position_key(other))

    def test_legacy_counts_retained_without_invented_context(self):
        from learning_keys import position_key
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'memory.json'
            board = chess.Board()
            legacy = board.board_fen() + '|e2e4'
            path.write_text(json.dumps({'meta': {'version': 2, 'outcome_scoring': True},
                                        'data': {legacy: {'w': 100, 'l': 0, 'd': 0}}}))
            ai = SimpleAI(learning_path=path)
            self.assertFalse(ai.use_outcome_scoring)
            self.assertEqual(ai.learning_db[legacy]['w'], 100)
            self.assertEqual(ai._learn_bonus(position_key(board), 'e2e4'), 0)
            ai._log_choice(position_key(board), 'e2e4', True)
            ai.finalize_game('white')
            self.assertEqual(SimpleAI(learning_path=path).learning_db[legacy]['w'], 100)
            self.assertEqual(ai.learning_db[position_key(board) + '|e2e4']['w'], 1)

class MemoryLimits(unittest.TestCase):
    def test_cache_is_bounded_and_pruning_keeps_valid_records(self):
        ai = SimpleAI(depth=3, load_learning=False)
        ai.transposition_limit = 4
        board = chess.Board()
        ai.choose_move_iterative(board, .2, record=False, node_limit=1000)
        self.assertLessEqual(len(ai.transposition_table), 4)
        self.assertEqual(board.fen(), chess.Board().fen())
        ai.learning_db = {f'position{i}|e2e4': {'w': i, 'l': 0, 'd': 0} for i in range(10)}
        ai.learning_max_entries, ai.learning_min_keep = 8, 4
        ai._maybe_prune_learning()
        self.assertLessEqual(len(ai.learning_db), 4)
        self.assertEqual(learning_records(ai.learning_db), ai.learning_db)

class SupportChecks(unittest.TestCase):
    def test_update_lookup_rejects_foreign_release_links(self):
        from support_tools import latest_release
        with patch('support_tools.urlopen') as request:
            request.return_value.__enter__.return_value.read.return_value = json.dumps({
                'html_url': 'https://example.com/installer', 'tag_name': 'fake'}).encode()
            with self.assertRaises(ValueError):
                latest_release()

    def test_support_report_excludes_learning_and_games(self):
        from support_tools import support_report
        report = json.loads(support_report())
        self.assertIn('build', report)
        self.assertNotIn('learning_db', report)
        self.assertNotIn('games', report)

    def test_checkpoint_rejects_nonfinite_time_and_future_version(self):
        from data_validation import training_checkpoint
        for record in ({'version': 9}, {'results': {'white': 0, 'black': 0, 'draw': 0},
                                      'elapsed_seconds': float('nan')}):
            with self.assertRaises(ValueError):
                training_checkpoint(record)
