"""Measure draw-check guards without claiming improved chess strength."""
import argparse
import json
from pathlib import Path
import random
import statistics
import sys
import time
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'chess'))
import chess
from simple_ai import SimpleAI
from search_rules import search_outcome


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    randomizer = random.Random(2026)
    board = chess.Board()
    for _ in range(400):
        assert search_outcome(board) == board.outcome(claim_draw=True)
        if board.is_game_over(claim_draw=True):
            board = chess.Board()
        board.push(randomizer.choice(list(board.legal_moves)))
    report = {'scope': 'Same draw policy; reference calls full python-chess outcome at every search node. '
                        'Five untraced runs per position, fixed depth/node budget, same machine.',
              'semantic_checks': 400, 'results': []}
    for case in json.loads(Path(__file__).with_name('positions.json').read_text())['positions']:
        row = {'id': case['id']}
        for mode in ('reference', 'guarded'):
            timings = []
            checker = (lambda board: board.outcome(claim_draw=True)) if mode == 'reference' else search_outcome
            for _ in range(5):
                ai = SimpleAI(depth=3, load_learning=False)
                with patch('simple_ai.search_outcome', checker):
                    start = time.perf_counter()
                    ai.choose_move_iterative(chess.Board(case['fen']), 30, record=False, node_limit=1000)
                    timings.append(time.perf_counter() - start)
            row[mode] = {'median_seconds': statistics.median(timings), 'samples_seconds': timings,
                         'move': ai.last_move_metrics['move'], 'nodes': ai.nodes_searched}
        assert row['reference']['move'] == row['guarded']['move']
        assert row['reference']['nodes'] == row['guarded']['nodes']
        report['results'].append(row)
    Path(args.output).write_text(json.dumps(report, indent=2) + '\n')
    print([(r['id'], round(r['reference']['median_seconds'], 4), round(r['guarded']['median_seconds'], 4))
           for r in report['results']])


if __name__ == '__main__':
    main()
