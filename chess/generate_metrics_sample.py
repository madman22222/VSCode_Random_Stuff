"""Generate a short metrics sample CSV for CI artifact.
Runs a handful of SimpleAI self-play moves to populate metrics.
"""
from __future__ import annotations
import csv, time
import chess
from simple_ai import SimpleAI

def main():
    board = chess.Board()
    ai = SimpleAI(depth=2)
    history = []
    max_moves = 8
    while not board.is_game_over() and len(history) < max_moves:
        mv = ai.choose_move_iterative(board, time_limit=0.15)
        if mv is None:
            break
        board.push(mv)
        history.append(ai.last_move_metrics if hasattr(ai, 'last_move_metrics') else {})
    path = 'metrics_sample.csv'
    keys = ['move','depth','nodes','branching','time','source']
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(keys)
        for row in history:
            w.writerow([row.get(k) for k in keys])
    print(f"Wrote metrics sample with {len(history)} moves to {path}")

if __name__ == '__main__':
    main()
