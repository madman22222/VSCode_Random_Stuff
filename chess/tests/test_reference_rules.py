"""Representative material checks, game conclusions, and exact search-draw semantics."""
import io
import json
from pathlib import Path
import random
import unittest
from unittest.mock import Mock, patch
import chess
import chess.pgn
from chess_clock import ChessClock
from game_endings import timeout_conclusion
from search_rules import search_outcome
from simple_ai import SimpleAI


class ReferenceRules(unittest.TestCase):
    def test_setup_and_special_move_boundaries(self):
        board = chess.Board()
        self.assertEqual(board.piece_at(chess.D1).piece_type, chess.QUEEN)
        self.assertEqual(board.piece_at(chess.D8).piece_type, chess.QUEEN)
        self.assertNotIn(chess.Move.from_uci('e2e5'), board.legal_moves)
        for fen, move, legal in (
                ('r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1', 'e1c1', True),
                ('r3k2r/8/8/8/8/8/5r2/R3K2R w KQkq - 0 1', 'e1g1', False),
                ('r3k2r/8/8/8/8/8/7r/R3K2R w KQkq - 0 1', 'e1g1', True),
                ('r3k2r/8/8/8/8/8/8/R3K2R w - - 0 1', 'e1g1', False)):
            board = chess.Board(fen)
            self.assertEqual(chess.Move.from_uci(move) in board.legal_moves, legal)
        board = chess.Board('7k/8/8/3pP3/8/8/8/K7 w - d6 0 1')
        self.assertTrue(board.is_en_passant(board.parse_san('exd6')))
        board.push_san('Kb1')
        board.push_san('Kh7')
        self.assertFalse(board.has_legal_en_passant())

    def test_promotions_and_mate_vs_stalemate(self):
        board = chess.Board('7k/P7/8/8/8/8/8/7K w - - 0 1')
        self.assertEqual({m.promotion for m in board.legal_moves if m.from_square == chess.A7},
                         {chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT})
        self.assertTrue(chess.Board('7k/6Q1/5K2/8/8/8/8/8 b - - 0 1').is_checkmate())
        self.assertTrue(chess.Board('7k/5Q2/6K1/8/8/8/8/8 b - - 0 1').is_stalemate())
        self.assertFalse(chess.Board('7k/8/8/8/8/8/NN6/K7 w - - 0 1').is_insufficient_material())
        double = chess.Board('4k3/8/8/1B6/8/8/8/4R1K1 b - - 0 1')
        self.assertEqual(len(double.checkers()), 2)
        self.assertTrue(all(m.from_square == double.king(double.turn) for m in double.legal_moves))

    def test_timeout_draw_depends_on_the_nonflagging_side(self):
        board = chess.Board('7k/8/8/8/8/8/R7/K7 w - - 0 1')
        self.assertIsNone(timeout_conclusion(board, chess.WHITE).winner)
        self.assertEqual(timeout_conclusion(board, chess.BLACK).winner, chess.WHITE)

    def test_increment_does_not_resurrect_a_flag_and_callback_is_once(self):
        callback, root = Mock(), Mock()
        clock = ChessClock(white_time=.1, increment=5, on_timeout=callback)
        with patch('chess_clock.time.monotonic', return_value=0) as now:
            clock.start(root)
            now.return_value = .2
            clock.switch()
            self.assertEqual(clock.white_time, 0)
            self.assertFalse(clock.running)
            clock.check_timeout()
        callback.assert_called_once_with(True)

    def test_search_outcome_matches_reference_including_prospective_claim(self):
        rng = random.Random(2026)
        board = chess.Board()
        for _ in range(400):
            self.assertEqual(search_outcome(board), board.outcome(claim_draw=True), board.fen())
            if board.is_game_over(claim_draw=True):
                board = chess.Board()
            board.push(rng.choice(list(board.legal_moves)))
        board = chess.Board()
        for uci in ('g1f3','g8f6','f3g1','f6g8','g1f3','g8f6','f3g1'):
            board.push_uci(uci)
        self.assertEqual(search_outcome(board).termination, chess.Termination.THREEFOLD_REPETITION)
        board = chess.Board()
        for uci in ('g1f3','g8f6','f3g1','f6g8') * 4:
            board.push_uci(uci)
        self.assertEqual(search_outcome(board).termination, chess.Termination.FIVEFOLD_REPETITION)
        self.assertEqual(search_outcome(chess.Board('7k/6Q1/5K2/8/8/8/8/8 b - - 150 100')).winner, chess.WHITE)
        for halfmoves in (98,99,100,149,150):
            board = chess.Board(f'7k/8/8/8/8/8/R7/K7 w - - {halfmoves} 100')
            self.assertEqual(search_outcome(board), board.outcome(claim_draw=True))

    def test_quiescence_claims_draw_without_changing_board(self):
        board = chess.Board('7k/8/8/8/8/8/R7/K7 w - - 100 100')
        before = board.fen()
        self.assertEqual(SimpleAI(load_learning=False).quiescence(board, -10000, 10000), 0)
        self.assertEqual(board.fen(), before)

    def test_representative_course_notation_replays_legally(self):
        # Factual move sequences from supplied TacticsCourse PDF pp.10–13.
        games = (
            '1.e4 e5 2.Nf3 d6 3.d4 Nd7 4.Bc4 h6 5.Nc3 c6 6.dxe5 dxe5 7.O-O Bd6 8.Qxd6 Qf6 9.Rd1 1-0',
            '1.e4 e5 2.Nf3 f5 3.Nc3 fxe4 4.Nxe5 Qf6 5.d4 exd3 6.Nxd3 Qe6+ 7.Qe2 Qxe2+ 8.Bxe2 Bb4 9.Nxb4 1-0',
            '1.e4 e5 2.Nf3 Nf6 3.Bc4 d6 4.Nc3 g6 5.Ng5 Be6 6.Bxe6 fxe6 7.Nxe6 Qe7 8.Nb5 Nxe4 9.Nexc7+ 1-0')
        for text in games:
            game = chess.pgn.read_game(io.StringIO(text))
            self.assertFalse(game.errors)
            self.assertTrue(game.end().board().is_valid())

    def test_vscode_gui_uses_the_shared_entry_point(self):
        root = Path(__file__).resolve().parents[2]
        launch = json.loads((root / '.vscode/launch.json').read_text())
        self.assertEqual(launch['configurations'][0]['program'], '${workspaceFolder}/chess/main.py')
        self.assertEqual(launch['configurations'][0]['cwd'], '${workspaceFolder}')


    def test_original_motif_pack_demonstrates_its_stated_tactics(self):
        from puzzle_packs import load_pack
        puzzles = load_pack(Path(__file__).resolve().parents[1] / 'assets/puzzles/reference-themes.json')
        for puzzle in puzzles:
            board = chess.Board(puzzle.fen)
            self.assertTrue(board.is_valid())
            move = chess.Move.from_uci(puzzle.solutions[0])
            self.assertTrue(puzzle.accepts(board, move))
            board.push(move)
            if puzzle.id.endswith(':absolute-pin'):
                self.assertTrue(board.is_pinned(chess.BLACK, chess.C6))
            else:
                self.assertTrue(board.is_check())
            if puzzle.id.endswith(':knight-fork'):
                self.assertIn(chess.C7, board.attacks(chess.D5))
            if puzzle.id.endswith(':rook-skewer'):
                self.assertNotIn(chess.Move.from_uci('d7c6'), board.legal_moves)
                for reply in list(board.legal_moves):
                    after = board.copy()
                    after.push(reply)
                    self.assertIn(chess.E8, after.attacks(chess.C6))
