"""Reproducible workloads, machine metadata, bounded search and optional UI redraws."""
import argparse
import json
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time
import tracemalloc
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'chess'))
from data_validation import validated_fen
from simple_ai import SimpleAI


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--nodes', type=int, default=2000)
    parser.add_argument('--redraw', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.repeats <= 100 or args.nodes < 1:
        parser.error('Use 1–100 repeats and positive nodes')
    corpus = json.loads(Path(__file__).with_name('positions.json').read_text())
    report = {'version': 1, 'revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
              'worktree_dirty': bool(subprocess.check_output(['git', 'status', '--porcelain'], text=True).strip()),
              'python': platform.python_version(), 'platform': platform.platform(),
              'processor': platform.processor(), 'node_limit': args.nodes, 'depth': 3,
              'corpus_version': corpus['version'], 'results': []}
    for item in corpus['positions']:
        times, peaks, last = [], [], {}
        for _ in range(args.repeats):
            ai = SimpleAI(depth=3, load_learning=False)
            board = validated_fen(item['fen'])
            tracemalloc.start()
            start = time.perf_counter()
            ai.choose_move_iterative(board, 5, record=False, node_limit=args.nodes)
            times.append(time.perf_counter() - start)
            peaks.append(tracemalloc.get_traced_memory()[1])
            tracemalloc.stop()
            last = ai.last_move_metrics
        report['results'].append(dict(item, median_seconds=statistics.median(times),
                                      peak_bytes=max(peaks), samples_seconds=times, metrics=last))
    if args.redraw:
        import tkinter as tk
        from config_manager import ConfigManager
        from game_controller import GameController
        import tempfile
        with tempfile.TemporaryDirectory() as temp:
            root = tk.Tk()
            app = GameController(root, ConfigManager(str(Path(temp) / 'config.json')))
            root.update()
            samples = []
            for _ in range(args.repeats):
                start = time.perf_counter()
                for _ in range(200):
                    app.board_view.update(app.board, app.piece_images)
                root.update_idletasks()
                samples.append(time.perf_counter() - start)
            report['redraw_200_median_seconds'] = statistics.median(samples)
            app.on_close()
    Path(args.output).write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(args.output)


if __name__ == '__main__':
    main()
