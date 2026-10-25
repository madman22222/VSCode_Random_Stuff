"""Repeat real training/checkpoint/resume/cancel cycles in an isolated profile."""
import argparse
import gc
import json
import platform
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'chess'))
from simple_ai import SimpleAI
from training_ai import TrainingAI


def run(cycles):
    started = time.monotonic()
    samples = []
    tracemalloc.start()
    try:
        with tempfile.TemporaryDirectory(prefix='chess-soak-') as temp:
            path = Path(temp) / 'memory.json'
            expected = 0
            for cycle in range(cycles):
                ai = SimpleAI(depth=1, learning_path=path)
                worker = TrainingAI(ai, depth=1, batch_size=1, max_games=1,
                                    max_moves=6, move_time_limit=.002,
                                    exploration_rate=0, resume=cycle > 0)
                worker.start()
                worker.thread.join(15)
                if worker.thread.is_alive():
                    worker.request_stop()
                    worker.thread.join(6)
                    raise RuntimeError('Training exceeded its bounded duration')
                if worker.last_error:
                    raise worker.last_error
                expected += 1
                assert worker.games_played == expected
                assert SimpleAI(learning_path=path).learning_db == ai.learning_db
                # Exercise cancellation while the worker owns its writer lease.
                cancel = TrainingAI(SimpleAI(depth=1, learning_path=path), depth=1,
                                    max_moves=100, move_time_limit=.002, resume=True)
                cancel.start()
                cancel.request_stop()
                cancel.thread.join(10)
                assert not cancel.thread.is_alive(), 'Cancellation hung'
                if cancel.last_error:
                    raise cancel.last_error
                expected = cancel.games_played
                probe = SimpleAI(learning_path=path)
                probe.acquire_writer()
                probe.release_writer()
                assert len(ai.transposition_table) <= ai.transposition_limit
                assert len(ai.learning_db) <= ai.learning_max_entries
                del worker, cancel, ai, probe
                gc.collect()
                current, peak = tracemalloc.get_traced_memory()
                samples.append({'cycle': cycle + 1, 'games': expected,
                                'retained_bytes': current, 'peak_bytes': peak})
    finally:
        tracemalloc.stop()
    return {'success': True, 'python': platform.python_version(), 'platform': platform.platform(),
            'cycles': cycles, 'elapsed_seconds': time.monotonic() - started, 'samples': samples,
            'scope': 'Bounded stress test; memory includes growing move records. Not a physical Windows or multi-hour certification.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cycles', type=int, default=100)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if not 1 <= args.cycles <= 100000:
        parser.error('Use 1–100000 cycles')
    result = run(args.cycles)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(f"Passed {args.cycles} cycles in {result['elapsed_seconds']:.1f}s")
