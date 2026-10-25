"""Opt-in end-to-end checks for the packaged app; uses a temporary profile."""
import json
from pathlib import Path
import sys
import tempfile
import time
import traceback
from app_paths import data_dir, resource_dir, frozen


def run_diagnostics(report_path):
    report = {'success': False, 'frozen': frozen(), 'python': sys.version,
              'resources': str(resource_dir()), 'data_directory': str(data_dir()), 'checks': {}}
    root = None
    app = None
    try:
        import tkinter as tk
        import chess
        from config_manager import ConfigManager
        from game_controller import GameController
        from simple_ai import SimpleAI
        from training_ai import TrainingAI, ComparisonSeries
        from game_review import ReviewRunner
        from tactical_suite import run_suite
        from tools.batch_pgn_converter import batch_convert
        assets = resource_dir() / 'assets'
        assert all((assets / (color + piece + '.png')).is_file()
                   for color in ('w', 'b') for piece in 'pnbrqk'), 'Missing bundled pieces'
        report['checks']['bundled_assets'] = True
        assert Path(ConfigManager().config_file).parent == data_dir()
        with tempfile.TemporaryDirectory(prefix='diagnostics-', dir=data_dir()) as temp:
            temp = Path(temp)
            root = tk.Tk()
            root.withdraw()
            errors = []
            root.report_callback_exception = lambda *args: errors.append(str(args))
            app = GameController(root, config=ConfigManager(str(temp / 'config.json')))
            app.ai = SimpleAI(depth=1, learning_path=temp / 'memory.json')
            assert len(app.piece_images or {}) == 12
            def pump():
                for _ in range(4):
                    root.update()
                    time.sleep(.02)
            pump()
            report['checks']['tkinter_and_pillow'] = True
            app.play_mode = 'player_vs_player'
            app.game_started = True
            for square in (chess.E2, chess.E4, chess.E7, chess.E5):
                app.on_click(square)
                pump()
            assert len(app.board.move_stack) == 2
            before = app.board.fen()
            app._save_session()
            assert app.session_store.load()['board'].fen() == before
            report['checks']['gameplay_and_session_save'] = True
            app.workspace.select(app.practice_workspace)
            pump()
            assert app._activity == 'practice'
            app.on_click(chess.G6)
            app.on_click(chess.G7)
            assert app.practice_done
            app.workspace.select(app.game_workspace)
            pump()
            assert app.board.fen() == before
            report['checks']['practice_isolation'] = True
            from curriculum import course_puzzles, LESSONS, lesson_status
            from practice_model import PuzzleSession
            puzzle = next(p for p in course_puzzles() if p.id == 'guided:fork')
            session = PuzzleSession(puzzle)
            assert session.attempt(chess.Move.from_uci('c3d5'))['reply'] == 'Kf7'
            assert session.attempt(chess.Move.from_uci('d5c7'))['completed']
            assert lesson_status(LESSONS[1], [puzzle.id]) == (1, 2)
            report['checks']['guided_curriculum_and_auto_reply'] = True
            trainer = TrainingAI(app.ai, depth=1, max_games=1, max_moves=4,
                                 move_time_limit=.005, exploration_rate=0)
            trainer.start()
            trainer.thread.join(20)
            if trainer.thread.is_alive():
                trainer.stop()
                raise RuntimeError('Training check timed out')
            assert trainer.last_error is None, str(trainer.last_error)
            assert trainer.games_played == 1
            assert SimpleAI(learning_path=temp / 'memory.json').learning_db == app.ai.learning_db
            resumed = TrainingAI(SimpleAI(learning_path=temp / 'memory.json'), resume=True)
            assert resumed.games_played == 1 and resumed._recovered_memory == app.ai.learning_db
            report['checks']['training_recovery_journal'] = True
            report['checks']['training_and_reload'] = True
            comparison = ComparisonSeries(app.ai, games=2, depth=1, node_limit=20, max_moves=4)
            comparison.start()
            comparison.thread.join(30)
            if comparison.thread.is_alive():
                comparison.stop()
                raise RuntimeError('Comparison check timed out')
            assert comparison.last_error is None, str(comparison.last_error)
            assert len(comparison.reports) == 2
            assert comparison.reports[0]['evaluation_suite']['position_count'] == 16
            assert len(comparison.reports[0]['games_ledger']) == 2
            report['checks']['independent_evaluation_corpus'] = True
            report['checks']['comparison_and_previous_version'] = True
            review = ReviewRunner(app.board, app.ai, depth=1, nodes=100)
            review.start()
            review.thread.join(20)
            assert not review.running and review.last_error is None
            assert len(review.rows) == 2
            report['checks']['game_review'] = True
            from coaching import coaching_moments
            from adaptive_practice import record, recommend
            from comparison_trends import trend_text
            moments = coaching_moments(review.rows)
            assert 1 <= len(moments) <= 3
            app._open_practice_id(moments[0]['puzzle_id'])
            pump()
            assert app._activity == 'practice'
            chosen = app.puzzles[app.practice_index]
            stats = record({}, chosen.id, False, now=100)
            assert recommend(app.puzzles, stats, now=100)[0].id == chosen.id
            app.workspace.select(app.game_workspace)
            pump()
            assert app.board.fen() == before
            assert len(course_puzzles()) == 14
            assert 'Group 1' in trend_text([('diagnostic', comparison.result)])
            report['checks']['coaching_adaptive_and_trends'] = True
            tactics = run_suite(app.ai)
            assert tactics['passed'] == tactics['total'], str(tactics)
            report['checks']['tactics'] = tactics['passed']
            inputs, outputs = temp / 'pgn', temp / 'converted'
            inputs.mkdir()
            (inputs / 'sample.pgn').write_text('[Event "Portable check"]\n\n1. e4 e5 2. Nf3 *\n')
            converted = batch_convert(str(inputs), str(outputs))
            assert converted['ok'] == 1, str(converted)
            report['checks']['bundled_converter'] = True
            from profile_store import ProfileStore
            from puzzle_packs import load_pack
            from support_tools import support_report
            from game_review import annotated_pgn
            from learning_keys import position_key
            profile = temp / 'profile'
            profile.mkdir()
            preferences = ConfigManager(str(profile / 'chess_config.json'))
            preferences.set('ai_depth', 1)
            store = ProfileStore(profile)
            store.backup(temp / 'backup.zip')
            preferences.set('ai_depth', 2)
            rollback = store.restore(temp / 'backup.zip')
            assert rollback.is_file()
            assert ConfigManager(str(profile / 'chess_config.json')).get('ai_depth') == 1
            assert len(load_pack(assets / 'puzzles' / 'studio-extras.json')) == 4
            assert 'Shallow estimate' in annotated_pgn(review)
            assert json.loads(support_report())['frozen'] == frozen()
            assert ' ' in position_key(chess.Board())
            report['checks']['profile_restore_and_puzzle_pack'] = True
            report['checks']['support_and_review_export'] = True
            assert len(load_pack(assets / 'puzzles' / 'reference-themes.json')) == 4
            from game_endings import timeout_conclusion
            app.new_game()
            app.board = chess.Board('7k/8/8/8/8/8/R7/K7 w - - 0 1')
            assert app._declare_result(timeout_conclusion(app.board, chess.WHITE))
            assert app.current_pgn().headers['Result'] == '1/2-1/2'
            assert not app.session_store.path.exists()
            report['checks']['timeout_draw_and_pgn_result'] = True
            assert not errors, str(errors)
            app.on_close()
            app = root = None
        report['success'] = True
    except Exception:
        report['error'] = traceback.format_exc()
    finally:
        if app is not None:
            app.on_close()
        elif root is not None:
            root.destroy()
        target = Path(report_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, indent=2), encoding='utf-8')
    return 0 if report['success'] else 1
