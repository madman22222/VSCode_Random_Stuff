"""Profile and compare exact-budget search/training against an immutable Git revision."""
import argparse
import copy
import cProfile
import io
import json
import platform
import pstats
import random
import statistics
import subprocess
import sys
import tempfile
import time
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'chess'))
import chess
from simple_ai import SimpleAI
from training_ai import TrainingAI

BASE = 'e2e5f0a9147c392dcd41298a0334dfd7cd70ee92'


def reference(path, name):
    source = subprocess.check_output(['git', 'show', BASE + ':' + path], cwd=ROOT, text=True)
    module = types.ModuleType(name)
    sys.modules[name] = module
    exec(compile(source, BASE + ':' + path, 'exec'), module.__dict__)
    return module


def workloads():
    rows = json.loads((ROOT / 'benchmarks/positions.json').read_text())['positions']
    rows += json.loads((ROOT / 'chess/assets/evaluation/independent-v1.json').read_text())['positions']
    return rows


def search_sample(cls, row, nodes):
    ai = cls(depth=4, load_learning=False)
    board = chess.Board(row['fen'])
    before = board.fen(), list(board.move_stack)
    started = time.perf_counter()
    move = ai.choose_move_iterative(board, 60, record=False, node_limit=nodes)
    elapsed = time.perf_counter() - started
    assert move in board.legal_moves
    assert (board.fen(), board.move_stack) == before
    metrics = {k: ai.last_move_metrics[k] for k in ('move', 'depth', 'nodes', 'score_cp')}
    return elapsed, metrics


def profile():
    profiler = cProfile.Profile()
    profiler.enable()
    for row in workloads():
        search_sample(SimpleAI, row, 1200)
    profiler.disable()
    stream = io.StringIO()
    pstats.Stats(profiler, stream=stream).strip_dirs().sort_stats('cumtime').print_stats(35)
    print('SEARCH PROFILE\n' + stream.getvalue())
    profiler = cProfile.Profile()
    with tempfile.TemporaryDirectory() as temp:
        ai = SimpleAI(depth=2, learning_path=Path(temp) / 'memory.json')
        trainer = TrainingAI(ai, depth=2, max_games=3, max_moves=20,
                             move_time_limit=.015, batch_size=1, exploration_rate=0)
        loop = trainer._training_loop
        trainer._training_loop = lambda: profiler.runcall(loop)
        trainer.start()
        trainer.thread.join(60)
        assert not trainer.running and trainer.last_error is None, trainer.last_error
    stream = io.StringIO()
    pstats.Stats(profiler, stream=stream).strip_dirs().sort_stats('cumtime').print_stats(35)
    print('SELF PLAY PROFILE\n' + stream.getvalue())


def compare(repeats=5, nodes=3000):
    old = reference('chess/simple_ai.py', 'reference_simple_ai').SimpleAI
    report = {'base': BASE, 'revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'python': platform.python_version(), 'platform': platform.platform(),
              'repeats': repeats, 'nodes': nodes, 'depth': 4, 'search': [], 'evaluation_positions': 0}
    rng = random.Random(718)
    board = chess.Board()
    for _ in range(1000):
        if board.is_game_over(claim_draw=True):
            board = chess.Board()
        before = board.fen(), list(board.move_stack)
        a, b = SimpleAI(load_learning=False), old(load_learning=False)
        assert a.evaluate(board) == b.evaluate(board), board.fen()
        for color in chess.COLORS:
            assert a.evaluate_pawn_structure(board, color) == b.evaluate_pawn_structure(board, color)
        assert (board.fen(), board.move_stack) == before
        report['evaluation_positions'] += 1
        board.push(rng.choice(list(board.legal_moves)))
    for row in workloads():
        samples = {'before': [], 'after': []}
        expected = None
        # Alternate order to reduce warm-up/runner bias; no tracing inside timers.
        for repeat in range(repeats):
            for name, cls in ([('before', old), ('after', SimpleAI)] if repeat % 2 == 0
                              else [('after', SimpleAI), ('before', old)]):
                elapsed, metrics = search_sample(cls, row, nodes)
                if expected is None:
                    expected = metrics
                assert metrics == expected, (row['id'], name, metrics, expected)
                samples[name].append(elapsed)
        medians = {name: statistics.median(values) for name, values in samples.items()}
        report['search'].append({'id': row['id'], 'samples': samples, 'medians': medians,
                                 'speedup': medians['before'] / medians['after'], 'metrics': expected})
    ratios = [item['speedup'] for item in report['search']]
    report['summary'] = {'median_workload_speedup': statistics.median(ratios),
                         'geometric_mean_speedup': statistics.geometric_mean(ratios),
                         'min_workload_speedup': min(ratios), 'max_workload_speedup': max(ratios)}
    print('SEARCH SUMMARY ' + json.dumps(report['summary']))
    print('SEARCH A/B ' + json.dumps([{k: row[k] for k in ('id', 'speedup', 'metrics')} for row in report['search']]))
    return report


def records(size):
    # Schema-valid opaque historical keys; synthetic data benchmarks I/O only.
    return {f'position-{n}|e2e4': {'w': n % 9, 'l': n % 3, 'd': n % 7, 'ts': 1700000000}
            for n in range(size)}


def storage_and_training(report):
    from unittest.mock import patch
    old_ai = reference('chess/simple_ai.py', 'storage_reference_ai').SimpleAI
    old_training = reference('chess/training_ai.py', 'storage_reference_training').TrainingAI
    large = records(50000)
    report['checkpoint'] = {}
    for name, cls, trainer_cls in [('before', old_ai, old_training), ('after', SimpleAI, TrainingAI)]:
        samples = []
        with tempfile.TemporaryDirectory() as temp:
            ai = cls(depth=1, learning_path=Path(temp) / 'memory.json')
            ai.learning_db = copy.deepcopy(large)
            trainer = trainer_cls(ai, depth=1)
            ai.acquire_writer()
            try:
                for _ in range(5):
                    started = time.perf_counter()
                    trainer._checkpoint()
                    samples.append(time.perf_counter() - started)
                assert cls(learning_path=ai._learning_path).learning_db == large
                import tracemalloc
                tracemalloc.start()
                try:
                    trainer._checkpoint()
                    _, peak = tracemalloc.get_traced_memory()
                finally:
                    tracemalloc.stop()
                report['checkpoint'][name] = {'samples': samples, 'median_seconds': statistics.median(samples), 'peak_traced_bytes': peak,
                    'gzip_bytes': Path(ai._learning_path_gz).stat().st_size,
                    'journal_bytes': Path(trainer.journal_path).stat().st_size}
            finally:
                ai.release_writer()
    report['training'] = {}
    expected = None
    for name, cls, trainer_cls in [('before', old_ai, old_training), ('after', SimpleAI, TrainingAI)]:
        samples = []
        for repeat in range(3):
            with tempfile.TemporaryDirectory() as temp:
                ai = cls(depth=2, learning_path=Path(temp) / 'memory.json')
                ai.learning_db = copy.deepcopy(records(10000))
                choose = ai.choose_move_iterative
                ai.choose_move_iterative = lambda board, limit, **kw: choose(board, 30, node_limit=80, **kw)
                trainer = trainer_cls(ai, depth=2, batch_size=3, max_games=6, max_moves=12,
                                      exploration_rate=.2, seed=77)
                with patch('time.time', return_value=1800000000):
                    started = time.perf_counter()
                    trainer.start(); trainer.thread.join(60)
                    elapsed = time.perf_counter() - started
                assert not trainer.running and trainer.last_error is None, trainer.last_error
                learned = {key: {k: v for k, v in value.items() if k != 'ts'}
                           for key, value in ai.learning_db.items()}
                state = (trainer.games_played, trainer.results, trainer.move_limit_draws, learned)
                if expected is None:
                    expected = state
                assert state == expected, (name, 'Self-play outcomes or learned counts changed')
                assert trainer.snapshot()['positions'] == len({key.split('|', 1)[0] for key in ai.learning_db})
                assert cls(learning_path=ai._learning_path).learning_db == ai.learning_db
                samples.append(elapsed)
        report['training'][name] = {'samples': samples, 'median_seconds': statistics.median(samples)}
    print('CHECKPOINT A/B ' + json.dumps(report['checkpoint']))
    print('SELF PLAY A/B ' + json.dumps(report['training']))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--profile-only', action='store_true')
    args = parser.parse_args()
    profile()
    report = {'profile_only': True} if args.profile_only else compare()
    if not args.profile_only:
        storage_and_training(report)
    Path(args.output).write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
