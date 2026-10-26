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
    ai = cls(depth=3, load_learning=False)
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


def compare(repeats=5, nodes=1200):
    old = reference('chess/simple_ai.py', 'reference_simple_ai').SimpleAI
    report = {'base': BASE, 'revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'python': platform.python_version(), 'platform': platform.platform(),
              'repeats': repeats, 'nodes': nodes, 'search': [], 'evaluation_positions': 0}
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
    print('SEARCH A/B ' + json.dumps([{k: row[k] for k in ('id', 'speedup', 'metrics')} for row in report['search']]))
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--profile-only', action='store_true')
    args = parser.parse_args()
    profile()
    report = {'profile_only': True} if args.profile_only else compare()
    Path(args.output).write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
