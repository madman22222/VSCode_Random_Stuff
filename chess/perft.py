"""
Perft (Performance Test) Implementation
========================================

Perft is a standard debugging and testing tool in chess programming, used to verify
the correctness of move generation. It counts the number of leaf nodes at a given depth.

This implementation is based on the standard perft approach used in chess engines like:
- Stockfish (https://github.com/official-stockfish/Stockfish)
- Crafty (https://github.com/MichaelB7/Crafty)
- Ethereal (https://github.com/AndyGrant/Ethereal)
- Fairy-Stockfish (https://github.com/fairy-stockfish/Fairy-Stockfish)

Perft is essential for validating chess move generation, as incorrect move generation
can lead to illegal positions or missed legal moves. The standard positions with known
perft results allow developers to verify their implementations.

Reference results from: https://www.chessprogramming.org/Perft_Results
"""

import chess
from typing import Dict, Tuple
import time


class PerftTester:
    """
    Performance test for chess move generation.
    
    Perft recursively generates all possible moves to a given depth and counts
    the leaf nodes. This is used to verify the correctness of:
    - Legal move generation
    - Check detection
    - Checkmate/stalemate detection
    - Special moves (castling, en passant, promotion)
    
    Standard test positions with known results allow validation against
    other chess engines and implementations.
    """
    
    # Standard perft test positions from chess programming community
    # Format: (FEN, {depth: expected_nodes})
    STANDARD_POSITIONS = {
        "starting": (
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            {
                1: 20,
                2: 400,
                3: 8902,
                4: 197281,
                5: 4865609,
                6: 119060324,
            }
        ),
        "kiwipete": (
            "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
            {
                1: 48,
                2: 2039,
                3: 97862,
                4: 4085603,
                5: 193690690,
            }
        ),
        "position3": (
            "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1",
            {
                1: 14,
                2: 191,
                3: 2812,
                4: 43238,
                5: 674624,
                6: 11030083,
            }
        ),
        "position4": (
            "r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1",
            {
                1: 6,
                2: 264,
                3: 9467,
                4: 422333,
                5: 15833292,
            }
        ),
        "position5": (
            "rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8",
            {
                1: 44,
                2: 1486,
                3: 62379,
                4: 2103487,
                5: 89941194,
            }
        ),
        "position6": (
            "r4rk1/1pp1qppp/p1np1n2/2b1p1B1/2B1P1b1/P1NP1N2/1PP1QPPP/R4RK1 w - - 0 10",
            {
                1: 46,
                2: 2079,
                3: 89890,
                4: 3894594,
                5: 164075551,
            }
        ),
    }
    
    def __init__(self):
        """Initialize the perft tester."""
        self.nodes = 0
        self.captures = 0
        self.en_passants = 0
        self.castles = 0
        self.promotions = 0
        self.checks = 0
        self.checkmates = 0
    
    def perft(self, board: chess.Board, depth: int, root: bool = True) -> int:
        """
        Count leaf nodes at given depth.
        
        Args:
            board: Chess board position
            depth: Depth to search
            root: Whether this is the root call (for divide mode)
            
        Returns:
            Number of leaf nodes at the given depth
        """
        if depth == 0:
            return 1
        
        nodes = 0
        
        for move in board.legal_moves:
            board.push(move)
            
            if depth == 1:
                # Count special moves
                if board.is_capture(move):
                    self.captures += 1
                if move.promotion:
                    self.promotions += 1
                if board.is_en_passant(move):
                    self.en_passants += 1
                if board.is_castling(move):
                    self.castles += 1
                if board.is_check():
                    self.checks += 1
                if board.is_checkmate():
                    self.checkmates += 1
            
            count = self.perft(board, depth - 1, False)
            nodes += count
            
            board.pop()
        
        return nodes
    
    def perft_divide(self, board: chess.Board, depth: int) -> Dict[str, int]:
        """
        Perform perft with divide - show node count for each root move.
        
        This is useful for debugging as it shows which moves contribute
        to the total node count at each depth.
        
        Args:
            board: Chess board position
            depth: Depth to search
            
        Returns:
            Dictionary mapping move (UCI) to node count
        """
        if depth == 0:
            return {}
        
        move_counts = {}
        
        for move in board.legal_moves:
            board.push(move)
            
            if depth == 1:
                count = 1
            else:
                count = self.perft(board, depth - 1, False)
            
            move_counts[move.uci()] = count
            board.pop()
        
        return move_counts
    
    def test_position(
        self, 
        fen: str, 
        depth: int, 
        expected: int = None,
        show_divide: bool = False
    ) -> Tuple[int, float, bool]:
        """
        Test a position at given depth and compare to expected result.
        
        Args:
            fen: FEN string of position to test
            depth: Depth to search
            expected: Expected node count (None to skip validation)
            show_divide: Whether to show per-move breakdown
            
        Returns:
            Tuple of (node_count, time_taken, passed)
        """
        board = chess.Board(fen)
        
        # Reset counters
        self.nodes = 0
        self.captures = 0
        self.en_passants = 0
        self.castles = 0
        self.promotions = 0
        self.checks = 0
        self.checkmates = 0
        
        start_time = time.time()
        
        if show_divide:
            move_counts = self.perft_divide(board, depth)
            nodes = sum(move_counts.values())
            
            print(f"\nDivide at depth {depth}:")
            for move_uci, count in sorted(move_counts.items()):
                print(f"  {move_uci}: {count:,}")
        else:
            nodes = self.perft(board, depth)
        
        elapsed = time.time() - start_time
        
        passed = True
        if expected is not None:
            passed = (nodes == expected)
        
        return nodes, elapsed, passed
    
    def run_standard_tests(self, max_depth: int = 4) -> None:
        """
        Run all standard perft test positions.
        
        Args:
            max_depth: Maximum depth to test (higher is slower)
        """
        print("=" * 70)
        print("Perft Standard Test Suite")
        print("=" * 70)
        print("\nTesting move generation correctness using standard positions")
        print("from the chess programming community.\n")
        
        total_tests = 0
        passed_tests = 0
        failed_tests = []
        
        for name, (fen, expected_results) in self.STANDARD_POSITIONS.items():
            print(f"\n{name.upper()}")
            print(f"FEN: {fen}")
            print("-" * 70)
            
            for depth in sorted(expected_results.keys()):
                if depth > max_depth:
                    continue
                
                total_tests += 1
                expected = expected_results[depth]
                
                nodes, elapsed, passed = self.test_position(fen, depth, expected)
                
                status = "✓ PASS" if passed else "✗ FAIL"
                nps = int(nodes / elapsed) if elapsed > 0 else 0
                
                print(f"  Depth {depth}: {nodes:>12,} nodes in {elapsed:>6.3f}s "
                      f"({nps:>10,} nps) - Expected: {expected:>12,} {status}")
                
                if passed:
                    passed_tests += 1
                else:
                    failed_tests.append((name, depth, nodes, expected))
        
        print("\n" + "=" * 70)
        print(f"Results: {passed_tests}/{total_tests} tests passed")
        
        if failed_tests:
            print("\nFailed tests:")
            for name, depth, actual, expected in failed_tests:
                print(f"  {name} depth {depth}: got {actual:,}, expected {expected:,}")
        else:
            print("All tests passed! Move generation is correct. ✓")
        
        print("=" * 70)


def run_perft_demo():
    """Demonstrate perft functionality."""
    tester = PerftTester()
    
    print("\nPerft (Performance Test) Demo")
    print("=" * 70)
    print("\nPerft is a standard tool from chess programming used to verify")
    print("move generation correctness. It counts leaf nodes at each depth.\n")
    
    # Quick test of starting position
    print("Testing starting position at depth 1-3...")
    board = chess.Board()
    
    for depth in range(1, 4):
        nodes, elapsed, _ = tester.test_position(board.fen(), depth)
        nps = int(nodes / elapsed) if elapsed > 0 else 0
        print(f"  Depth {depth}: {nodes:,} nodes in {elapsed:.3f}s ({nps:,} nps)")
    
    print("\nFor full validation, run: python perft.py --test")


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--test':
        # Run full test suite
        tester = PerftTester()
        max_depth = 4 if len(sys.argv) < 3 else int(sys.argv[2])
        tester.run_standard_tests(max_depth)
    else:
        # Just show a demo
        run_perft_demo()
        print("\nUsage:")
        print("  python perft.py           - Quick demo")
        print("  python perft.py --test    - Run full test suite (depth 4)")
        print("  python perft.py --test 5  - Run full test suite at depth 5")
