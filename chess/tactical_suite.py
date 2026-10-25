"""Small hand-built tactical regressions, also used for guided practice."""
from dataclasses import dataclass
import argparse
import json
import chess


@dataclass(frozen=True)
class Puzzle:
    id: str
    title: str
    fen: str
    goal: str
    hints: tuple
    def accepts(self, board, move):
        if move not in board.legal_moves:
            return False
        after = board.copy()
        after.push(move)
        if self.goal == 'mate':
            return after.is_checkmate()
        if self.goal == 'queen':
            victim = board.piece_at(move.to_square)
            return victim is not None and victim.piece_type == chess.QUEEN
        if self.goal == 'promotion':
            return move.promotion == chess.QUEEN
        if self.goal == 'escape':
            return board.is_check() and not after.is_attacked_by(after.turn, after.king(board.turn))
        if self.goal == 'save_queen':
            queens = after.pieces(chess.QUEEN, board.turn)
            return bool(queens) and not any(m.to_square in queens for m in after.legal_moves)
        if self.goal == 'stop_mate':
            for reply in list(after.legal_moves):
                after.push(reply)
                mate = after.is_checkmate()
                after.pop()
                if mate:
                    return False
            return True
        return False


PUZZLES = (
    Puzzle('mate-white', 'Mate in one', '7k/8/5KQ1/8/8/8/8/8 w - - 0 1', 'mate',
           ('Use the queen to close the escape squares.', 'The king supports a queen placed on g7.', 'Try Qg7#.')),
    Puzzle('mate-black', 'Mate in one as Black', '8/8/8/8/8/5kq1/8/7K b - - 0 1', 'mate',
           ('Black has the move.', 'The black king supports g2.', 'Try Qg2#.')),
    Puzzle('free-queen', 'Win the queen', '6k1/8/8/3q4/4P3/8/8/6K1 w - - 0 1', 'queen',
           ('Pawns capture diagonally.', 'The pawn on e4 attacks d5.', 'Try exd5.')),
    Puzzle('promotion', 'Promote safely', '1b5k/P7/8/8/8/8/8/7K w - - 0 1', 'promotion',
           ('Your pawn is one step from promotion.', 'Move from a7 to a8.', 'Promote to a queen.')),
    Puzzle('escape-check', 'Escape the check', '4r1k1/8/8/8/8/8/8/R3K3 w - - 0 1', 'escape',
           ('The rook attacks down the e-file.', 'Move your king off that file.', 'Kd1 is one legal escape.')),
    Puzzle('save-queen', 'Save your queen', 'rk6/8/8/8/8/8/8/Q5K1 w - - 0 1', 'save_queen',
           ('The rook attacks your queen along the a-file.', 'Capturing the rook lets its king recapture.', 'Move the queen off the a-file, for example Qe5+.')),
    Puzzle('stop-mate', 'Prevent mate in one', '4r1k1/8/8/8/7q/8/P5PP/3Q1RK1 w - - 0 1', 'stop_mate',
           ('Black threatens Qxh2#.', 'A pawn move can change the escape squares and attack the queen.', 'Look at g3.')),
)


def run_suite(ai, depth=2, nodes=12000):
    rows = []
    for puzzle in PUZZLES:
        board = chess.Board(puzzle.fen)
        engine = ai.fork()
        engine.depth = depth
        move = engine.choose_move_iterative(board, 10, record=False, node_limit=nodes)
        rows.append({'id': puzzle.id, 'passed': bool(move and puzzle.accepts(board, move)),
                     'move': move.uci() if move else None, 'depth': engine.last_move_metrics.get('depth', 0),
                     'nodes': engine.nodes_searched})
    return {'passed': sum(row['passed'] for row in rows), 'total': len(rows), 'positions': rows}


if __name__ == '__main__':
    from simple_ai import SimpleAI
    parser = argparse.ArgumentParser()
    parser.add_argument('--depth', type=int, default=2)
    parser.add_argument('--nodes', type=int, default=12000)
    args = parser.parse_args()
    report = run_suite(SimpleAI(load_learning=False), args.depth, args.nodes)
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report['passed'] == report['total'] else 1)
