"""
FEN/EPD Analysis Tools
======================

Tools for analyzing chess positions in FEN (Forsyth-Edwards Notation) and
EPD (Extended Position Description) formats.

These utilities are commonly found in chess programming projects like:
- Stockfish analysis tools
- Chess position databases
- Training position suites (e.g., WAC, Bratko-Kopec, etc.)

FEN is the standard for representing a single chess position.
EPD extends FEN with operations and is used for test suites and analysis.
"""

import chess
from typing import Dict, List, Optional, Tuple
import re


class PositionAnalyzer:
    """
    Analyze chess positions and extract useful information.
    
    Provides analysis capabilities commonly found in chess tools:
    - Material count and imbalance
    - Phase detection (opening/middlegame/endgame)
    - Position classification
    - Piece activity metrics
    """
    
    # Material values in centipawns
    PIECE_VALUES = {
        chess.PAWN: 100,
        chess.KNIGHT: 320,
        chess.BISHOP: 330,
        chess.ROOK: 500,
        chess.QUEEN: 900,
        chess.KING: 0,  # King has no material value
    }
    
    def __init__(self, fen: str = None):
        """
        Initialize analyzer with a position.
        
        Args:
            fen: FEN string (optional, defaults to starting position)
        """
        if fen:
            self.board = chess.Board(fen)
        else:
            self.board = chess.Board()
    
    def set_position(self, fen: str) -> None:
        """Set a new position to analyze."""
        self.board = chess.Board(fen)
    
    def material_count(self, color: chess.Color = None) -> Dict[str, int]:
        """
        Count material for one or both sides.
        
        Args:
            color: chess.WHITE, chess.BLACK, or None (both sides)
            
        Returns:
            Dictionary with piece counts
        """
        if color is not None:
            return {
                'pawns': len(self.board.pieces(chess.PAWN, color)),
                'knights': len(self.board.pieces(chess.KNIGHT, color)),
                'bishops': len(self.board.pieces(chess.BISHOP, color)),
                'rooks': len(self.board.pieces(chess.ROOK, color)),
                'queens': len(self.board.pieces(chess.QUEEN, color)),
                'king': len(self.board.pieces(chess.KING, color)),
            }
        else:
            return {
                'white': self.material_count(chess.WHITE),
                'black': self.material_count(chess.BLACK),
            }
    
    def material_value(self, color: chess.Color) -> int:
        """
        Calculate total material value for a side.
        
        Args:
            color: chess.WHITE or chess.BLACK
            
        Returns:
            Material value in centipawns
        """
        value = 0
        for piece_type in [chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN]:
            count = len(self.board.pieces(piece_type, color))
            value += count * self.PIECE_VALUES[piece_type]
        return value
    
    def material_balance(self) -> int:
        """
        Calculate material balance (positive = white ahead).
        
        Returns:
            Material difference in centipawns
        """
        return self.material_value(chess.WHITE) - self.material_value(chess.BLACK)
    
    def game_phase(self) -> str:
        """
        Determine game phase based on material.
        
        Returns:
            'opening', 'middlegame', or 'endgame'
        """
        # Count total non-pawn pieces
        total_pieces = 0
        for piece_type in [chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN]:
            total_pieces += len(self.board.pieces(piece_type, chess.WHITE))
            total_pieces += len(self.board.pieces(piece_type, chess.BLACK))
        
        # Simple heuristic
        if len(self.board.move_stack) < 10:
            return 'opening'
        elif total_pieces <= 6:
            return 'endgame'
        else:
            return 'middlegame'
    
    def mobility(self, color: chess.Color) -> int:
        """
        Count number of legal moves for a side.
        
        Args:
            color: chess.WHITE or chess.BLACK
            
        Returns:
            Number of legal moves
        """
        if self.board.turn == color:
            return self.board.legal_moves.count()
        else:
            # Temporarily switch turn to count opponent moves
            self.board.push(chess.Move.null())
            count = self.board.legal_moves.count()
            self.board.pop()
            return count
    
    def is_tactical(self) -> bool:
        """
        Check if position appears tactical (checks, captures available).
        
        Returns:
            True if position has tactical characteristics
        """
        if self.board.is_check():
            return True
        
        # Check for available captures
        for move in self.board.legal_moves:
            if self.board.is_capture(move):
                return True
        
        return False
    
    def piece_activity(self, color: chess.Color) -> Dict[str, float]:
        """
        Measure piece activity (how well pieces are placed).
        
        Args:
            color: chess.WHITE or chess.BLACK
            
        Returns:
            Dictionary with activity metrics
        """
        # Count pieces in center squares (d4, d5, e4, e5)
        center_squares = [chess.D4, chess.D5, chess.E4, chess.E5]
        center_control = sum(1 for sq in center_squares if self.board.piece_at(sq) and self.board.piece_at(sq).color == color)
        
        # Count developed pieces (not on back rank)
        back_rank = range(0, 8) if color == chess.WHITE else range(56, 64)
        developed = 0
        total_minor = len(self.board.pieces(chess.KNIGHT, color)) + len(self.board.pieces(chess.BISHOP, color))
        
        for piece_type in [chess.KNIGHT, chess.BISHOP]:
            for square in self.board.pieces(piece_type, color):
                if square not in back_rank:
                    developed += 1
        
        development = developed / max(1, total_minor)
        
        return {
            'center_control': center_control,
            'development': development,
            'mobility': self.mobility(color),
        }
    
    def classify_position(self) -> List[str]:
        """
        Classify the position based on characteristics.
        
        Returns:
            List of classification tags
        """
        tags = []
        
        # Game phase
        tags.append(self.game_phase())
        
        # Material status
        balance = self.material_balance()
        if abs(balance) < 50:
            tags.append('equal')
        elif balance > 50:
            tags.append('white_advantage')
        else:
            tags.append('black_advantage')
        
        # Tactical or positional
        if self.is_tactical():
            tags.append('tactical')
        else:
            tags.append('positional')
        
        # Check status
        if self.board.is_check():
            tags.append('check')
        if self.board.is_checkmate():
            tags.append('checkmate')
        if self.board.is_stalemate():
            tags.append('stalemate')
        
        return tags
    
    def summary(self) -> str:
        """
        Generate a human-readable summary of the position.
        
        Returns:
            Multi-line string with position analysis
        """
        lines = []
        lines.append("=" * 60)
        lines.append("Position Analysis")
        lines.append("=" * 60)
        lines.append(f"FEN: {self.board.fen()}")
        lines.append("")
        
        # Turn
        lines.append(f"Turn: {'White' if self.board.turn else 'Black'}")
        
        # Material
        white_mat = self.material_value(chess.WHITE)
        black_mat = self.material_value(chess.BLACK)
        balance = white_mat - black_mat
        lines.append(f"Material: White {white_mat} - Black {black_mat} (Balance: {balance:+d})")
        
        # Material count
        white_count = self.material_count(chess.WHITE)
        black_count = self.material_count(chess.BLACK)
        lines.append(f"Pieces: W[P:{white_count['pawns']} N:{white_count['knights']} B:{white_count['bishops']} R:{white_count['rooks']} Q:{white_count['queens']}] "
                    f"B[P:{black_count['pawns']} N:{black_count['knights']} B:{black_count['bishops']} R:{black_count['rooks']} Q:{black_count['queens']}]")
        
        # Game phase
        lines.append(f"Phase: {self.game_phase()}")
        
        # Mobility
        white_mob = self.mobility(chess.WHITE)
        black_mob = self.mobility(chess.BLACK)
        lines.append(f"Mobility: White {white_mob} - Black {black_mob}")
        
        # Piece activity
        white_activity = self.piece_activity(chess.WHITE)
        black_activity = self.piece_activity(chess.BLACK)
        lines.append(f"Development: White {white_activity['development']:.1%} - Black {black_activity['development']:.1%}")
        
        # Classification
        tags = self.classify_position()
        lines.append(f"Classification: {', '.join(tags)}")
        
        # Position status
        if self.board.is_checkmate():
            winner = 'Black' if self.board.turn else 'White'
            lines.append(f"Status: Checkmate! {winner} wins.")
        elif self.board.is_stalemate():
            lines.append("Status: Stalemate (draw)")
        elif self.board.is_insufficient_material():
            lines.append("Status: Insufficient material (draw)")
        elif self.board.is_check():
            lines.append("Status: In check")
        else:
            lines.append("Status: Normal")
        
        lines.append("=" * 60)
        
        return "\n".join(lines)


class EPDProcessor:
    """
    Process EPD (Extended Position Description) format.
    
    EPD is used for test suites like:
    - WAC (Win At Chess)
    - Bratko-Kopec Test
    - Strategic Test Suite
    - Tactical positions
    """
    
    def __init__(self):
        """Initialize EPD processor."""
        pass
    
    @staticmethod
    def parse_epd(epd_line: str) -> Tuple[str, Dict[str, str]]:
        """
        Parse an EPD line into FEN and operations.
        
        EPD format: FEN (4 fields) + operations
        Example: "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - bm Bb5; id WAC.001;"
        
        Args:
            epd_line: EPD string
            
        Returns:
            Tuple of (fen, operations_dict)
        """
        # Split into FEN fields and operations
        parts = epd_line.strip().split()
        
        # EPD has 4 FEN fields (no halfmove/fullmove)
        if len(parts) < 4:
            raise ValueError("Invalid EPD: too few fields")
        
        fen = ' '.join(parts[:4]) + ' 0 1'  # Add halfmove and fullmove
        
        # Parse operations
        operations = {}
        if len(parts) > 4:
            ops_str = ' '.join(parts[4:])
            # Parse operations like "bm Bb5; id WAC.001;"
            for op_match in re.finditer(r'(\w+)\s+([^;]+);', ops_str):
                op_code = op_match.group(1)
                op_value = op_match.group(2).strip()
                operations[op_code] = op_value
        
        return fen, operations
    
    @staticmethod
    def load_epd_file(filepath: str) -> List[Tuple[str, Dict[str, str]]]:
        """
        Load positions from an EPD file.
        
        Args:
            filepath: Path to EPD file
            
        Returns:
            List of (fen, operations) tuples
        """
        positions = []
        
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                try:
                    fen, ops = EPDProcessor.parse_epd(line)
                    positions.append((fen, ops))
                except Exception:
                    continue  # Skip invalid lines
        
        return positions


# Demo and testing
if __name__ == '__main__':
    print("\nFEN/EPD Analysis Tools Demo")
    print("=" * 60)
    
    # Analyze starting position
    print("\n1. Starting Position Analysis:")
    analyzer = PositionAnalyzer()
    print(analyzer.summary())
    
    # Analyze a tactical position
    print("\n2. Tactical Position (Scholar's Mate):")
    tactical_fen = "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4"
    analyzer.set_position(tactical_fen)
    print(analyzer.summary())
    
    # EPD parsing example
    print("\n3. EPD Parsing Example:")
    epd = "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - bm Bb5; id Italian.001;"
    fen, ops = EPDProcessor.parse_epd(epd)
    print(f"FEN: {fen}")
    print(f"Best move: {ops.get('bm', 'N/A')}")
    print(f"ID: {ops.get('id', 'N/A')}")
    
    print("\n" + "=" * 60)
    print("FEN/EPD tools ready for use!")
