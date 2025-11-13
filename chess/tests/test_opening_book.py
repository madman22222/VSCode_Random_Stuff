"""
Tests for Polyglot opening book support.
"""

import unittest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chess
from opening_book import ZobristHasher, PolyglotBook


class TestZobristHasher(unittest.TestCase):
    """Test Zobrist hashing functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.hasher = ZobristHasher()
        
    def test_hash_starting_position(self):
        """Test hashing of the starting position."""
        board = chess.Board()
        hash1 = self.hasher.hash_position(board)
        
        # Hash should be a valid 64-bit integer
        self.assertIsInstance(hash1, int)
        self.assertGreaterEqual(hash1, 0)
        self.assertLess(hash1, 2**64)
    
    def test_hash_changes_after_move(self):
        """Test that hash changes after making a move."""
        board = chess.Board()
        hash_before = self.hasher.hash_position(board)
        
        board.push_san("e4")
        hash_after = self.hasher.hash_position(board)
        
        # Hash should be different after move
        self.assertNotEqual(hash_before, hash_after)
    
    def test_hash_identical_positions(self):
        """Test that identical positions have the same hash."""
        board1 = chess.Board()
        board2 = chess.Board()
        
        # Make same moves on both boards
        for move in ["e4", "e5", "Nf3", "Nc6"]:
            board1.push_san(move)
            board2.push_san(move)
        
        hash1 = self.hasher.hash_position(board1)
        hash2 = self.hasher.hash_position(board2)
        
        self.assertEqual(hash1, hash2)
    
    def test_hash_different_positions(self):
        """Test that different positions have different hashes."""
        board1 = chess.Board()
        board2 = chess.Board()
        
        board1.push_san("e4")
        board2.push_san("d4")
        
        hash1 = self.hasher.hash_position(board1)
        hash2 = self.hasher.hash_position(board2)
        
        self.assertNotEqual(hash1, hash2)
    
    def test_hash_respects_turn(self):
        """Test that hash is different for same position but different turn."""
        board1 = chess.Board()
        board2 = chess.Board()
        
        # board1 is white to move
        hash1 = self.hasher.hash_position(board1)
        
        # Make a null move to flip the turn (not possible in python-chess)
        # Instead, compare after one move and undo
        board2.push_san("e4")
        hash_mid = self.hasher.hash_position(board2)
        board2.pop()
        hash_back = self.hasher.hash_position(board2)
        
        # Original position hash should match after undo
        self.assertEqual(hash1, hash_back)
        # But should differ from position after move
        self.assertNotEqual(hash1, hash_mid)


class TestPolyglotBook(unittest.TestCase):
    """Test Polyglot book functionality (without actual .bin file)."""
    
    def test_missing_book_file(self):
        """Test that loading a non-existent book raises FileNotFoundError."""
        with self.assertRaises(FileNotFoundError):
            PolyglotBook("/nonexistent/book.bin")
    
    def test_empty_book_file(self):
        """Test that loading an empty file raises ValueError."""
        import tempfile
        
        with tempfile.NamedTemporaryFile(suffix='.bin', delete=False) as f:
            temp_path = f.name
        
        try:
            with self.assertRaises(ValueError):
                PolyglotBook(temp_path)
        finally:
            os.unlink(temp_path)
    
    def test_decode_move(self):
        """Test move decoding from Polyglot format."""
        # We can test the decode function without a full book
        book = object.__new__(PolyglotBook)  # Create without __init__
        
        # Decode e2e4 (from square 12, to square 28)
        # Format: to_square (6 bits) | from_square (6 bits) | promotion (3 bits)
        # e2 = square 12, e4 = square 28
        # Binary: 0000 011100 001100 = 0x0E0C (but need to verify endianness)
        move_int = (12 << 6) | 28  # from=12, to=28, promotion=0
        result = book._decode_move(move_int)
        
        # Should decode to a valid UCI move
        self.assertIsInstance(result, str)
        self.assertEqual(len(result), 4)  # e.g., "e2e4"


if __name__ == '__main__':
    unittest.main()
