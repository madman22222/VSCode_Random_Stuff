import unittest
import os
import importlib.util

# load chess/main.py as a module without importing as a package
THIS_DIR = os.path.dirname(__file__)
MAIN_PY = os.path.join(THIS_DIR, '..', 'main.py')
spec = importlib.util.spec_from_file_location('chess_main', os.path.abspath(MAIN_PY))
assert spec is not None
assert spec.loader is not None
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

SimpleAI = mod.SimpleAI
import chess


class TestSpecialMoves(unittest.TestCase):
    def test_promotion_prefers_queen(self):
        # white pawn on a7, white to move -> should promote to queen
        fen = '8/P7/8/8/8/8/8/k6K w - - 0 1'
        board = chess.Board(fen)
        ai = SimpleAI(depth=1)
        mv = ai.choose_move(board)
        self.assertIsNotNone(mv, 'AI did not return a move for promotion position')
        self.assertIsNotNone(mv.promotion, 'AI move is not a promotion')
        self.assertEqual(mv.promotion, chess.QUEEN, 'AI did not prefer queen promotion')

    def test_en_passant_capture(self):
        # white pawn on e5, black pawn moved d7-d5 leaving ep target d6; white to move
        fen = '7k/8/8/3pP3/8/8/8/K7 w - d6 0 1'
        board = chess.Board(fen)
        ai = SimpleAI(depth=1)
        mv = ai.choose_move(board)
        self.assertIsNotNone(mv, 'AI did not return a move for en-passant position')
        # move should be en-passant capture to d6
        self.assertTrue(board.is_en_passant(mv), f'Move {mv} is not recognized as en-passant')

    def test_castling_score_bonus(self):
        # position with castling rights and empty between squares
        fen = 'r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1'
        board = chess.Board(fen)
        ai = SimpleAI(depth=1)
        # find a castling move and a quiet pawn move and ensure castling has higher score
        castling_moves = []
        for m in board.legal_moves:
            p = board.piece_at(m.from_square)
            if p is not None and p.piece_type == chess.KING and abs(chess.square_file(m.from_square) - chess.square_file(m.to_square)) == 2:
                castling_moves.append(m)
        self.assertTrue(len(castling_moves) >= 1, 'No castling moves found in test position')
        # pick a non-castling move (first found non-king move)
        other_moves = []
        for m in board.legal_moves:
            p = board.piece_at(m.from_square)
            if p is None or p.piece_type != chess.KING:
                other_moves.append(m)
        self.assertTrue(len(other_moves) >= 1, 'No non-castling moves found')
        cast_score = ai._move_score(board, castling_moves[0])
        other_score = ai._move_score(board, other_moves[0])
        self.assertGreaterEqual(cast_score, other_score, 'Castling move did not have higher or equal heuristic score')


if __name__ == '__main__':
    unittest.main()
