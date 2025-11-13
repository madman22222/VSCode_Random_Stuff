"""
Tests for perft and FEN analyzer modules.
"""

import unittest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chess
from perft import PerftTester
from fen_analyzer import PositionAnalyzer, EPDProcessor


class TestPerft(unittest.TestCase):
    """Test perft move generation validation."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.tester = PerftTester()
    
    def test_starting_position_depth1(self):
        """Test perft depth 1 from starting position."""
        board = chess.Board()
        nodes, _, passed = self.tester.test_position(board.fen(), 1, 20)
        self.assertEqual(nodes, 20)
        self.assertTrue(passed)
    
    def test_starting_position_depth2(self):
        """Test perft depth 2 from starting position."""
        board = chess.Board()
        nodes, _, passed = self.tester.test_position(board.fen(), 2, 400)
        self.assertEqual(nodes, 400)
        self.assertTrue(passed)
    
    def test_kiwipete_position(self):
        """Test perft on famous kiwipete position."""
        fen = "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1"
        nodes, _, passed = self.tester.test_position(fen, 1, 48)
        self.assertEqual(nodes, 48)
        self.assertTrue(passed)
    
    def test_perft_divide(self):
        """Test perft divide mode."""
        board = chess.Board()
        move_counts = self.tester.perft_divide(board, 1)
        
        # Should have 20 moves from starting position
        self.assertEqual(len(move_counts), 20)
        
        # Each move at depth 1 should count as 1 node
        for move, count in move_counts.items():
            self.assertEqual(count, 1)


class TestPositionAnalyzer(unittest.TestCase):
    """Test position analysis functionality."""
    
    def test_starting_position_material(self):
        """Test material count in starting position."""
        analyzer = PositionAnalyzer()
        
        white = analyzer.material_count(chess.WHITE)
        self.assertEqual(white['pawns'], 8)
        self.assertEqual(white['knights'], 2)
        self.assertEqual(white['bishops'], 2)
        self.assertEqual(white['rooks'], 2)
        self.assertEqual(white['queens'], 1)
        
        black = analyzer.material_count(chess.BLACK)
        self.assertEqual(black['pawns'], 8)
        self.assertEqual(black['knights'], 2)
    
    def test_material_balance(self):
        """Test material balance calculation."""
        analyzer = PositionAnalyzer()
        
        # Starting position should be balanced
        balance = analyzer.material_balance()
        self.assertEqual(balance, 0)
        
        # Position with white ahead by a pawn (removed one black pawn)
        analyzer.set_position("rnbqkbnr/ppppppp1/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
        balance = analyzer.material_balance()
        self.assertEqual(balance, 100)  # White up a pawn
    
    def test_game_phase_detection(self):
        """Test game phase detection."""
        # Starting position should be opening
        analyzer = PositionAnalyzer()
        self.assertEqual(analyzer.game_phase(), 'opening')
        
        # Endgame position (few pieces) - need to simulate moves to get past opening phase
        endgame_fen = "8/8/4k3/8/8/4K3/8/8 w - - 0 50"  # Set halfmove to simulate late game
        analyzer.set_position(endgame_fen)
        # Manually push some null moves to get past opening phase
        for _ in range(10):
            analyzer.board.move_stack.append(chess.Move.null())
        self.assertEqual(analyzer.game_phase(), 'endgame')
    
    def test_mobility_count(self):
        """Test mobility counting."""
        analyzer = PositionAnalyzer()
        
        # Starting position: white has 20 moves
        white_mobility = analyzer.mobility(chess.WHITE)
        self.assertEqual(white_mobility, 20)
        
        # Black also has 20 moves in starting position
        black_mobility = analyzer.mobility(chess.BLACK)
        self.assertEqual(black_mobility, 20)
    
    def test_is_tactical(self):
        """Test tactical position detection."""
        # Starting position is not tactical (no captures or checks)
        analyzer = PositionAnalyzer()
        self.assertFalse(analyzer.is_tactical())
        
        # Position with actual captures available (after e4 e5 Nf3 Nc6 Bc4 Nf6)
        # where multiple captures are possible
        analyzer.set_position("r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4")
        self.assertTrue(analyzer.is_tactical())
    
    def test_classify_position(self):
        """Test position classification."""
        analyzer = PositionAnalyzer()
        tags = analyzer.classify_position()
        
        # Starting position should be: opening, equal, positional
        self.assertIn('opening', tags)
        self.assertIn('equal', tags)
        self.assertIn('positional', tags)


class TestEPDProcessor(unittest.TestCase):
    """Test EPD format processing."""
    
    def test_parse_basic_epd(self):
        """Test parsing basic EPD string."""
        epd = "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq -"
        fen, ops = EPDProcessor.parse_epd(epd)
        
        # Should extract FEN correctly
        self.assertIn("r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R", fen)
        self.assertIn("w KQkq", fen)
    
    def test_parse_epd_with_operations(self):
        """Test parsing EPD with operations."""
        epd = "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - bm Bb5; id Test.001;"
        fen, ops = EPDProcessor.parse_epd(epd)
        
        # Should extract operations
        self.assertIn('bm', ops)
        self.assertEqual(ops['bm'], 'Bb5')
        self.assertIn('id', ops)
        self.assertEqual(ops['id'], 'Test.001')
    
    def test_epd_creates_valid_board(self):
        """Test that parsed EPD creates valid chess board."""
        epd = "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - bm Bb5;"
        fen, _ = EPDProcessor.parse_epd(epd)
        
        # Should be able to create a valid board
        board = chess.Board(fen)
        self.assertIsNotNone(board)
        self.assertTrue(board.is_valid())


if __name__ == '__main__':
    unittest.main()
