"""
Chess Game Controller with AI Learning
======================================

This module provides a complete chess GUI application with:
- Built-in AI with advanced search (PVS, LMR, aspiration windows, killer/history heuristics)
- Persistent learning system that improves move ordering based on game outcomes
- Human-readable learning export and import
- Support for external engines (Stockfish)
- Multiple game modes: Player vs Player, Player vs AI, AI vs AI
- Themes, sound effects, chess clock, and game statistics
- PGN save/load functionality

Architecture:
- SimpleAI: Chess engine with evaluation, search algorithms, and learning
- GameController: GUI coordinator handling user input, AI threading, and UI updates
- BoardView: Visual chess board with drag-drop and animations
- ConfigManager, SoundManager, ChessClock: Optional feature modules
"""

import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Optional
import chess  # type: ignore - Python-chess library handles all chess rules (legal moves, check, checkmate, castling, en passant, etc.)
import chess.pgn  # type: ignore - For saving/loading games in PGN format
import chess.engine  # type: ignore - For interfacing with external UCI engines like Stockfish
import threading  # For running AI search in background without freezing UI
import time
import shutil
import os
import random

# Optional: PIL for loading custom piece images
try:
    from PIL import Image, ImageTk  # type: ignore
except Exception:
    from typing import Any
    Image: Any = None
    ImageTk: Any = None

# Core components
from engine_manager import EngineManager  # Manages external UCI chess engines
from board_view import BoardView  # Visual chess board widget
from constants import PIECE_UNICODE, THEMES  # Unicode pieces and color themes
import image_generator  # Fallback piece image generation

# Optional upgrade modules (gracefully degrade if not present)
try:
    from config_manager import ConfigManager  # Persistent settings and statistics
    from sound_manager import SoundManager  # Sound effects for moves
    from chess_clock import ChessClock  # Chess clock with time controls
    HAS_UPGRADES = True
except ImportError:
    HAS_UPGRADES = False
    ConfigManager = None  # type: ignore
    SoundManager = None  # type: ignore
    ChessClock = None  # type: ignore

# Polyglot opening book support (optional)
try:
    from opening_book import PolyglotBook
    HAS_POLYGLOT = True
except ImportError:
    HAS_POLYGLOT = False
    PolyglotBook = None  # type: ignore


class Tooltip:
    """Simple tooltip for Tk widgets."""
    def __init__(self, widget: tk.Widget, text: str, delay_ms: int = 400):
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self._after_id: 'Optional[str]' = None
        self._tip: 'Optional[tk.Toplevel]' = None
        try:
            widget.bind('<Enter>', self._on_enter)
            widget.bind('<Leave>', self._on_leave)
        except Exception:
            pass

    def _on_enter(self, _evt=None):
        try:
            self._after_id = self.widget.after(self.delay_ms, self._show)
        except Exception:
            pass

    def _on_leave(self, _evt=None):
        try:
            if self._after_id:
                self.widget.after_cancel(self._after_id)
                self._after_id = None
            if self._tip:
                self._tip.destroy()
                self._tip = None
        except Exception:
            pass

    def _show(self):
        try:
            if self._tip is not None:
                return
            x = self.widget.winfo_rootx() + 20
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 8
            tip = tk.Toplevel(self.widget)
            tip.wm_overrideredirect(True)
            tip.geometry(f"+{x}+{y}")
            lbl = tk.Label(tip, text=self.text, justify='left',
                           background='#FFFFE0', relief='solid', borderwidth=1,
                           font=('Arial', 9))
            lbl.pack(ipadx=6, ipady=3)
            self._tip = tip
        except Exception:
            pass


class SimpleAI:
    """
    Advanced Chess AI with Learning Capability
    ==========================================
    
    This AI combines traditional chess engine techniques with a lightweight learning system:
    
    Search Algorithms:
    - Negamax with alpha-beta pruning (minimax for zero-sum games)
    - Principal Variation Search (PVS): null-window searches for non-PV nodes
    - Late Move Reductions (LMR): reduce search depth for unlikely moves
    - Quiescence search: extend search at leaf nodes to avoid horizon effect
    - Iterative deepening with aspiration windows: gradually increase depth with narrow search windows
    - Transposition table: cache position evaluations with bound flags (EXACT/LOWER/UPPER)
    
    Move Ordering (critical for pruning efficiency):
    - Transposition table best move (highest priority)
    - Killer moves: non-capture moves that caused beta cutoffs at same depth
    - History heuristic: moves that historically caused cutoffs
    - MVV-LVA for captures: Most Valuable Victim - Least Valuable Attacker
    - Learned preference bonus: small bias from past game outcomes
    
    Evaluation Function:
    - Material counting with piece values
    - Piece-square tables (positional bonuses)
    - King safety (different for middlegame vs endgame)
    - Mobility (number of legal moves)
    - Pawn structure analysis
    - Bishop pair bonus
    - Tapered evaluation (smooth transition from opening to endgame)
    
    Learning System:
    - Records each chosen root move with (position_fen, move_uci, color_to_move)
    - On game end, updates win/loss/draw counts per (position, move) pair
    - Persists to ai_learn.json for incremental improvement across sessions
    - Exports human-readable ai_learn_readable.json with winrates and ordering bonuses
    - Small learned bonus (+/- 100 range) added to move ordering (doesn't override evaluation)
    - Works in all game modes including AI vs AI self-play
    
    The python-chess library ensures all moves follow official FIDE rules.
    """
    
    # Material values in centipawns (1 pawn = 100)
    PIECE_VALUES = {
        chess.PAWN: 100,
        chess.KNIGHT: 320,
        chess.BISHOP: 330,
        chess.ROOK: 500,
        chess.QUEEN: 900,
        chess.KING: 20000,
    }
    
    # Piece-Square Tables (positional bonuses/penalties for each square)
    # These encourage pieces to occupy strong squares (e.g., pawns advance, knights centralize)
    # Values are for white's perspective; flipped for black pieces
    # Piece-Square Tables (values for white, flipped for black)
    PAWN_TABLE = [
        0,  0,  0,  0,  0,  0,  0,  0,
        50, 50, 50, 50, 50, 50, 50, 50,
        10, 10, 20, 30, 30, 20, 10, 10,
        5,  5, 10, 27, 27, 10,  5,  5,
        0,  0,  0, 25, 25,  0,  0,  0,
        5, -5,-10,  0,  0,-10, -5,  5,
        5, 10, 10,-25,-25, 10, 10,  5,
        0,  0,  0,  0,  0,  0,  0,  0
    ]
    
    KNIGHT_TABLE = [
        -50,-40,-30,-30,-30,-30,-40,-50,
        -40,-20,  0,  0,  0,  0,-20,-40,
        -30,  0, 10, 15, 15, 10,  0,-30,
        -30,  5, 15, 20, 20, 15,  5,-30,
        -30,  0, 15, 20, 20, 15,  0,-30,
        -30,  5, 10, 15, 15, 10,  5,-30,
        -40,-20,  0,  5,  5,  0,-20,-40,
        -50,-40,-30,-30,-30,-30,-40,-50
    ]
    
    BISHOP_TABLE = [
        -20,-10,-10,-10,-10,-10,-10,-20,
        -10,  0,  0,  0,  0,  0,  0,-10,
        -10,  0,  5, 10, 10,  5,  0,-10,
        -10,  5,  5, 10, 10,  5,  5,-10,
        -10,  0, 10, 10, 10, 10,  0,-10,
        -10, 10, 10, 10, 10, 10, 10,-10,
        -10,  5,  0,  0,  0,  0,  5,-10,
        -20,-10,-10,-10,-10,-10,-10,-20
    ]
    
    ROOK_TABLE = [
        0,  0,  0,  0,  0,  0,  0,  0,
        5, 10, 10, 10, 10, 10, 10,  5,
        -5,  0,  0,  0,  0,  0,  0, -5,
        -5,  0,  0,  0,  0,  0,  0, -5,
        -5,  0,  0,  0,  0,  0,  0, -5,
        -5,  0,  0,  0,  0,  0,  0, -5,
        -5,  0,  0,  0,  0,  0,  0, -5,
        0,  0,  0,  5,  5,  0,  0,  0
    ]
    
    QUEEN_TABLE = [
        -20,-10,-10, -5, -5,-10,-10,-20,
        -10,  0,  0,  0,  0,  0,  0,-10,
        -10,  0,  5,  5,  5,  5,  0,-10,
        -5,  0,  5,  5,  5,  5,  0, -5,
        0,  0,  5,  5,  5,  5,  0, -5,
        -10,  5,  5,  5,  5,  5,  0,-10,
        -10,  0,  5,  0,  0,  0,  0,-10,
        -20,-10,-10, -5, -5,-10,-10,-20
    ]
    
    KING_MIDDLEGAME_TABLE = [
        -30,-40,-40,-50,-50,-40,-40,-30,
        -30,-40,-40,-50,-50,-40,-40,-30,
        -30,-40,-40,-50,-50,-40,-40,-30,
        -30,-40,-40,-50,-50,-40,-40,-30,
        -20,-30,-30,-40,-40,-30,-30,-20,
        -10,-20,-20,-20,-20,-20,-20,-10,
        20, 20,  0,  0,  0,  0, 20, 20,
        20, 30, 10,  0,  0, 10, 30, 20
    ]
    
    KING_ENDGAME_TABLE = [
        -50,-40,-30,-20,-20,-30,-40,-50,
        -30,-20,-10,  0,  0,-10,-20,-30,
        -30,-10, 20, 30, 30, 20,-10,-30,
        -30,-10, 30, 40, 40, 30,-10,-30,
        -30,-10, 30, 40, 40, 30,-10,-30,
        -30,-10, 20, 30, 30, 20,-10,-30,
        -30,-30,  0,  0,  0,  0,-30,-30,
        -50,-30,-30,-30,-30,-30,-30,-50
    ]
    
    # Opening book: maps starting positions (FEN) to good opening moves (UCI notation)
    # Helps AI play reasonable openings before deep search is feasible
    # FEN format: piece placement, side to move, castling rights, en passant, halfmove, fullmove
    OPENING_BOOK = {
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1": ["e2e4", "d2d4", "c2c4", "g1f3"],  # Starting position
        "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1": ["e7e5", "c7c5", "e7e6", "c7c6"],  # After 1.e4
        "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2": ["g1f3", "f1c4", "b1c3"],  # After 1.e4 e5
        "rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 1 2": ["b8c6", "g8f6"],  # After 1.e4 e5 2.Nf3
        "rnbqkbnr/pppppppp/8/8/3P4/8/PPP1PPPP/RNBQKBNR b KQkq - 0 1": ["g8f6", "d7d5", "e7e6"],  # After 1.d4
        "rnbqkb1r/pppppppp/5n2/8/3P4/8/PPP1PPPP/RNBQKBNR w KQkq - 1 2": ["c2c4", "g1f3"],  # After 1.d4 Nf6
    }

    def __init__(self, depth=3):
        """
        Initialize the AI engine.
        
        Args:
            depth: Maximum search depth (ply). Higher = stronger but slower.
                   Typical values: 3-6. Each +1 roughly 3-5x slower.
        """
        self.depth = depth
        self.nodes_searched = 0  # Counter for performance analysis
        
        # Transposition table: cache evaluated positions to avoid re-searching
        # Key: board FEN string
        # Value: (score, depth_searched, bound_flag, best_move_uci)
        # Bound flags: 'EXACT' (= real value), 'LOWER' (>=), 'UPPER' (<=)
        self.transposition_table: dict = {}
        self.tt_max_size = 500000  # Limit to ~500k entries (about 50-100MB)
        
        # Killer moves: non-capture moves that caused beta cutoffs at each depth
        # Key: depth (int), Value: list of up to 2 move UCIs
        # Tried early in move ordering since they often cause cutoffs again
        self.killers: dict[int, list[str]] = {}
        
        # History heuristic: rewards moves that historically caused beta cutoffs
        # Key: move UCI, Value: accumulated score (depth^2 per cutoff)
        self.history: dict[str, int] = {}
        
        # Learning database: persistent memory of past game outcomes
        # Key: "fen_position|move_uci", Value: {"w": wins, "l": losses, "d": draws}
        self.learning_db: dict = {}
        
        # Per-game log: accumulates choices made this game for learning update on game end
        # Each entry: (fen_key, move_uci, color_to_move_bool)
        self.game_log: list[tuple[str, str, bool]] = []
        
        # Path to persistent learning file
        self._learning_path = os.path.join(os.path.dirname(__file__), 'ai_learn.json')
        self._learning_path_gz = self._learning_path + '.gz'
        self._load_learning_db()
        
        # Toggle for learning bias in move ordering
        self.use_learning = True
        
        # Polyglot opening book (optional, loaded externally)
        self.polyglot_book: 'Optional[PolyglotBook]' = None
        self.use_polyglot = True  # Prefer Polyglot over hardcoded book when available

        # Training persistence and storage controls
        # When defer_persistence is True, finalize_game will batch disk writes
        self.defer_persistence: bool = False
        self.persist_every_n: int = 100
        self._pending_games: int = 0
        # Skip readable export during training batches by default
        self.export_readable_during_training: bool = False
        # Compress learning file to save disk space (writes ai_learn.json.gz)
        self.compress_learning: bool = True

    # ==================== Learning System ====================
    # These methods handle persistent learning across games
    
    def _load_learning_db(self) -> None:
        """Load the learning database from disk (if it exists)."""
        try:
            import json, gzip
            data = None
            # Prefer compressed file if available
            if os.path.exists(self._learning_path_gz):
                with gzip.open(self._learning_path_gz, 'rt', encoding='utf-8') as f:
                    data = json.load(f)
            elif os.path.exists(self._learning_path):
                with open(self._learning_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self.learning_db = data
            # If we loaded from uncompressed file but compression is enabled, migrate on next save
        except Exception:
            # If file corrupt or missing, start with empty database
            self.learning_db = {}

    def _save_learning_db(self) -> None:
        """Persist the learning database to disk."""
        try:
            import json, gzip
            if getattr(self, 'compress_learning', False):
                # Write compressed
                with gzip.open(self._learning_path_gz, 'wt', encoding='utf-8') as f:
                    json.dump(self.learning_db, f, separators=(',', ':'), ensure_ascii=False)
                # Try to remove uncompressed file to save space
                try:
                    if os.path.exists(self._learning_path):
                        os.remove(self._learning_path)
                except Exception:
                    pass
            else:
                with open(self._learning_path, 'w', encoding='utf-8') as f:
                    json.dump(self.learning_db, f, separators=(',', ':'), ensure_ascii=False)
        except Exception:
            pass  # Silently fail to avoid disrupting gameplay

    def _log_choice(self, fen_key: str, move_uci: str, color_to_move: bool) -> None:
        """
        Record an AI move choice for later learning update.
        
        Args:
            fen_key: Position (piece placement part of FEN)
            move_uci: Move in UCI notation (e.g., 'e2e4')
            color_to_move: True if white to move, False if black
        """
        try:
            self.game_log.append((fen_key, move_uci, color_to_move))
        except Exception:
            pass

    def finalize_game(self, result: str) -> None:
        """
        Apply game outcome to all logged moves, updating learning database.
        
        Called once per game after checkmate/stalemate/insufficient material.
        Updates win/loss/draw counts for each (position, move) pair.
        
        Args:
            result: 'white', 'black', or 'draw' — indicates winner
        """
        try:
            if not self.game_log:
                return
            
            # Process each logged move from this game
            for fen_key, move_uci, color_to_move in self.game_log:
                key = fen_key + '|' + move_uci  # Combined key for database lookup
                rec = self.learning_db.get(key) or {"w": 0, "l": 0, "d": 0}
                
                # Update counts based on result
                if result == 'draw':
                    rec["d"] = rec.get("d", 0) + 1  # Increment draw count
                else:
                    winner_is_white = (result == 'white')
                    # If the side that made this move won, it's a win; otherwise a loss
                    if winner_is_white == color_to_move:
                        rec["w"] = rec.get("w", 0) + 1
                    else:
                        rec["l"] = rec.get("l", 0) + 1
                self.learning_db[key] = rec
            
            # Clear the game log for next game
            self.game_log = []
            
            # Persist to disk (batched if training mode defers persistence)
            if getattr(self, 'defer_persistence', False):
                # Batch persistence for speed during training
                self._pending_games = int(getattr(self, '_pending_games', 0)) + 1
                threshold = int(getattr(self, 'persist_every_n', 100))
                if self._pending_games >= max(1, threshold):
                    self._save_learning_db()
                    # Optionally export readable file during training batches
                    if bool(getattr(self, 'export_readable_during_training', False)):
                        try:
                            self.export_readable_learning()
                        except Exception:
                            pass
                    self._pending_games = 0
            else:
                # Default behavior: save and export after every game
                self._save_learning_db()
                try:
                    self.export_readable_learning()
                except Exception:
                    pass
        except Exception:
            pass

    def export_readable_learning(self, path: 'Optional[str]' = None) -> 'Optional[str]':
        """
        Export learning database to a human-readable JSON file.
        
        Creates a file with:
        - Metadata (version, timestamp, counts)
        - Positions grouped by FEN
        - For each move: wins, losses, draws, games, winrate, and ordering bonus
        
        The ordering_bonus shows the exact value (+/- centipawns) the AI adds
        to move ordering for that (position, move) pair.
        
        Args:
            path: Optional custom save path. Defaults to ai_learn_readable.json
            
        Returns:
            Path to saved file, or None on error
        """
        try:
            import json, time
            
            # Aggregate raw database into positions -> moves structure
            positions: dict[str, dict] = {}
            for key, rec in self.learning_db.items():
                if '|' not in key:
                    continue  # Skip malformed keys
                    
                fen_key, move_uci = key.split('|', 1)
                entry = positions.setdefault(fen_key, {"moves": {}})
                entry["moves"][move_uci] = {
                    "wins": int(rec.get('w', 0)),
                    "losses": int(rec.get('l', 0)),
                    "draws": int(rec.get('d', 0)),
                }
            
            # Compute derived statistics (games, winrate, ordering bonus)
            total_positions = 0
            total_entries = 0
            for fen_key, entry in positions.items():
                moves = entry.get("moves", {})
                for mv, r in moves.items():
                    games = r["wins"] + r["losses"] + r["draws"]
                    r["games"] = games
                    # Winrate: wins + 0.5*draws (treating draws as half-wins)
                    r["winrate"] = 0.0 if games == 0 else round((r["wins"] + 0.5 * r["draws"]) / games, 3)
                    # Ordering bonus: scaled from -100 to +100 based on winrate deviation from 50%
                    r["ordering_bonus"] = int((r["winrate"] - 0.5) * 200)
                    total_entries += 1
                total_positions += 1
            
            # Build final output with metadata
            blob = {
                "meta": {
                    "version": 1,
                    "updated": time.strftime('%Y-%m-%d %H:%M:%S'),
                    "total_positions": total_positions,
                    "total_entries": total_entries,
                    "notes": "AI uses these stats to slightly bias move ordering; this does not change evaluation.",
                },
                "positions": positions,
            }
            
            out_path = path or os.path.join(os.path.dirname(self._learning_path), 'ai_learn_readable.json')
            with open(out_path, 'w', encoding='utf-8') as f:
                # Minified to reduce size; still viewable
                json.dump(blob, f, separators=(',', ':'), ensure_ascii=False)
            return out_path
        except Exception:
            return None

    def _learn_bonus(self, fen_key: str, move_uci: str) -> int:
        """
        Calculate move ordering bonus from learned statistics.
        
        Returns a small integer bonus (+/- ~100) based on the historical
        success rate of this move in this position. Moves that led to more
        wins get positive bonuses; moves that led to losses get penalties.
        
        This does NOT change the evaluation function—it only influences the
        order in which moves are tried, which can speed up alpha-beta pruning.
        
        Args:
            fen_key: Position (piece placement from FEN)
            move_uci: Move in UCI notation
            
        Returns:
            Ordering bonus in centipawns (typically -100 to +100)
        """
        try:
            rec = self.learning_db.get(fen_key + '|' + move_uci)
            if not rec:
                return 0  # No learning data for this position/move
                
            w = int(rec.get('w', 0))
            l = int(rec.get('l', 0))
            d = int(rec.get('d', 0))
            tot = w + l + d
            if tot == 0:
                return 0  # No games recorded yet
                
            # Calculate winrate (0.0 to 1.0), treating draws as 0.5
            rating = (w + 0.5 * d) / tot
            
            # Scale to bonus: -100 (0% winrate) to +100 (100% winrate)
            # 50% winrate = 0 bonus (neutral)
            bonus = int((rating - 0.5) * 200)
            return bonus
        except Exception:
            return 0

    # ==================== Polyglot Opening Book ====================
    
    def load_polyglot_book(self, book_path: str) -> bool:
        """
        Load a Polyglot opening book (.bin file).
        
        Polyglot is a standard opening book format used by many chess engines
        (Stockfish, Cute Chess, Arena, etc.). This provides much stronger
        opening play than the small hardcoded book.
        
        Args:
            book_path: Path to .bin Polyglot book file
            
        Returns:
            True if book loaded successfully, False otherwise
        """
        if not HAS_POLYGLOT:
            return False
        
        try:
            self.polyglot_book = PolyglotBook(book_path)
            return True
        except Exception as e:
            self.polyglot_book = None
            return False
    
    def unload_polyglot_book(self) -> None:
        """Unload the current Polyglot book (revert to hardcoded book)."""
        self.polyglot_book = None

    # ==================== Evaluation Functions ====================
    
    def game_phase(self, board: chess.Board) -> int:
        """
        Determine current game phase for tapered evaluation.
        
        Different phases use different strategies:
        - Opening: book moves, rapid development
        - Middlegame: king safety critical, aggressive piece placement
        - Endgame: king should be active, pawns become more valuable
        
        Returns:
            0 = Opening (< 10 moves)
            1 = Middlegame (normal material)
            2 = Endgame (≤ 6 minor/major pieces total)
        """
        # Count non-pawn pieces (queens, rooks, bishops, knights)
        total_material = sum(len(board.pieces(pt, chess.WHITE)) + len(board.pieces(pt, chess.BLACK)) 
                            for pt in [chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT])
        
        if len(board.move_stack) < 10:
            return 0  # Opening: first 10 moves
        elif total_material <= 6:  # Few pieces left (endgame threshold)
            return 2  # Endgame
        else:
            return 1  # Middlegame

    def get_piece_square_value(self, piece: chess.Piece, square: int, phase: int) -> int:
        """
        Get positional bonus/penalty for a piece on a specific square.
        
        Uses piece-square tables to encourage good piece placement:
        - Pawns: advance toward promotion
        - Knights: centralize
        - Bishops: control long diagonals
        - Rooks: open files and 7th rank
        - Queens: flexible but avoid early development
        - Kings: castle in middlegame, activate in endgame
        
        Args:
            piece: Chess piece (type and color)
            square: Square index (0-63, a1=0, h8=63)
            phase: Game phase (0=opening, 1=middlegame, 2=endgame)
            
        Returns:
            Bonus in centipawns (can be negative for bad squares)
        """
        # Mirror square for black pieces (tables are from white's perspective)
        sq = square if piece.color == chess.WHITE else chess.square_mirror(square)
        
        if piece.piece_type == chess.PAWN:
            return self.PAWN_TABLE[sq]
        elif piece.piece_type == chess.KNIGHT:
            return self.KNIGHT_TABLE[sq]
        elif piece.piece_type == chess.BISHOP:
            return self.BISHOP_TABLE[sq]
        elif piece.piece_type == chess.ROOK:
            return self.ROOK_TABLE[sq]
        elif piece.piece_type == chess.QUEEN:
            return self.QUEEN_TABLE[sq]
        elif piece.piece_type == chess.KING:
            if phase == 2:  # Endgame
                return self.KING_ENDGAME_TABLE[sq]
            else:
                return self.KING_MIDDLEGAME_TABLE[sq]
        return 0

    def evaluate(self, board: chess.Board) -> int:
        """Enhanced evaluation with material, position, mobility, king safety, and pawn structure"""
        if board.is_checkmate():
            return -20000 if board.turn == chess.WHITE else 20000
        if board.is_stalemate() or board.is_insufficient_material():
            return 0
        
        phase = self.game_phase(board)
        score = 0
        
        # Material and positional values
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece:
                value = self.PIECE_VALUES[piece.piece_type]
                pos_value = self.get_piece_square_value(piece, square, phase)
                if piece.color == chess.WHITE:
                    score += value + pos_value
                else:
                    score -= value + pos_value
        
        # Mobility (piece activity)
        score += self.evaluate_mobility(board)
        
        # King safety
        score += self.evaluate_king_safety(board, chess.WHITE, phase)
        score -= self.evaluate_king_safety(board, chess.BLACK, phase)
        
        # Pawn structure
        score += self.evaluate_pawn_structure(board, chess.WHITE)
        score -= self.evaluate_pawn_structure(board, chess.BLACK)
        
        # Bishop pair bonus
        if len(board.pieces(chess.BISHOP, chess.WHITE)) >= 2:
            score += 30
        if len(board.pieces(chess.BISHOP, chess.BLACK)) >= 2:
            score -= 30
        
        return score if board.turn == chess.WHITE else -score

    def evaluate_mobility(self, board: chess.Board) -> int:
        """Evaluate piece mobility (number of legal moves)"""
        current_turn = board.turn
        
        board.turn = chess.WHITE
        white_mobility = board.legal_moves.count()
        
        board.turn = chess.BLACK  
        black_mobility = board.legal_moves.count()
        
        board.turn = current_turn
        
        return (white_mobility - black_mobility) * 3

    def evaluate_king_safety(self, board: chess.Board, color: bool, phase: int) -> int:
        """Evaluate king safety based on game phase"""
        if phase == 2:  # Endgame - king should be active
            return 0
        
        score = 0
        king_square = board.king(color)
        if king_square is None:
            return 0
        
        king_file = chess.square_file(king_square)
        king_rank = chess.square_rank(king_square)
        
        # Penalize king in center during middlegame
        if phase == 1:
            if 2 <= king_file <= 5:
                score -= 40
        
        # Bonus for castled position
        if color == chess.WHITE:
            if king_square in [chess.G1, chess.C1]:
                score += 50
                # Bonus for pawn shield
                if king_square == chess.G1:
                    f2_piece = board.piece_at(chess.F2)
                    if f2_piece and f2_piece.piece_type == chess.PAWN:
                        score += 10
                    g2_piece = board.piece_at(chess.G2)
                    if g2_piece and g2_piece.piece_type == chess.PAWN:
                        score += 10
                    h2_piece = board.piece_at(chess.H2)
                    if h2_piece and h2_piece.piece_type == chess.PAWN:
                        score += 10
        else:
            if king_square in [chess.G8, chess.C8]:
                score += 50
                if king_square == chess.G8:
                    f7_piece = board.piece_at(chess.F7)
                    if f7_piece and f7_piece.piece_type == chess.PAWN:
                        score += 10
                    g7_piece = board.piece_at(chess.G7)
                    if g7_piece and g7_piece.piece_type == chess.PAWN:
                        score += 10
                    h7_piece = board.piece_at(chess.H7)
                    if h7_piece and h7_piece.piece_type == chess.PAWN:
                        score += 10
        
        return score

    def evaluate_pawn_structure(self, board: chess.Board, color: bool) -> int:
        """Evaluate pawn structure: passed pawns, doubled pawns, isolated pawns"""
        score = 0
        pawns = board.pieces(chess.PAWN, color)
        
        for pawn_square in pawns:
            pawn_file = chess.square_file(pawn_square)
            pawn_rank = chess.square_rank(pawn_square)
            
            # Check for passed pawn
            if self.is_passed_pawn(board, pawn_square, color):
                # More valuable closer to promotion
                if color == chess.WHITE:
                    score += 20 + (pawn_rank * 10)
                else:
                    score += 20 + ((7 - pawn_rank) * 10)
            
            # Check for doubled pawns
            same_file = [sq for sq in pawns if chess.square_file(sq) == pawn_file]
            if len(same_file) > 1:
                score -= 15
            
            # Check for isolated pawns
            if self.is_isolated_pawn(board, pawn_square, color):
                score -= 20
            
            # Check for backward pawns
            if self.is_backward_pawn(board, pawn_square, color):
                score -= 10
        
        return score

    def is_passed_pawn(self, board: chess.Board, square: int, color: bool) -> bool:
        """Check if pawn is passed (no enemy pawns ahead)"""
        pawn_file = chess.square_file(square)
        pawn_rank = chess.square_rank(square)
        
        enemy_color = not color
        enemy_pawns = board.pieces(chess.PAWN, enemy_color)
        
        for enemy_pawn in enemy_pawns:
            ep_file = chess.square_file(enemy_pawn)
            ep_rank = chess.square_rank(enemy_pawn)
            
            # Check if enemy pawn is in front or adjacent files
            if abs(ep_file - pawn_file) <= 1:
                if color == chess.WHITE and ep_rank > pawn_rank:
                    return False
                if color == chess.BLACK and ep_rank < pawn_rank:
                    return False
        
        return True

    def is_isolated_pawn(self, board: chess.Board, square: int, color: bool) -> bool:
        """Check if pawn has no friendly pawns on adjacent files"""
        pawn_file = chess.square_file(square)
        friendly_pawns = board.pieces(chess.PAWN, color)
        
        for friendly_pawn in friendly_pawns:
            if friendly_pawn != square:
                fp_file = chess.square_file(friendly_pawn)
                if abs(fp_file - pawn_file) == 1:
                    return False
        
        return True

    def is_backward_pawn(self, board: chess.Board, square: int, color: bool) -> bool:
        """Check if pawn is behind all friendly pawns on adjacent files"""
        pawn_file = chess.square_file(square)
        pawn_rank = chess.square_rank(square)
        friendly_pawns = board.pieces(chess.PAWN, color)
        
        for friendly_pawn in friendly_pawns:
            if friendly_pawn != square:
                fp_file = chess.square_file(friendly_pawn)
                fp_rank = chess.square_rank(friendly_pawn)
                
                if abs(fp_file - pawn_file) == 1:
                    if color == chess.WHITE and fp_rank < pawn_rank:
                        return True
                    if color == chess.BLACK and fp_rank > pawn_rank:
                        return True
        
        return False

    def quiescence(self, board: chess.Board, alpha: int, beta: int, depth: int = 0) -> int:
        """
        Quiescence search: extends search to stable positions to avoid horizon effect.
        
        The "horizon effect" is when the engine stops searching mid-combination,
        giving a false evaluation. For example:
        - Engine searches to depth 4 and sees "I can win a queen!"
        - But at depth 5, the opponent recaptures with check
        - Without quiescence, engine only sees the queen capture, not the recapture
        
        Solution: At depth 0, keep searching until position is "quiet" (no captures).
        Only tactical moves (captures) are searched, not all moves.
        
        Optimizations:
        - Delta pruning: Skip captures that can't possibly improve alpha
        - Depth limit: Prevent excessive quiescence search depth
        
        This is much cheaper than full search because:
        1. Only ~5-10% of legal moves are captures
        2. We stop as soon as position stabilizes (stand_pat evaluation)
        
        Args:
            board: Current position
            alpha, beta: Alpha-beta bounds
            depth: Current quiescence depth (for limiting search)
            
        Returns:
            Evaluation score when position is stable
        """
        # Limit quiescence search depth to prevent explosion
        if depth >= 8:
            return self.evaluate(board)
        
        # ===== STAND-PAT EVALUATION =====
        # Evaluate current position without any moves
        # If this is already good enough (>= beta), we can stop
        stand_pat = self.evaluate(board)
        
        if stand_pat >= beta:
            return beta  # Beta cutoff: position is too good, prune
        if alpha < stand_pat:
            alpha = stand_pat  # Update alpha if current position is better
        
        # ===== DELTA PRUNING =====
        # If even capturing a queen can't raise alpha, skip search
        # This saves ~30-40% of quiescence nodes
        BIG_DELTA = 975  # Queen value + margin
        if stand_pat < alpha - BIG_DELTA:
            return alpha  # Hopeless position, even best capture won't help
        
        # ===== CAPTURE-ONLY SEARCH =====
        # Generate only capture moves (tactical)
        capture_moves = [move for move in board.legal_moves if board.is_capture(move)]
        # Sort by MVV-LVA (Most Valuable Victim - Least Valuable Attacker)
        # Try queen captures before pawn captures
        capture_moves.sort(key=lambda m: self._move_score(board, m), reverse=True)
        
        for move in capture_moves:
            # Delta pruning per move: skip if captured piece value won't help
            captured_piece = board.piece_at(move.to_square)
            if captured_piece:
                delta = self.PIECE_VALUES.get(captured_piece.piece_type, 0)
                if stand_pat + delta + 200 < alpha:  # 200 = positional margin
                    continue  # Skip this capture, won't improve alpha
            
            board.push(move)
            score = -self.quiescence(board, -beta, -alpha, depth + 1)  # Recursive quiescence
            board.pop()
            
            if score >= beta:
                return beta  # Beta cutoff
            if score > alpha:
                alpha = score  # Improved lower bound
        
        return alpha  # Best score found in quiescence

    def negamax(self, board: chess.Board, depth: int, alpha: int, beta: int) -> int:
        """
        Negamax search with alpha-beta pruning, PVS, and LMR.
        
        This is the core search function that explores the game tree to find the best move.
        
        Key optimizations:
        1. Transposition Table: Avoids re-searching positions we've seen before
        2. Principal Variation Search (PVS): Most of the tree is searched with a null window
        3. Late Move Reductions (LMR): Less promising moves are searched at reduced depth
        
        Args:
            board: Current position to evaluate
            depth: How many more plies (half-moves) to search
            alpha: Lower bound (best score we can guarantee for the side to move)
            beta: Upper bound (opponent's best alternative elsewhere)
            
        Returns:
            Score in centipawns from the perspective of the side to move
            (positive = good for current player, negative = good for opponent)
        """
        # ===== TRANSPOSITION TABLE PROBE =====
        # Check if we've already searched this position
        fen = board.fen()
        if fen in self.transposition_table:
            t_score, t_depth, t_flag, _ = self.transposition_table[fen]
            # Only use cached score if it was searched at equal/greater depth
            if t_depth >= depth:
                # EXACT: score is accurate, no need to search
                if t_flag == 'EXACT':
                    return t_score
                # LOWER: real score is at least t_score (caused beta cutoff)
                # If cached lower bound exceeds beta, we'll cut off again
                if t_flag == 'LOWER' and t_score >= beta:
                    return t_score
                # UPPER: real score is at most t_score (all moves failed low)
                # If cached upper bound is below alpha, it won't improve
                if t_flag == 'UPPER' and t_score <= alpha:
                    return t_score

        # ===== TERMINAL NODE CHECKS =====
        if board.is_game_over():
            if board.is_checkmate():
                score = -9999999  # Opponent wins (we're checkmated)
            else:
                score = 0  # Draw (stalemate or insufficient material)
            self.transposition_table[fen] = (score, depth, 'EXACT', None)
            return score
        
        # ===== NULL MOVE PRUNING =====
        # If we're not in check and passing our turn still leads to beta cutoff,
        # we can prune this branch. This is safe because:
        # - If doing nothing is too good (>= beta), any real move will be even better
        # - Zugzwang positions (where passing would be better) are rare in middlegame
        #
        # This typically saves 20-30% of nodes searched.
        NULL_MOVE_R = 2  # Reduction for null move search
        if (depth >= 3 and 
            not board.is_check() and 
            # Don't do null move in endgame (zugzwang risk) or when in check
            len(list(board.legal_moves)) > 3):  # Not in zugzwang-prone positions
            try:
                board.push(chess.Move.null())
                score = -self.negamax(board, depth - NULL_MOVE_R - 1, -beta, -beta + 1)
                board.pop()
                
                if score >= beta:
                    # Null move caused beta cutoff, real moves will be even better
                    return beta
            except:
                # Null move might not be legal in some positions
                pass
        
        # ===== DEPTH LIMIT REACHED: QUIESCENCE SEARCH =====
        # At depth 0, we don't stop immediately—we search tactical moves to avoid
        # the "horizon effect" (e.g., stopping mid-capture sequence)
        if depth == 0:
            score = self.quiescence(board, alpha, beta, 0)
            self.transposition_table[fen] = (score, depth, 'EXACT', None)
            return score
        
        # ===== FUTILITY PRUNING =====
        # At low depths, if our position is very bad and a quiet move can't save us,
        # skip the move. This saves time on clearly losing positions.
        # Only apply when not in check (we must search all moves in check).
        if depth <= 2 and not board.is_check():
            # Futility margins: how much a quiet move can improve position
            futility_margins = [0, 300, 500]  # depth 0, 1, 2
            static_eval = self.evaluate(board)
            
            if static_eval + futility_margins[depth] <= alpha:
                # Position is so bad that quiet moves won't help
                # Still search captures (via quiescence)
                return self.quiescence(board, alpha, beta, 0)

        # ===== MOVE GENERATION AND ORDERING =====
        max_score = -9999999
        best_move = None
        moves = list(board.legal_moves)
        # Good move ordering is critical: if we search the best move first,
        # we'll get more alpha-beta cutoffs (pruning the rest of the tree)
        moves = self._order_moves(board, moves, depth)

        # ===== MAIN SEARCH LOOP =====
        orig_alpha = alpha  # Remember original alpha to determine bound flag
        for idx, move in enumerate(moves):
            # First move is the Principal Variation (PV) — most likely best
            pv = (idx == 0)
            
            # Pre-compute move properties for LMR logic
            try:
                is_capture = board.is_capture(move)
                gives_check = board.gives_check(move)
            except Exception:
                # Rare: board might be in an unexpected state
                is_capture = False
                gives_check = False
                
            board.push(move)
            
            if pv:
                # ===== PV NODE: FULL-WINDOW SEARCH =====
                # First move gets the full alpha-beta window because it's most likely best
                score = -self.negamax(board, depth - 1, -beta, -alpha)
            else:
                # ===== NON-PV NODES: PRINCIPAL VARIATION SEARCH (PVS) =====
                # Other moves are searched with a "null window" (alpha, alpha+1)
                # This is much faster because the window is tiny, causing quick cutoffs
                
                # Late Move Reductions (LMR):
                # Moves searched late are less likely to be good (we ordered them poorly)
                # So we search them at reduced depth first to save time
                reduction = 0
                if depth >= 3 and not is_capture and not gives_check and move.promotion is None:
                    # Only reduce "quiet" moves (non-tactical) after the first few
                    if idx >= 4:
                        reduction = 1  # Conservative: only reduce by 1 ply
                        
                d2 = max(1, depth - 1 - reduction)
                
                # Null-window search (PVS) with possibly reduced depth (LMR)
                score = -self.negamax(board, d2, -(alpha + 1), -alpha)
                
                # If the null-window search suggests this move is better than we thought...
                if score > alpha:
                    # Re-search with full window and full depth to get accurate score
                    # This "fail-soft" behavior ensures we don't miss good moves
                    score = -self.negamax(board, depth - 1, -beta, -alpha)
                    
            board.pop()
            
            # ===== UPDATE BEST SCORE =====
            if score > max_score:
                max_score = score
                best_move = move
                
            # ===== ALPHA-BETA PRUNING =====
            alpha = max(alpha, score)
            if alpha >= beta:
                # Beta cutoff: This position is too good; opponent won't let us reach it
                # (They have a better option earlier in the tree)
                
                # Record this move as a "killer" and bump its history score
                # so we'll try it first in sibling positions
                self._store_killer(depth, move)
                self._bump_history(move, depth)
                break  # Prune the rest of the moves
        
        # ===== TRANSPOSITION TABLE STORAGE =====
        # Store the result with a flag indicating what we learned:
        # - EXACT: we searched all moves and found the true score
        # - UPPER: all moves were <= orig_alpha (fail-low, no improvement)
        # - LOWER: at least one move was >= beta (fail-high, caused cutoff)
        flag = 'EXACT'
        if max_score <= orig_alpha:
            flag = 'UPPER'  # Real score could be lower, but at most max_score
        elif max_score >= beta:
            flag = 'LOWER'  # Real score could be higher, but at least max_score
            
        self.transposition_table[fen] = (max_score, depth, flag, best_move.uci() if best_move else None)
        
        # Manage transposition table size to prevent memory issues
        if len(self.transposition_table) > self.tt_max_size:
            self._trim_transposition_table()
        
        return max_score
    
    def _trim_transposition_table(self) -> None:
        """
        Trim transposition table when it gets too large.
        Keeps entries that were searched at higher depth (more valuable).
        """
        # Sort by depth (keeping deeper searches) and take top 80%
        sorted_entries = sorted(
            self.transposition_table.items(),
            key=lambda x: x[1][1],  # x[1][1] is the depth
            reverse=True
        )
        keep_count = int(self.tt_max_size * 0.8)
        self.transposition_table = dict(sorted_entries[:keep_count])

    def choose_move(self, board: chess.Board) -> 'Optional[chess.Move]':
        """
        Choose the best move using iterative deepening with aspiration windows.
        
        Iterative Deepening:
        - Searches depth 1, then depth 2, then depth 3, etc., up to self.depth
        - Each iteration uses results from previous depth to improve move ordering
        - Provides best move so far even if time runs out (anytime algorithm)
        
        Aspiration Windows:
        - Instead of searching with infinite bounds (-∞, +∞), use narrow window
        - Window is centered around previous depth's score
        - Much faster due to more alpha-beta cutoffs
        - If search fails outside window, widen and re-search
        
        Returns:
            Best move found, or None if no legal moves (shouldn't happen)
        """
        # ===== OPENING BOOK CHECK =====
        # First, check Polyglot book if available (higher priority, larger database)
        if self.use_polyglot and self.polyglot_book is not None:
            try:
                book_move_uci = self.polyglot_book.get_move(board, random_choice=True)
                if book_move_uci:
                    return chess.Move.from_uci(book_move_uci)
            except Exception:
                pass  # Fall back to hardcoded book or search
        
        # Fallback to hardcoded opening book
        # Check if current position is in our opening book (common opening lines)
        position_fen = board.fen().split(' ')[0]  # Just piece placement, ignore turn/castling
        if position_fen in self.OPENING_BOOK:
            book_moves = self.OPENING_BOOK[position_fen]
            # Filter for legal moves in case book has illegal entries
            legal_book_moves = [mv for mv in book_moves if mv in [m.uci() for m in board.legal_moves]]
            if legal_book_moves:
                # Play a random move from the book to add variety
                return chess.Move.from_uci(random.choice(legal_book_moves))

        # ===== ITERATIVE DEEPENING LOOP =====
        best_move = None
        prev_score = 0  # Score from previous depth iteration
        
        for d in range(1, max(1, self.depth) + 1):
            # ===== ASPIRATION WINDOW SETUP =====
            # Window width grows slightly with depth (deeper = less accurate prev_score)
            window = 30 + d * 10  # e.g., depth 1: ±40, depth 4: ±70
            
            # Set alpha/beta bounds around previous score, clamped to valid range
            alpha = max(-9999999, prev_score - window)
            beta = min(9999999, prev_score + window)
            
            # ===== ASPIRATION SEARCH =====
            # Try searching with narrow window first
            move_d, score_d = self._search_root(board, d, alpha, beta)
            
            # ===== HANDLE ASPIRATION FAILURES =====
            # Fail-low: score <= alpha (position is worse than expected)
            if move_d is not None and score_d <= alpha:
                # Re-search with alpha = -∞ to find true score
                move_d, score_d = self._search_root(board, d, -9999999, beta)
                
            # Fail-high: score >= beta (position is better than expected)
            elif move_d is not None and score_d >= beta:
                # Re-search with beta = +∞ to find true score
                move_d, score_d = self._search_root(board, d, alpha, 9999999)
                
            # ===== UPDATE BEST MOVE =====
            if move_d is not None:
                best_move, prev_score = move_d, score_d
                
        # ===== LOG CHOICE FOR LEARNING =====
        # Record the final chosen move so we can update statistics after the game
        try:
            if best_move is not None:
                fen_key = board.fen().split(' ')[0]  # Position (piece placement only)
                self._log_choice(fen_key, best_move.uci(), board.turn)
        except Exception:
            pass  # Don't let logging errors disrupt gameplay
            
        return best_move

    def _search_root(self, board: chess.Board, depth: int, alpha: int, beta: int) -> tuple['Optional[chess.Move]', int]:
        """Root search with PVS and TT storage; returns (best_move, score)."""
        best_move: 'Optional[chess.Move]' = None
        max_score = -9999999
        fen = board.fen()
        moves = list(board.legal_moves)
        moves = self._order_moves(board, moves, depth)
        orig_alpha = alpha
        for idx, move in enumerate(moves):
            board.push(move)
            if idx == 0:
                score = -self.negamax(board, depth - 1, -beta, -alpha)
            else:
                score = -self.negamax(board, depth - 1, -(alpha + 1), -alpha)
                if score > alpha:
                    score = -self.negamax(board, depth - 1, -beta, -alpha)
            board.pop()
            if score > max_score:
                max_score = score
                best_move = move
            alpha = max(alpha, score)
            if alpha >= beta:
                # Beta cutoff at root: still store killer/history for depth
                self._store_killer(depth, move)
                self._bump_history(move, depth)
                break
        # Store TT bound at root as well
        flag = 'EXACT'
        if max_score <= orig_alpha:
            flag = 'UPPER'
        elif max_score >= beta:
            flag = 'LOWER'
        self.transposition_table[fen] = (max_score, depth, flag, best_move.uci() if best_move else None)
        # Log the final choice for learning when this call represents the final ID depth.
        # The caller (choose_move) will call _search_root once per depth; only the last depth's
        # returned best_move is logged before finalize_game.
        return best_move, max_score

    # ---- Move ordering and heuristics ----
    def _order_moves(self, board: chess.Board, moves: list[chess.Move], depth: int) -> list[chess.Move]:
        def score_move(m: chess.Move) -> int:
            s = self._move_score(board, m)
            # History heuristic
            s += self.history.get(m.uci(), 0)
            # Killer bonuses
            killers = self.killers.get(depth, [])
            if m.uci() in killers:
                s += 10000
            # TT best move bonus
            try:
                fen = board.fen()
                entry = self.transposition_table.get(fen)
                if entry and entry[3] == m.uci():
                    s += 20000
            except Exception:
                pass
            # Learned preference bonus (small)
            if self.use_learning:
                try:
                    fen_key = board.fen().split(' ')[0]
                    s += self._learn_bonus(fen_key, m.uci())
                except Exception:
                    pass
            return s
        return sorted(moves, key=score_move, reverse=True)

    def _store_killer(self, depth: int, move: chess.Move) -> None:
        try:
            u = move.uci()
            arr = self.killers.get(depth, [])
            if u in arr:
                return
            if len(arr) < 2:
                arr.append(u)
            else:
                arr[1] = arr[0]
                arr[0] = u
            self.killers[depth] = arr
        except Exception:
            pass

    def _bump_history(self, move: chess.Move, depth: int) -> None:
        try:
            u = move.uci()
            self.history[u] = self.history.get(u, 0) + depth * depth
        except Exception:
            pass

    def choose_move_iterative(self, board: chess.Board, time_limit: float = 5.0) -> 'Optional[chess.Move]':
        """Choose best move using iterative deepening with time limit."""
        import time
        
        # Check Polyglot opening book first (if available)
        if self.use_polyglot and self.polyglot_book is not None:
            try:
                book_move_uci = self.polyglot_book.get_move(board, random_choice=True)
                if book_move_uci:
                    return chess.Move.from_uci(book_move_uci)
            except Exception:
                pass  # Fall back to hardcoded book or search
        
        # Check hardcoded opening book
        position_fen = board.fen().split(' ')[0]
        if position_fen in self.OPENING_BOOK:
            book_moves = self.OPENING_BOOK[position_fen]
            legal_book_moves = [move for move in book_moves if move in [m.uci() for m in board.legal_moves]]
            if legal_book_moves:
                chosen_uci = random.choice(legal_book_moves)
                return chess.Move.from_uci(chosen_uci)
        
        start_time = time.time()
        best_move = None
        
        # Iteratively deepen from 1 to max depth
        for depth in range(1, 11):  # Up to depth 10
            if time.time() - start_time >= time_limit:
                break
            
            self.depth = depth
            current_best = None
            best_score = -9999999
            alpha = -9999999
            beta = 9999999
            moves = list(board.legal_moves)
            moves.sort(key=lambda m: self._move_score(board, m), reverse=True)
            
            for move in moves:
                if time.time() - start_time >= time_limit:
                    break
                
                board.push(move)
                score = -self.negamax(board, depth - 1, -beta, -alpha)
                board.pop()
                
                if score > best_score:
                    best_score = score
                    current_best = move
                alpha = max(alpha, score)
            
            if current_best is not None:
                best_move = current_best
        
        return best_move

    def _move_score(self, board: chess.Board, move: chess.Move) -> int:
        score = 0
        if move.promotion is not None:
            if move.promotion == chess.QUEEN:
                score += 1200
            else:
                score += 900
        try:
            if board.is_capture(move):
                if board.is_en_passant(move):
                    victim_value = self.PIECE_VALUES[chess.PAWN]
                else:
                    victim_piece = board.piece_type_at(move.to_square)
                    victim_value = self.PIECE_VALUES.get(victim_piece, 0) if victim_piece is not None else 0
                score += 200 + victim_value
        except Exception:
            pass
        try:
            piece = board.piece_at(move.from_square)
            if piece is not None and piece.piece_type == chess.KING:
                from_file = chess.square_file(move.from_square)
                to_file = chess.square_file(move.to_square)
                if abs(from_file - to_file) == 2:
                    score += 80
        except Exception:
            pass
        try:
            board.push(move)
            if board.is_check():
                score += 40
            board.pop()
        except Exception:
            try:
                board.pop()
            except Exception:
                pass
        return score


class TrainingAI:
    """
    Headless high-speed AI vs AI training mode.
    Runs games in background without UI updates for faster learning.
    """
    
    def __init__(self, ai_instance: SimpleAI, depth: int = 3, batch_size: int = 100, export_interval: int | None = None, move_time_limit: float = 0.25):
        """
        Initialize training AI.
        
        Args:
            ai_instance: The SimpleAI instance to train
            depth: Search depth for both AIs
        """
        self.ai = ai_instance
        self.depth = depth
        self.running = False
        self.games_played = 0
        self.results = {'white': 0, 'black': 0, 'draw': 0}
        self.thread = None
        # Batching controls
        self.batch_size = max(1, int(batch_size))
        # If provided, export human-readable every N batches; None disables during training
        self.export_interval = export_interval
        self._batches_done = 0
        self.move_time_limit = max(0.05, float(move_time_limit))
        # Live metrics for UI polling
        self.current_move_count = 0
        # Console move counter throttle
        self._last_move_print = 0.0
    
    def start(self):
        """Start training in background thread."""
        if self.running:
            return
        
        self.running = True
        # Configure AI for batched persistence
        try:
            self.ai.defer_persistence = True
            self.ai.persist_every_n = self.batch_size
            # Only export readable during training if export_interval is set
            self.ai.export_readable_during_training = False if self.export_interval is None else True
            # Reset pending counter
            self.ai._pending_games = 0
        except Exception:
            pass
        self.thread = threading.Thread(target=self._training_loop, daemon=True)
        self.thread.start()
        print(f"\n{'='*60}")
        print(f"🎓 TRAINING AI MODE STARTED")
        print(f"{'='*60}")
        print(f"AI Depth: {self.depth}")
        print(f"Learning enabled: {self.ai.use_learning}")
        print(f"{'='*60}\n")
        # Reset live metrics at start
        try:
            self.current_move_count = 0
            self._last_move_print = 0.0
        except Exception:
            pass
    
    def stop(self):
        """Stop training."""
        if not self.running:
            return
        
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
        
        # Flush any pending learning to disk and export readable once
        try:
            self.ai._save_learning_db()
            try:
                self.ai.export_readable_learning()
            except Exception:
                pass
            # Restore default persistence behavior
            self.ai.defer_persistence = False
            self.ai.export_readable_during_training = False
        except Exception:
            pass

        print(f"\n{'='*60}")
        print(f"🛑 TRAINING AI MODE STOPPED")
        print(f"{'='*60}")
        print(f"Total games played: {self.games_played}")
        print(f"Results: White wins: {self.results['white']}, "
              f"Black wins: {self.results['black']}, "
              f"Draws: {self.results['draw']}")
        if self.games_played > 0:
            white_pct = (self.results['white'] / self.games_played) * 100
            black_pct = (self.results['black'] / self.games_played) * 100
            draw_pct = (self.results['draw'] / self.games_played) * 100
            print(f"Win rates: White: {white_pct:.1f}%, Black: {black_pct:.1f}%, Draw: {draw_pct:.1f}%")
        print(f"{'='*60}\n")
        try:
            self.current_move_count = 0
        except Exception:
            pass
    
    def _training_loop(self):
        """Main training loop - runs games continuously."""
        while self.running:
            try:
                print(f"🚀 Starting game #{self.games_played + 1}...")
                board = chess.Board()
                self.ai.game_log = []  # Reset game log
                
                # Play one complete game
                move_count = 0
                self.current_move_count = 0
                max_moves = 300  # Prevent infinite games
                
                while not board.is_game_over() and move_count < max_moves and self.running:
                    # Use time-limited search to guarantee steady progress
                    move = self.ai.choose_move_iterative(board, time_limit=self.move_time_limit)
                    
                    if move is None:
                        # Fallback: pick a random legal move to keep progress
                        legal = list(board.legal_moves)
                        if not legal:
                            break
                        move = random.choice(legal)
                    
                    board.push(move)
                    move_count += 1
                    # Update live move counter for UI
                    self.current_move_count = move_count
                    # Throttled move counter output to console
                    try:
                        now = time.time()
                        if (move_count % 10 == 0) or (now - self._last_move_print >= 1.0):
                            print(f"   Moves so far: {move_count}")
                            self._last_move_print = now
                    except Exception:
                        pass
                
                # Game ended
                if not self.running:
                    break
                
                self.games_played += 1
                
                # Determine result
                if board.is_checkmate():
                    winner = 'black' if board.turn == chess.WHITE else 'white'
                    result_text = f"{'White' if winner == 'white' else 'Black'} wins by checkmate"
                elif board.is_stalemate():
                    winner = 'draw'
                    result_text = "Draw by stalemate"
                elif board.is_insufficient_material():
                    winner = 'draw'
                    result_text = "Draw by insufficient material"
                elif move_count >= max_moves:
                    winner = 'draw'
                    result_text = "Draw by move limit"
                else:
                    winner = 'draw'
                    result_text = "Draw"
                
                # Update results
                self.results[winner] += 1
                
                # Finalize learning
                self.ai.finalize_game(winner)
                
                # Print game summary
                print(f"🎮 Game #{self.games_played} completed: {result_text} ({move_count} moves)")

                # Handle export interval if configured: export every N batches
                if self.export_interval is not None and self.ai._pending_games == 0:
                    # A batch was just flushed; increment batch counter
                    self._batches_done += 1
                    if (self._batches_done % max(1, self.export_interval)) == 0:
                        try:
                            self.ai.export_readable_learning()
                            print("📤 Exported readable learning snapshot.")
                        except Exception:
                            pass
                
                # Print periodic statistics
                if self.games_played % 10 == 0:
                    print(f"\n{'─'*60}")
                    print(f"📊 Training Statistics (after {self.games_played} games):")
                    print(f"   White: {self.results['white']} wins ({(self.results['white']/self.games_played)*100:.1f}%)")
                    print(f"   Black: {self.results['black']} wins ({(self.results['black']/self.games_played)*100:.1f}%)")
                    print(f"   Draws: {self.results['draw']} ({(self.results['draw']/self.games_played)*100:.1f}%)")
                    print(f"{'─'*60}\n")
                
            except Exception as e:
                print(f"Error in training loop: {e}")
                time.sleep(0.1)


class GameController:
    """Coordinates the GUI view, AI, and engine manager.

    This class owns the game state and provides callbacks for UI events.
    """

    def __init__(self, master: tk.Tk):
        self.master = master
        
        # Initialize config manager first
        if HAS_UPGRADES and ConfigManager:
            self.config = ConfigManager()
        else:
            self.config = None
        
        self.master.title('Python Chess — AI / Engine (Enhanced)')
        self.board = chess.Board()
        
        # Get AI depth from config
        ai_depth = self.config.get('ai_depth', 3) if self.config else 3
        self.ai = SimpleAI(depth=ai_depth)
        
        self.engine_manager = EngineManager(os.path.dirname(__file__))
        self.engine_enabled = False
        self.engine = None
        self.piece_images = None
        self.overlay_icons = None
        self.selected = None
        self.ai_thinking = False  # Track when AI is making a move
        self.move_history: list = []  # Store move history for last move highlighting
        self.play_mode = 'player_vs_player'  # New: 'player_vs_player' or 'player_vs_ai'
        # Track AI session to safely abort background moves on new game/mode changes
        self._ai_session_id = 0
        # Auto-restart control for AI vs AI mode
        self._auto_restart_scheduled = False
        # Track autosave state to avoid duplicate saves per game
        self._autosave_done = False
        # Game started flag - prevents AI from moving until Start is pressed
        self.game_started = False
        # UI update throttling for smoother high-speed AI
        self._last_ui_update = 0
        self._ui_update_interval = 0.05  # Minimum 50ms between UI updates
        # Training AI instance for headless mode
        self.training_ai = None
        
        # Initialize sound manager
        if HAS_UPGRADES and SoundManager:
            self.sound = SoundManager(
                base_path=os.path.dirname(__file__),
                enabled=self.config.get('sound_enabled', True) if self.config else True
            )
        else:
            self.sound = None
        
        # Initialize chess clock
        if HAS_UPGRADES and ChessClock:
            clock_time = self.config.get('clock_time', 600) if self.config else 600
            clock_increment = self.config.get('clock_increment', 0) if self.config else 0
            self.clock = ChessClock(
                white_time=clock_time,
                black_time=clock_time,
                increment=clock_increment,
                on_timeout=self.on_clock_timeout
            )
            self.clock_enabled = self.config.get('clock_enabled', False) if self.config else False
        else:
            self.clock = None
            self.clock_enabled = False

        # build UI
        self.status = tk.Label(master, text='White to move', font=('Arial', 12))
        self.status.grid(row=0, column=0, columnspan=8)
        self.hints_label = tk.Label(master, text='', font=('Arial', 9), fg='#333333')
        self.hints_label.grid(row=1, column=0, columnspan=8)
        self.ai_last_explanation = ''

        board_frame = tk.Frame(master)
        board_frame.grid(row=2, column=0, rowspan=8, columnspan=8)
        self.board_view = BoardView(board_frame, on_click=self.on_click)

        # Right-side controls with scrollable canvas for compact display
        ctrl_frame = tk.Frame(master)
        ctrl_frame.grid(row=2, column=8, rowspan=8, sticky='ns', padx=6)
        self.ctrl_frame = ctrl_frame
        
        # Create a canvas with scrollbar for the control panel
        canvas_container = tk.Frame(ctrl_frame)
        canvas_container.pack(fill='both', expand=True)
        
        scrollbar = tk.Scrollbar(canvas_container, orient='vertical')
        scrollbar.pack(side='right', fill='y')
        
        ctrl_canvas = tk.Canvas(canvas_container, yscrollcommand=scrollbar.set, width=220, highlightthickness=0)
        ctrl_canvas.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=ctrl_canvas.yview)
        self.ctrl_canvas = ctrl_canvas
        
        # Frame inside canvas for all controls
        scrollable_frame = tk.Frame(ctrl_canvas)
        ctrl_canvas.create_window((0, 0), window=scrollable_frame, anchor='nw')
        self.scrollable_frame = scrollable_frame
        
        # Small helper to add an info icon with a tooltip
        def _info(parent: tk.Widget, text: str) -> tk.Label:
            lbl = tk.Label(parent, text='ℹ', font=('Arial', 8, 'bold'), fg='#3f51b5', cursor='question_arrow')
            try:
                Tooltip(lbl, text)
            except Exception:
                pass
            return lbl

        # Update scroll region when frame changes size (throttled)
        def on_frame_configure(event):
            try:
                ctrl_canvas.update_idletasks()
                ctrl_canvas.configure(scrollregion=ctrl_canvas.bbox('all'))
            except Exception:
                pass
        scrollable_frame.bind('<Configure>', on_frame_configure)

        # Improve scrolling responsiveness: bind to canvas and inner frame only
        ctrl_canvas.configure(yscrollincrement=20)
        def on_mousewheel(event):
            try:
                if getattr(event, 'delta', 0) != 0:
                    ctrl_canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units')
                elif getattr(event, 'num', None) == 4:
                    ctrl_canvas.yview_scroll(-1, 'units')
                elif getattr(event, 'num', None) == 5:
                    ctrl_canvas.yview_scroll(1, 'units')
            except Exception:
                pass
        # Ensure canvas gets focus under pointer for wheel events
        ctrl_canvas.bind('<Enter>', lambda e: ctrl_canvas.focus_set())
        ctrl_canvas.bind('<MouseWheel>', on_mousewheel)
        scrollable_frame.bind('<MouseWheel>', on_mousewheel)
        # Linux support
        ctrl_canvas.bind('<Button-4>', on_mousewheel)
        ctrl_canvas.bind('<Button-5>', on_mousewheel)
        scrollable_frame.bind('<Button-4>', on_mousewheel)
        scrollable_frame.bind('<Button-5>', on_mousewheel)
        
        # Move list - more compact
        tk.Label(scrollable_frame, text='Moves', font=('Arial', 9, 'bold')).pack()
        self.move_list = tk.Listbox(scrollable_frame, width=20, height=12, font=('Arial', 8))
        self.move_list.pack(fill='x', padx=2, pady=2)

        btn_frame = tk.Frame(scrollable_frame)
        btn_frame.pack(pady=2)
        tk.Button(btn_frame, text='Save', command=self.save_pgn, font=('Arial', 8)).grid(row=0, column=0, padx=1)
        tk.Button(btn_frame, text='Load', command=self.load_pgn, font=('Arial', 8)).grid(row=0, column=1, padx=1)
        tk.Button(btn_frame, text='Undo', command=self.undo_move, font=('Arial', 8)).grid(row=0, column=2, padx=1)
        # New Game button available in all modes
        tk.Button(btn_frame, text='New', command=self.new_game, font=('Arial', 8)).grid(row=0, column=3, padx=1)
        tk.Button(btn_frame, text='Restart', command=self.restart_game, font=('Arial', 8)).grid(row=0, column=4, padx=1)
        
        # Start/Pause button for game control
        start_pause_frame = tk.Frame(scrollable_frame)
        start_pause_frame.pack(pady=4)
        self.start_pause_button = tk.Button(start_pause_frame, text='▶ Start Game', 
                                           command=self.toggle_game_started, 
                                           font=('Arial', 10, 'bold'),
                                           bg='#4CAF50', fg='white',
                                           width=15)
        self.start_pause_button.pack()

        # AI depth - header with info
        depth_header = tk.Frame(scrollable_frame)
        depth_header.pack(fill='x')
        tk.Label(depth_header, text='AI Depth', font=('Arial', 9, 'bold')).pack(side='left')
        _info(depth_header, 'Search depth for AI in GUI modes. Higher = stronger, slower.\nFor Training AI, use Per-move time to control speed.').pack(side='left', padx=4)
        self.depth_var = tk.IntVar(value=ai_depth)
        depth_scale = tk.Scale(scrollable_frame, from_=1, to=6, orient='horizontal', 
                              variable=self.depth_var, command=self.on_depth_change,
                              length=180, sliderlength=20)
        depth_scale.pack(padx=2)
        self.depth_scale = depth_scale
        
        # Game mode selector
        mode_frame = tk.LabelFrame(scrollable_frame, text='Game Mode', font=('Arial', 9, 'bold'))
        mode_frame.pack(fill='x', pady=2, padx=2)
        # Info row at the top of Game Mode
        mode_info_row = tk.Frame(mode_frame)
        mode_info_row.pack(fill='x', padx=2, pady=1)
        _info(mode_info_row, 'Player vs Player: both sides human.\nPlayer vs AI: Black is AI by default.\nAI vs AI: visible self-play with UI pacing.\nTraining AI: fastest headless self-play, logs to console.').pack(side='left')

        self.mode_var = tk.StringVar(value='player_vs_player')
        tk.Radiobutton(mode_frame, text='Player vs Player', variable=self.mode_var,
                       value='player_vs_player', command=self.change_mode,
                       font=('Arial', 8)).pack(anchor='w', padx=2)
        tk.Radiobutton(mode_frame, text='Player vs AI', variable=self.mode_var,
                       value='player_vs_ai', command=self.change_mode,
                       font=('Arial', 8)).pack(anchor='w', padx=2)
        tk.Radiobutton(mode_frame, text='AI vs AI', variable=self.mode_var,
                       value='ai_vs_ai', command=self.change_mode,
                       font=('Arial', 8)).pack(anchor='w', padx=2)
        tk.Radiobutton(mode_frame, text='Training AI (No UI)', variable=self.mode_var,
                       value='training_ai', command=self.change_mode,
                       font=('Arial', 8)).pack(anchor='w', padx=2)
        # Auto-restart option (effective in AI vs AI only)
        self.auto_restart_var = tk.BooleanVar(value=True)
        tk.Checkbutton(mode_frame, text='Auto-restart on game end (AI vs AI)',
                       variable=self.auto_restart_var, font=('Arial', 8)).pack(anchor='w', padx=10)
        # AI move pacing to ensure UI keeps up (ms)
        pace_frame = tk.Frame(mode_frame)
        pace_frame.pack(fill='x', padx=8, pady=2)
        tk.Label(pace_frame, text='AI Move Delay (ms):', font=('Arial', 8)).pack(side='left')
        _info(pace_frame, 'Applies only to AI vs AI (UI) to slow moves for visibility. Training AI uses Per-move time instead.').pack(side='left', padx=4)
        self.ai_delay_var = tk.IntVar(value=200)
        tk.Scale(pace_frame, from_=0, to=1000, orient='horizontal', variable=self.ai_delay_var, length=120, sliderlength=14).pack(side='left', padx=4)

        # General options
        options_frame = tk.LabelFrame(scrollable_frame, text='Options', font=('Arial', 9, 'bold'))
        options_frame.pack(fill='x', pady=2, padx=2)
        self.autosave_pgn_var = tk.BooleanVar(value=self.config.get('auto_save_pgn', False) if self.config else False)
        # Row for autosave option + info icon
        opts_row1 = tk.Frame(options_frame)
        opts_row1.pack(fill='x', padx=2, pady=1)
        autosave_cb = tk.Checkbutton(opts_row1, text='Auto-save PGN on game end', variable=self.autosave_pgn_var, command=self.on_toggle_autosave, font=('Arial', 8))
        autosave_cb.pack(side='left')
        _info(opts_row1, 'When enabled, saves PGN automatically at game end.').pack(side='left', padx=4)
        # Compress learning data (gzip)
        self.compress_learning_var = tk.BooleanVar(value=(self.config.get('compress_learning', getattr(self.ai, 'compress_learning', True)) if self.config else getattr(self.ai, 'compress_learning', True)))
        opts_row2 = tk.Frame(options_frame)
        opts_row2.pack(fill='x', padx=2, pady=1)
        compress_cb = tk.Checkbutton(opts_row2, text='Compress learning data (gzip)', variable=self.compress_learning_var,
                                     command=self.on_toggle_compress, font=('Arial', 8))
        compress_cb.pack(side='left')
        _info(opts_row2, 'Store learning as ai_learn.json.gz (smaller, faster I/O).').pack(side='left', padx=4)
        # Apply initial compression setting to AI
        try:
            self.ai.compress_learning = bool(self.compress_learning_var.get())
        except Exception:
            pass

        # Training settings
        training_frame = tk.LabelFrame(scrollable_frame, text='Training Settings', font=('Arial', 9, 'bold'))
        training_frame.pack(fill='x', pady=2, padx=2)
        self.training_batch_size_var = tk.IntVar(value=(self.config.get('training_batch_size', 100) if self.config else 100))
        self.training_move_time_var = tk.IntVar(value=(self.config.get('training_move_time_ms', 250) if self.config else 250))  # milliseconds per move
        self.training_snapshot_interval_var = tk.IntVar(value=(self.config.get('training_snapshot_batches', 0) if self.config else 0))  # 0 = off
        self.training_games_var = tk.IntVar(value=(self.config.get('training_games', 0) if self.config else 0))
        row = tk.Frame(training_frame)
        row.pack(fill='x', padx=4, pady=1)
        tk.Label(row, text='Batch size (games):', font=('Arial', 8)).pack(side='left')
        batch_entry = tk.Entry(row, textvariable=self.training_batch_size_var, width=6, font=('Arial', 8))
        batch_entry.pack(side='left', padx=6)
        _info(row, 'Save learning after this many games. Larger = fewer writes, faster training.').pack(side='left', padx=4)
        row2 = tk.Frame(training_frame)
        row2.pack(fill='x', padx=4, pady=1)
        tk.Label(row2, text='Per-move time (ms):', font=('Arial', 8)).pack(side='left')
        move_scale = tk.Scale(row2, from_=50, to=1000, orient='horizontal', variable=self.training_move_time_var, length=120, sliderlength=14)
        move_scale.pack(side='left', padx=6)
        _info(row2, 'Time budget per move during training. Guarantees progress at high depths.').pack(side='left', padx=4)
        row3 = tk.Frame(training_frame)
        row3.pack(fill='x', padx=4, pady=1)
        tk.Label(row3, text='Readable snapshot every N batches (0=off):', font=('Arial', 8)).pack(side='left')
        snap_entry = tk.Entry(row3, textvariable=self.training_snapshot_interval_var, width=6, font=('Arial', 8))
        snap_entry.pack(side='left', padx=6)
        _info(row3, 'Export readable learning after N batches. 0 disables periodic snapshots.').pack(side='left', padx=4)
        row4 = tk.Frame(training_frame)
        row4.pack(fill='x', padx=4, pady=1)
        tk.Label(row4, text='Games to run (0=until stop):', font=('Arial', 8)).pack(side='left')
        games_entry = tk.Entry(row4, textvariable=self.training_games_var, width=8, font=('Arial', 8))
        games_entry.pack(side='left', padx=6)
        _info(row4, 'End training automatically after this many games. 0 keeps training until you stop it.').pack(side='left', padx=4)
        # Reset to defaults button
        reset_btn = tk.Button(training_frame, text='Reset Training Defaults', font=('Arial', 8), command=self.reset_training_defaults)
        reset_btn.pack(anchor='e', padx=4, pady=4)
        # Quick actions: Copy command / Run training
        actions_row = tk.Frame(training_frame)
        actions_row.pack(fill='x', padx=4, pady=4)
        tk.Button(actions_row, text='Copy Training Command', font=('Arial', 8), command=self.copy_training_command).pack(side='left')
        tk.Button(actions_row, text='Run Training in Console', font=('Arial', 8), command=self.run_training_now).pack(side='left', padx=6)
        _info(actions_row, 'Copy: puts a ready-to-run CLI command on clipboard. Run: opens a new console window executing training.').pack(side='left', padx=6)
        # Tooltip for reset action
        try:
            Tooltip(reset_btn, 'Restore batch=100, per-move=250ms, snapshots off, compression on.')
        except Exception:
            pass

        # Live training progress label
        stats_row = tk.Frame(training_frame)
        stats_row.pack(fill='x', padx=4, pady=2)
        tk.Label(stats_row, text='Training Progress:', font=('Arial', 8, 'bold')).pack(side='left')
        self.training_stats_label = tk.Label(stats_row, text='—', font=('Arial', 8))
        self.training_stats_label.pack(side='left', padx=6)

        # New features frame - more compact
        if HAS_UPGRADES:
            features_frame = tk.LabelFrame(scrollable_frame, text='Features', font=('Arial', 9, 'bold'))
            features_frame.pack(fill='x', pady=2, padx=2)
            self.features_frame = features_frame
            
            # Flip board button - smaller
            tk.Button(features_frame, text='Flip Board', command=self.flip_board, 
                     font=('Arial', 8)).pack(fill='x', pady=1, padx=2)
            
            # Theme toggle - more compact
            theme_frame = tk.Frame(features_frame)
            theme_frame.pack(fill='x', pady=1, padx=2)
            tk.Label(theme_frame, text='Theme:', font=('Arial', 8)).pack(side='left')
            self.theme_var = tk.StringVar(value=self.config.get('theme', 'light') if self.config else 'light')
            theme_menu = tk.OptionMenu(theme_frame, self.theme_var, 'light', 'dark')
            theme_menu.config(font=('Arial', 8))
            theme_menu.pack(side='left', fill='x', expand=True)
            self.theme_var.trace('w', lambda *args: self.change_theme(self.theme_var.get()))
            # Apply theme on startup to ensure board colors match saved preference
            try:
                self.change_theme(self.theme_var.get())
            except Exception:
                pass
            
            # Sound toggle - smaller
            if self.sound:
                self.sound_button = tk.Button(features_frame, 
                                             text=f"Sound: {'On' if self.sound.enabled else 'Off'}",
                                             command=self.toggle_sound,
                                             font=('Arial', 8))
                self.sound_button.pack(fill='x', pady=1, padx=2)
            
            # Clock controls - more compact
            if self.clock:
                clock_frame = tk.LabelFrame(features_frame, text='Clock', font=('Arial', 8))
                clock_frame.pack(fill='x', pady=2, padx=2)
                
                self.white_clock_label = tk.Label(clock_frame, text="10:00",
                                                  font=('Arial', 11, 'bold'), fg='white', bg='black')
                self.white_clock_label.pack(fill='x', padx=2, pady=1)
                
                self.black_clock_label = tk.Label(clock_frame, text="10:00",
                                                  font=('Arial', 11, 'bold'), fg='black', bg='white')
                self.black_clock_label.pack(fill='x', padx=2, pady=1)
                
                clock_btn_frame = tk.Frame(clock_frame)
                clock_btn_frame.pack(fill='x', padx=2)
                
                self.clock_toggle_button = tk.Button(clock_btn_frame,
                                                     text='Enable',
                                                     command=self.toggle_clock,
                                                     font=('Arial', 8))
                self.clock_toggle_button.pack(side='left', fill='x', expand=True)
                
                tk.Button(clock_btn_frame, text='Reset', command=self.reset_clock,
                         font=('Arial', 8)).pack(side='left', padx=1)
                
                # Start updating clock display
                self.update_clock_display()
            
            # Statistics display - more compact
            if self.config:
                stats_frame = tk.LabelFrame(scrollable_frame, text='Stats', font=('Arial', 9, 'bold'))
                stats_frame.pack(fill='x', pady=2, padx=2)
                
                stats = self.config.get('statistics', {})
                games = stats.get('games_played', 0)
                white_wins = stats.get('white_wins', 0)
                black_wins = stats.get('black_wins', 0)
                draws = stats.get('draws', 0)
                
                stats_text = f"Games: {games}\nW: {white_wins} | B: {black_wins} | D: {draws}"
                self.stats_label = tk.Label(stats_frame, text=stats_text, justify='left', font=('Arial', 8))
                self.stats_label.pack(padx=2, pady=2)

        # Learning panel
        learn_frame = tk.LabelFrame(scrollable_frame, text='Learning', font=('Arial', 9, 'bold'))
        learn_frame.pack(fill='x', pady=2, padx=2)
        self.learn_use_var = tk.BooleanVar(value=True)
        def toggle_learning():
            try:
                self.ai.use_learning = bool(self.learn_use_var.get())
            except Exception:
                pass
        tk.Checkbutton(learn_frame, text='Use Learning Bias', variable=self.learn_use_var,
                       command=toggle_learning, font=('Arial', 8)).pack(anchor='w', padx=2)
        
        # Learning status display
        self.learning_status_label = tk.Label(learn_frame, text='', font=('Arial', 7), fg='blue')
        self.learning_status_label.pack(padx=2, pady=1)
        self.update_learning_status()
        
        btns = tk.Frame(learn_frame)
        btns.pack(fill='x', padx=2, pady=2)
        tk.Button(btns, text='Show Position', command=self.show_learning_for_position,
                  font=('Arial', 8)).pack(side='left', padx=1)
        tk.Button(btns, text='Export', command=self.export_learning,
                  font=('Arial', 8)).pack(side='left', padx=1)
        tk.Button(btns, text='Import', command=self.import_learning,
                  font=('Arial', 8)).pack(side='left', padx=1)
        tk.Button(btns, text='Reset', command=self.reset_learning,
                  font=('Arial', 8)).pack(side='left', padx=1)

        # Polyglot Opening Book panel
        if HAS_POLYGLOT:
            book_frame = tk.LabelFrame(scrollable_frame, text='Opening Book (Polyglot)', font=('Arial', 9, 'bold'))
            book_frame.pack(fill='x', pady=2, padx=2)
            
            self.polyglot_use_var = tk.BooleanVar(value=True)
            def toggle_polyglot():
                try:
                    self.ai.use_polyglot = bool(self.polyglot_use_var.get())
                except Exception:
                    pass
            
            tk.Checkbutton(book_frame, text='Use Polyglot Book', variable=self.polyglot_use_var,
                          command=toggle_polyglot, font=('Arial', 8)).pack(anchor='w', padx=2)
            
            book_btns = tk.Frame(book_frame)
            book_btns.pack(fill='x', padx=2, pady=2)
            tk.Button(book_btns, text='Load Book', command=self.load_opening_book,
                     font=('Arial', 8)).pack(side='left', padx=1, fill='x', expand=True)
            tk.Button(book_btns, text='Unload', command=self.unload_opening_book,
                     font=('Arial', 8)).pack(side='left', padx=1, fill='x', expand=True)
            
            self.book_status_label = tk.Label(book_frame, text='No book loaded', font=('Arial', 7), fg='gray')
            self.book_status_label.pack(padx=2, pady=1)

        # Engine frame - more compact
        engine_frame = tk.LabelFrame(scrollable_frame, text='Engine (Advanced)', font=('Arial', 9, 'bold'))
        engine_frame.pack(fill='x', pady=2, padx=2)
        self.engine_frame = engine_frame
        self.engine_path_var = tk.StringVar()
        self.engine_path_var.set(shutil.which('stockfish') or '')
        tk.Entry(engine_frame, textvariable=self.engine_path_var, width=22, font=('Arial', 8)).pack(padx=2, pady=1)
        
        engine_btn_frame = tk.Frame(engine_frame)
        engine_btn_frame.pack(fill='x', padx=2)
        self.detect_button = tk.Button(engine_btn_frame, text='Detect', command=self.detect_engine, font=('Arial', 8))
        self.detect_button.pack(side='left', fill='x', expand=True, padx=1)
        self.download_button = tk.Button(engine_btn_frame, text='Download', command=self.download_engine, font=('Arial', 8))
        self.download_button.pack(side='left', fill='x', expand=True, padx=1)
        self.verify_button = tk.Button(engine_btn_frame, text='Verify', command=self.verify_engine, font=('Arial', 8))
        self.verify_button.pack(side='left', fill='x', expand=True, padx=1)
        
        # Engine settings - simple defaults
        self.platform_var = tk.StringVar(value='auto')
        self.github_token = tk.StringVar()
        self.verify_retries = tk.IntVar(value=2)
        self.verify_timeout = tk.DoubleVar(value=0.05)
        self.backoff_var = tk.StringVar(value='linear')
        self.backoff_max = tk.DoubleVar(value=5.0)
        self.auto_download_var = tk.BooleanVar(value=False)
        self.verify_log = tk.Listbox(scrollable_frame, width=22, height=4, font=('Arial', 7))
        
        self.engine_toggle = tk.Button(engine_frame, text='Use Engine: Off', command=self.toggle_engine, font=('Arial', 8))
        self.engine_toggle.pack(fill='x', pady=1, padx=2)

        self.load_piece_images()
        self.load_overlay_icons()

        # finalize
        self.update_board()
        master.protocol('WM_DELETE_WINDOW', self.on_close)

    # ---- UI callbacks and helpers (moved from previous main.py ChessGUI) ----
    def on_click(self, square):
        # Prevent moves while AI is thinking
        if self.ai_thinking:
            return
        # In AI vs AI mode, ignore manual input
        if self.play_mode == 'ai_vs_ai':
            return
        # In training AI mode, ignore manual input
        if self.play_mode == 'training_ai':
            return
        # In player vs AI mode, only allow moves if game has started
        if self.play_mode == 'player_vs_ai' and not self.game_started:
            return
        if self.board.is_game_over():
            return
        piece = self.board.piece_at(square)
        if self.selected is None:
            if piece is None:
                return
            if piece.color != self.board.turn:
                return
            self.selected = square
            self.board_view.highlight(square)
            self.board_view.show_legal_moves(self.board, square)
        else:
            move = None
            sel_piece = self.board.piece_at(self.selected)
            promotes = False
            if sel_piece is not None and sel_piece.piece_type == chess.PAWN:
                r = chess.square_rank(square)
                if (sel_piece.color == chess.WHITE and r == 7) or (sel_piece.color == chess.BLACK and r == 0):
                    promotes = True
            if promotes:
                assert sel_piece is not None
                promo = self.ask_promotion(sel_piece.color)
                if promo is None:
                    self.selected = None
                    self.update_board()
                    return
                move = chess.Move(self.selected, square, promotion=promo)
            else:
                move = chess.Move(self.selected, square)
            if move in self.board.legal_moves:
                # Determine move type for sound effects
                is_capture = self.board.is_capture(move)
                is_castle = sel_piece is not None and sel_piece.piece_type == chess.KING and abs(chess.square_file(self.selected) - chess.square_file(square)) == 2
                
                # Make the move
                self.board.push(move)
                self.move_history.append(move)
                
                # Store move for statistics
                if self.config:
                    self.config.increment_move_count()
                
                # Update clock
                if self.clock and self.clock_enabled and self.clock.is_running():
                    self.clock.switch()
                
                # Play sound effects
                if self.sound:
                    if self.board.is_checkmate():
                        self.sound.play('checkmate')
                    elif self.board.is_check():
                        self.sound.play('check')
                    elif is_castle:
                        self.sound.play('castle')
                    elif is_capture:
                        self.sound.play('capture')
                    else:
                        self.sound.play('move')
                
                self.selected = None
                self.board_view.clear_highlights()
                self.update_board()
                self.master.update()
                
                # Update statistics if game over
                if self.board.is_game_over() and self.config:
                    if self.board.is_checkmate():
                        winner = 'black' if self.board.turn == chess.WHITE else 'white'
                        self.config.update_statistics(winner)
                    else:
                        self.config.update_statistics('draw')
                
                if not self.board.is_game_over():
                    # Only trigger AI if in player vs AI mode AND game has started
                    if self.play_mode == 'player_vs_ai' and self.game_started:
                        self.ai_thinking = True  # Lock UI while AI thinks
                        self.status.config(text='AI is thinking...')
                        self.master.config(cursor='watch')  # Change cursor to show waiting
                        # Capture depth before thread to avoid tkinter variable access issues
                        current_depth = max(1, self.depth_var.get())
                        threading.Thread(target=self.run_ai_move, args=(current_depth,), daemon=True).start()
            else:
                if piece is not None and piece.color == self.board.turn:
                    self.selected = square
                    self.update_board()

    def run_ai_move(self, depth: int):
        # Optional pacing so the UI can render between AI moves (especially in AI vs AI)
        try:
            if self.play_mode == 'ai_vs_ai':
                delay_ms = int(self.ai_delay_var.get()) if hasattr(self, 'ai_delay_var') else 200
                if delay_ms > 0:
                    time.sleep(delay_ms / 1000.0)
        except Exception:
            pass
        
        # For AI vs AI, wait until previous move is fully processed
        if self.play_mode == 'ai_vs_ai':
            # Wait for ai_thinking to be False (previous move completed)
            max_wait = 50  # Maximum 5 seconds
            wait_count = 0
            while self.ai_thinking and wait_count < max_wait:
                time.sleep(0.1)
                wait_count += 1
        # Capture session ID to prevent stale threads from applying moves after a new game
        session_id = self._ai_session_id
        move = None
        try:
            if self.engine_enabled and getattr(self.engine_manager, 'engine', None) is not None:
                try:
                    tm = 0.05 * depth
                    result = self.engine_manager.play(self.board, chess.engine.Limit(time=tm))
                    move = result.move
                    # Engine move: no learning-based explanation
                    self.ai_last_explanation = ''
                except Exception:
                    move = None
            else:
                self.ai.depth = depth
                # Compute explanation using learning before pushing
                fen_key = self.board.fen().split(' ')[0]
                # Use time-limited search in AI vs AI to avoid long stalls at higher depths
                if self.play_mode == 'ai_vs_ai':
                    try:
                        tl = (self.training_move_time_var.get() / 1000.0) if hasattr(self, 'training_move_time_var') else 0.25
                        tl = max(0.05, float(tl))
                    except Exception:
                        tl = 0.25
                    move = self.ai.choose_move_iterative(self.board, time_limit=tl)
                else:
                    move = self.ai.choose_move(self.board)
                if move is not None and getattr(self.ai, 'use_learning', False):
                    try:
                        key = f"{fen_key}|{move.uci()}"
                        rec = self.ai.learning_db.get(key)
                        if rec:
                            w = int(rec.get('w', 0)); l = int(rec.get('l', 0)); d = int(rec.get('d', 0))
                            games = w + l + d
                            wr = (w + 0.5 * d) / games if games > 0 else 0.0
                            bonus = int((wr - 0.5) * 200)
                            self.ai_last_explanation = f"AI chose {move.uci()} — games:{games} wr:{wr:.3f} bonus:{bonus:+d}"
                        else:
                            self.ai_last_explanation = f"AI chose {move.uci()} — no prior learning"
                    except Exception:
                        self.ai_last_explanation = ''
                else:
                    self.ai_last_explanation = ''
            
            # Only apply the move if session hasn't changed (no new game/mode switch)
            if move is not None and session_id == self._ai_session_id:
                self.board.push(move)
        except Exception as e:
            print(f"Error in AI move: {e}")
        
        # Schedule GUI update on main thread only if still current session
        if session_id == self._ai_session_id:
            self.master.after(0, self._finish_ai_move)
    
    def _finish_ai_move(self):
        """Called on main thread after AI move completes."""
        try:
            self.ai_thinking = False  # Unlock UI after AI move
            self.master.config(cursor='')  # Reset cursor to default
            self.update_board()
            # Chain next AI move if in AI vs AI mode AND game has started
            if self.play_mode == 'ai_vs_ai' and not self.board.is_game_over() and self.game_started:
                # Brief delay to keep UI responsive
                current_depth = max(1, self.depth_var.get())
                self.ai_thinking = True
                self.status.config(text='AI is thinking...')
                self.master.config(cursor='watch')
                threading.Thread(target=self.run_ai_move, args=(current_depth,), daemon=True).start()
        except Exception as e:
            print(f"Error finishing AI move: {e}")
            self.ai_thinking = False
            self.master.config(cursor='')

    def update_board(self, force=False):
        # Throttle UI updates for smoother high-speed AI performance
        if not force:
            current_time = time.time()
            if current_time - self._last_ui_update < self._ui_update_interval:
                return
            self._last_ui_update = current_time
        
        # render pieces and move list
        try:
            self.board_view.update(self.board, self.piece_images)
            self.board_view.apply_special_overlays(self.board, self.overlay_icons)
        except Exception:
            pass
        
        # If player is in check, show all legal moves to escape using fixed board highlight colors
        if self.board.is_check() and not self.ai_thinking:
            from constants import CAPTURE_COLOR, LEGAL_MOVE_COLOR

            # Highlight king in check with fixed capture color
            king_square = self.board.king(self.board.turn)
            if king_square is not None:
                try:
                    self.board_view.canvases[king_square].configure(bg=CAPTURE_COLOR)
                except Exception:
                    pass

            # Show all legal moves that get out of check with fixed legal move color
            try:
                for move in self.board.legal_moves:
                    to_square = move.to_square
                    canvas = self.board_view.canvases.get(to_square)
                    if canvas:
                        canvas.configure(bg=LEGAL_MOVE_COLOR)
            except Exception:
                pass
        
        # update move list
        self.move_list.delete(0, tk.END)
        b = chess.Board()
        san_moves = []
        for mv in self.board.move_stack:
            san_moves.append(b.san(mv))
            b.push(mv)
        for idx in range(0, len(san_moves), 2):
            n = idx // 2 + 1
            white = san_moves[idx]
            black = san_moves[idx + 1] if idx + 1 < len(san_moves) else ''
            self.move_list.insert(tk.END, f"{n}. {white} {black}")
        game_over_now = False
        if self.board.is_checkmate():
            winner = 'Black' if self.board.turn == chess.WHITE else 'White'
            self.status.configure(text=f'Checkmate — {winner} wins')
            game_over_now = True
        elif self.board.is_stalemate():
            self.status.configure(text='Stalemate — draw')
            game_over_now = True
        elif self.board.is_insufficient_material():
            self.status.configure(text='Draw — insufficient material')
            game_over_now = True
        else:
            turn = 'White' if self.board.turn == chess.WHITE else 'Black'
            if self.board.is_check():
                self.status.configure(text=f'{turn} to move — CHECK!')
            else:
                self.status.configure(text=f'{turn} to move')
        try:
            hints = self._special_hints()
            self.hints_label.configure(text=hints)
        except Exception:
            try:
                self.hints_label.configure(text='')
            except Exception:
                pass
        self.update_controls_state()

        # If the game just ended, finalize AI learning once
        try:
            if game_over_now and hasattr(self, 'ai') and self.ai:
                if not getattr(self, '_learn_finalized', False):
                    result = 'draw'
                    if self.board.is_checkmate():
                        # If it's checkmate, current turn is the side that cannot move (was mated)
                        result = 'black' if self.board.turn == chess.WHITE else 'white'
                    self.ai.finalize_game(result)
                    self._learn_finalized = True
                    # Update learning status display
                    self.update_learning_status()
                    # Auto-save PGN if enabled
                    try:
                        if bool(self.autosave_pgn_var.get() if hasattr(self, 'autosave_pgn_var') else False) and not getattr(self, '_autosave_done', False):
                            self.autosave_pgn(result)
                            self._autosave_done = True
                    except Exception:
                        pass
                    # Auto-restart for AI vs AI if enabled
                    try:
                        if self.play_mode == 'ai_vs_ai' and bool(self.auto_restart_var.get() if hasattr(self, 'auto_restart_var') else False):
                            if not self._auto_restart_scheduled:
                                self._auto_restart_scheduled = True
                                # Give a brief pause to let user see result
                                self.master.after(1000, self._auto_restart_ai_game)
                    except Exception:
                        pass
            elif not game_over_now:
                # Reset flag during ongoing games
                self._learn_finalized = False
                self._auto_restart_scheduled = False
        except Exception:
            pass

    def new_game(self) -> None:
        """Start a fresh game, clearing the board and state."""
        try:
            # Increment session to abort any in-flight AI moves
            self._ai_session_id += 1
            self.ai_thinking = False
            # Reset board/state
            self.board = chess.Board()
            self.selected = None
            self.move_history = []
            self.ai_last_explanation = ''
            # Reset learning finalize flag
            self._learn_finalized = False
            # Reset autosave flag
            self._autosave_done = False
            # Stop the game - require Start button press
            self.game_started = False
            self._update_start_pause_button()
            self.update_board(force=True)
        except Exception as e:
            messagebox.showerror('New Game', f'Failed to start new game: {e}')

    def restart_game(self) -> None:
        """Restart the current game (alias of New Game), preserving mode and settings."""
        self.new_game()

    def _auto_restart_ai_game(self) -> None:
        """Internal: auto-restart a new AI vs AI game after a conclusion."""
        try:
            # Ensure still in AI vs AI and auto-restart still requested
            if self.play_mode != 'ai_vs_ai' or not (self.auto_restart_var.get() if hasattr(self, 'auto_restart_var') else False):
                self._auto_restart_scheduled = False
                return
            self._auto_restart_scheduled = False
            self.new_game()
            # Auto-start the game for AI vs AI
            self.game_started = True
            self._update_start_pause_button()
            if not self.board.is_game_over():
                current_depth = max(1, self.depth_var.get())
                self.ai_thinking = True
                self.status.config(text='AI is thinking...')
                self.master.config(cursor='watch')
                threading.Thread(target=self.run_ai_move, args=(current_depth,), daemon=True).start()
        except Exception:
            self._auto_restart_scheduled = False

    def on_clock_timeout(self, is_white: bool) -> None:
        """Handle chess clock timeout."""
        winner = "Black" if is_white else "White"
        self.status.configure(text=f"Time's up! {winner} wins on time")
        messagebox.showinfo("Time's Up!", f"{winner} wins on time!")
        if self.config:
            result = 'black' if is_white else 'white'
            self.config.update_statistics(result)
    
    def flip_board(self) -> None:
        """Flip the board orientation."""
        try:
            if hasattr(self.board_view, 'flip_board'):
                self.board_view.flip_board()  # type: ignore
                if self.config:
                    self.config.set('board_flipped', not self.config.get('board_flipped', False))
            self.update_board()
        except Exception as e:
            print(f"Board flip not supported: {e}")
    
    def change_theme(self, theme: str) -> None:
        """Change the color theme."""
        try:
            # Keep board visuals constant; if BoardView supports set_theme, it may still use it for labels, etc.
            if hasattr(self.board_view, 'set_theme'):
                self.board_view.set_theme(theme)  # type: ignore
            if self.config:
                self.config.set('theme', theme)
            # Apply background/foreground styles to UI, not the board squares
            self.apply_theme_to_ui(theme)
            self.update_board()
        except Exception as e:
            print(f"Theme change not supported: {e}")

    def apply_theme_to_ui(self, theme: str) -> None:
        """Apply theme colors to app background and control panels only."""
        try:
            palette = THEMES.get(theme, THEMES['light'])
            bg = palette.get('bg', '#F5F5F5')
            fg = palette.get('fg', '#000000')
            btn_bg = palette.get('button_bg', '#E0E0E0')

            # Root window
            try:
                self.master.configure(bg=bg)
            except Exception:
                pass

            # Status and hints labels
            for lbl in (getattr(self, 'status', None), getattr(self, 'hints_label', None)):
                try:
                    if lbl:
                        lbl.configure(bg=bg, fg=fg)
                except Exception:
                    pass

            # Control panel frames/canvas
            for w in (
                getattr(self, 'ctrl_frame', None),
                getattr(self, 'ctrl_canvas', None),
                getattr(self, 'scrollable_frame', None),
                getattr(self, 'features_frame', None),
                getattr(self, 'engine_frame', None),
            ):
                try:
                    if w:
                        w.configure(bg=bg)
                except Exception:
                    pass
        except Exception:
            pass
    
    def change_mode(self) -> None:
        """Change game mode between player vs player and player vs AI."""
        self.play_mode = self.mode_var.get()
        if self.config:
            self.config.set('play_mode', self.play_mode)
        
        if self.play_mode == 'ai_vs_ai':
            mode_text = "AI vs AI"
        elif self.play_mode == 'player_vs_ai':
            mode_text = "Player vs AI"
        elif self.play_mode == 'training_ai':
            mode_text = "Training AI (No UI)"
        else:
            mode_text = "Player vs Player"
        print(f"Game mode changed to: {mode_text}")
        # Stop the game when mode changes - require Start button press
        self.game_started = False
        self._update_start_pause_button()
        
        # Stop training AI if switching away from training mode
        if self.play_mode != 'training_ai' and self.training_ai and self.training_ai.running:
            self.stop_training_ai()
        
        # If entering training mode, start training AI
        if self.play_mode == 'training_ai':
            self.start_training_ai()
    
    def toggle_game_started(self) -> None:
        """Toggle game started state (Start/Pause button)."""
        self.game_started = not self.game_started
        self._update_start_pause_button()
        
        # If starting the game and it's AI's turn (or AI vs AI), trigger AI move
        if self.game_started and not self.board.is_game_over():
            if self.play_mode == 'ai_vs_ai':
                # Start AI vs AI game
                current_depth = max(1, self.depth_var.get())
                self.ai_thinking = True
                self.status.config(text='AI is thinking...')
                self.master.config(cursor='watch')
                threading.Thread(target=self.run_ai_move, args=(current_depth,), daemon=True).start()
            elif self.play_mode == 'player_vs_ai' and self.board.turn == chess.BLACK:
                # If it's black's turn and black is AI, start AI move
                current_depth = max(1, self.depth_var.get())
                self.ai_thinking = True
                self.status.config(text='AI is thinking...')
                self.master.config(cursor='watch')
                threading.Thread(target=self.run_ai_move, args=(current_depth,), daemon=True).start()
            elif self.play_mode == 'training_ai':
                # Start training AI
                self.start_training_ai()
        elif not self.game_started and self.play_mode == 'training_ai':
            # Stop training AI
            self.stop_training_ai()
    
    def start_training_ai(self) -> None:
        """Start headless training AI mode."""
        try:
            # Stop any existing training
            if self.training_ai and self.training_ai.running:
                self.training_ai.stop()
            
            # Get current AI depth
            current_depth = max(1, self.depth_var.get())
            
            # Create new training AI instance from UI settings
            batch_size = max(1, int(self.training_batch_size_var.get() if hasattr(self, 'training_batch_size_var') else 100))
            move_time_limit = max(0.05, (self.training_move_time_var.get() if hasattr(self, 'training_move_time_var') else 250) / 1000.0)
            snapshot_batches = int(self.training_snapshot_interval_var.get() if hasattr(self, 'training_snapshot_interval_var') else 0)
            export_interval = None if snapshot_batches <= 0 else snapshot_batches
            self.training_ai = TrainingAI(self.ai, depth=current_depth, batch_size=batch_size, export_interval=export_interval, move_time_limit=move_time_limit)

            # Persist training settings
            if self.config:
                try:
                    self.config.set('training_batch_size', batch_size)
                    self.config.set('training_move_time_ms', int(move_time_limit * 1000))
                    self.config.set('training_snapshot_batches', int(0 if export_interval is None else export_interval))
                    self.config.set('training_games', int(self.training_games_var.get() if hasattr(self, 'training_games_var') else 0))
                except Exception:
                    pass
            self.training_ai.start()
            
            # Update UI
            self.status.config(text='Training AI running (headless)...')
            self.game_started = True
            self._update_start_pause_button()
            # Begin polling to reflect progress in the status bar
            try:
                self._poll_training_status()
            except Exception:
                pass
        except Exception as e:
            print(f"Error starting training AI: {e}")
            messagebox.showerror('Training AI', f'Failed to start training: {e}')
    
    def stop_training_ai(self) -> None:
        """Stop headless training AI mode."""
        try:
            if self.training_ai and self.training_ai.running:
                self.training_ai.stop()
                self.training_ai = None
            
            # Update UI
            self.status.config(text='Training AI stopped')
            try:
                if hasattr(self, 'training_stats_label'):
                    self.training_stats_label.config(text='Training stopped')
            except Exception:
                pass
            self.game_started = False
            self._update_start_pause_button()
        except Exception as e:
            print(f"Error stopping training AI: {e}")

    def _poll_training_status(self) -> None:
        """Periodically update the status label with training progress."""
        try:
            if self.training_ai and getattr(self.training_ai, 'running', False):
                g = int(getattr(self.training_ai, 'games_played', 0))
                res = getattr(self.training_ai, 'results', {'white': 0, 'black': 0, 'draw': 0})
                mv = int(getattr(self.training_ai, 'current_move_count', 0))
                # Show current game's move count; games_played is completed games
                txt = f"Training AI: games {g}  moves:{mv}  W:{res.get('white',0)} B:{res.get('black',0)} D:{res.get('draw',0)}"
                self.status.config(text=txt)
                try:
                    if hasattr(self, 'training_stats_label'):
                        self.training_stats_label.config(text=f"Games: {g} | Moves: {mv} | W:{res.get('white',0)} B:{res.get('black',0)} D:{res.get('draw',0)}")
                except Exception:
                    pass
                # Poll again in ~1s
                self.master.after(1000, self._poll_training_status)
        except Exception:
            # Best-effort UI heartbeat; ignore transient errors
            try:
                self.master.after(1000, self._poll_training_status)
            except Exception:
                pass
    
    def _update_start_pause_button(self) -> None:
        """Update the Start/Pause button appearance based on game state."""
        if hasattr(self, 'start_pause_button'):
            if self.game_started:
                self.start_pause_button.config(text='\u23f8 Pause Game', bg='#ff9800')
            else:
                self.start_pause_button.config(text='\u25b6 Start Game', bg='#4CAF50')
    
    def toggle_sound(self) -> None:
        """Toggle sound effects on/off."""
        if self.sound:
            enabled = self.sound.toggle()
            if hasattr(self, 'sound_button'):
                self.sound_button.config(text=f"Sound: {'On' if enabled else 'Off'}")
            if self.config:
                self.config.set('sound_enabled', enabled)
    
    def toggle_clock(self) -> None:
        """Toggle chess clock on/off."""
        if not self.clock:
            return
        
        self.clock_enabled = not self.clock_enabled
        
        if self.clock_enabled:
            # Start the clock for current player
            self.clock.start(self.master, self.board.turn == chess.WHITE)
            self.clock_toggle_button.config(text='Disable Clock')
        else:
            self.clock.stop()
            self.clock_toggle_button.config(text='Enable Clock')
        
        if self.config:
            self.config.set('clock_enabled', self.clock_enabled)

    def on_toggle_compress(self) -> None:
        """Toggle gzip compression for learning data."""
        try:
            if hasattr(self, 'ai') and self.ai:
                val = bool(self.compress_learning_var.get())
                self.ai.compress_learning = val
                if self.config:
                    self.config.set('compress_learning', val)
        except Exception:
            pass

    def _build_training_cli(self) -> str:
        """Build the CLI command for training with current UI settings."""
        try:
            depth = max(1, int(self.depth_var.get())) if hasattr(self, 'depth_var') else 3
            batch = max(1, int(self.training_batch_size_var.get())) if hasattr(self, 'training_batch_size_var') else 100
            move_ms = int(self.training_move_time_var.get()) if hasattr(self, 'training_move_time_var') else 250
            snaps = int(self.training_snapshot_interval_var.get()) if hasattr(self, 'training_snapshot_interval_var') else 0
            games = int(self.training_games_var.get()) if hasattr(self, 'training_games_var') else 0
            compress = bool(self.compress_learning_var.get()) if hasattr(self, 'compress_learning_var') else True
            parts = ["python", "main.py", "--training", f"--depth", str(depth), f"--batch-size", str(batch), f"--move-ms", str(move_ms)]
            if snaps > 0:
                parts += ["--snapshot-batches", str(snaps)]
            if games > 0:
                parts += ["--games", str(games)]
            if not compress:
                parts += ["--no-compress"]
            return " ".join(parts)
        except Exception:
            return "python main.py --training"

    def copy_training_command(self) -> None:
        """Copy a ready-to-run training CLI command to clipboard."""
        try:
            cmd = self._build_training_cli()
            self.master.clipboard_clear()
            self.master.clipboard_append(cmd)
            try:
                self.master.update()
            except Exception:
                pass
            messagebox.showinfo('Training', 'Training command copied to clipboard.')
        except Exception as e:
            messagebox.showerror('Training', f'Failed to copy command: {e}')

    def run_training_now(self) -> None:
        """Launch a new console window running training with current settings."""
        try:
            import subprocess, sys, os
            # Ensure we run from the chess folder so main.py is resolvable
            cwd = os.path.dirname(__file__)
            # Build args list for robust subprocess call
            depth = max(1, int(self.depth_var.get())) if hasattr(self, 'depth_var') else 3
            batch = max(1, int(self.training_batch_size_var.get())) if hasattr(self, 'training_batch_size_var') else 100
            move_ms = int(self.training_move_time_var.get()) if hasattr(self, 'training_move_time_var') else 250
            snaps = int(self.training_snapshot_interval_var.get()) if hasattr(self, 'training_snapshot_interval_var') else 0
            games = int(self.training_games_var.get()) if hasattr(self, 'training_games_var') else 0
            compress = bool(self.compress_learning_var.get()) if hasattr(self, 'compress_learning_var') else True
            args = [sys.executable, 'main.py', '--training', '--depth', str(depth), '--batch-size', str(batch), '--move-ms', str(move_ms)]
            if snaps > 0:
                args += ['--snapshot-batches', str(snaps)]
            if games > 0:
                args += ['--games', str(games)]
            if not compress:
                args += ['--no-compress']
            creationflags = 0
            try:
                # On Windows, open in a new console window
                creationflags = getattr(subprocess, 'CREATE_NEW_CONSOLE', 0)
            except Exception:
                pass
            subprocess.Popen(args, cwd=cwd, creationflags=creationflags)
            messagebox.showinfo('Training', 'Started training in a new console window. Check that window for logs.\nUse Stop/Close there to end training.')
        except Exception as e:
            messagebox.showerror('Training', f'Failed to launch training: {e}')

    def reset_training_defaults(self) -> None:
        """Restore training and compression defaults and persist them."""
        try:
            # Defaults
            default_batch = 100
            default_move_ms = 250
            default_snap = 0
            default_compress = True
            # Update UI vars
            self.training_batch_size_var.set(default_batch)
            self.training_move_time_var.set(default_move_ms)
            self.training_snapshot_interval_var.set(default_snap)
            self.compress_learning_var.set(default_compress)
            # Apply compression immediately
            self.on_toggle_compress()
            # Persist training settings
            if self.config:
                self.config.set('training_batch_size', default_batch)
                self.config.set('training_move_time_ms', default_move_ms)
                self.config.set('training_snapshot_batches', default_snap)
        except Exception:
            pass

    # ---- Learning controls ----
    def reset_learning(self) -> None:
        try:
            if hasattr(self, 'ai') and self.ai:
                self.ai.learning_db = {}
                self.ai.game_log = []
                # Overwrite file
                try:
                    with open(self.ai._learning_path, 'w', encoding='utf-8') as f:
                        f.write('{}')
                except Exception:
                    pass
                self.update_learning_status()
                messagebox.showinfo('Learning', 'Learning data has been reset.')
        except Exception as e:
            messagebox.showerror('Learning', f'Failed to reset: {e}')

    def export_learning(self) -> None:
        try:
            if not hasattr(self, 'ai') or not self.ai:
                return
            path = filedialog.asksaveasfilename(defaultextension='.json', initialfile='ai_learn_readable.json',
                                                filetypes=[('JSON files', '*.json')])
            if not path:
                return
            out = self.ai.export_readable_learning(path)
            if out:
                messagebox.showinfo('Learning', f'Exported readable learning to:\n{out}')
            else:
                messagebox.showerror('Learning', 'Failed to export learning.')
        except Exception as e:
            messagebox.showerror('Learning', f'Failed to export: {e}')

    def import_learning(self) -> None:
        """Import learning data from a JSON file; accepts raw or readable format and merges counts."""
        try:
            if not hasattr(self, 'ai') or not self.ai:
                return
            path = filedialog.askopenfilename(filetypes=[('JSON files', '*.json')])
            if not path:
                return
            import json
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            merged = 0
            # Detect readable format
            if isinstance(data, dict) and 'positions' in data:
                positions = data.get('positions', {})
                for fen_key, entry in positions.items():
                    moves = entry.get('moves', {})
                    for uci, rec in moves.items():
                        key = f"{fen_key}|{uci}"
                        dest = self.ai.learning_db.get(key, {"w": 0, "l": 0, "d": 0})
                        dest['w'] = int(dest.get('w', 0)) + int(rec.get('wins', 0))
                        dest['l'] = int(dest.get('l', 0)) + int(rec.get('losses', 0))
                        dest['d'] = int(dest.get('d', 0)) + int(rec.get('draws', 0))
                        self.ai.learning_db[key] = dest
                        merged += 1
            elif isinstance(data, dict):
                # Raw format: key -> {w,l,d}
                for key, rec in data.items():
                    if not isinstance(rec, dict):
                        continue
                    dest = self.ai.learning_db.get(key, {"w": 0, "l": 0, "d": 0})
                    dest['w'] = int(dest.get('w', 0)) + int(rec.get('w', 0))
                    dest['l'] = int(dest.get('l', 0)) + int(rec.get('l', 0))
                    dest['d'] = int(dest.get('d', 0)) + int(rec.get('d', 0))
                    self.ai.learning_db[key] = dest
                    merged += 1
            else:
                messagebox.showerror('Learning', 'Unsupported file format.')
                return
            # Persist and regenerate readable file
            self.ai._save_learning_db()
            try:
                self.ai.export_readable_learning()
            except Exception:
                pass
            self.update_learning_status()
            messagebox.showinfo('Learning', f'Merged {merged} entries into learning database.')
        except Exception as e:
            messagebox.showerror('Learning', f'Failed to import: {e}')
    
    def update_learning_status(self) -> None:
        """Update the learning status display with current statistics."""
        try:
            if not hasattr(self, 'ai') or not self.ai or not hasattr(self, 'learning_status_label'):
                return
            
            # Count positions and total games learned
            position_count = len(self.ai.learning_db)
            total_games = 0
            
            for key, rec in self.ai.learning_db.items():
                wins = rec.get('w', 0)
                losses = rec.get('l', 0)
                draws = rec.get('d', 0)
                total_games += wins + losses + draws
            
            if position_count == 0:
                status_text = 'No learned data yet'
            else:
                status_text = f'Learned: {position_count} positions, {total_games} games'
            
            self.learning_status_label.config(text=status_text)
        except Exception:
            pass

    def show_learning_for_position(self) -> None:
        try:
            if not hasattr(self, 'ai') or not self.ai:
                return
            fen_key = self.board.fen().split(' ')[0]
            # Collect moves
            rows = []
            for mv in self.board.legal_moves:
                u = mv.uci()
                rec = self.ai.learning_db.get(fen_key + '|' + u)
                w = rec.get('w', 0) if rec else 0
                l = rec.get('l', 0) if rec else 0
                d = rec.get('d', 0) if rec else 0
                games = w + l + d
                winrate = 0.0 if games == 0 else (w + 0.5 * d) / games
                bonus = int((winrate - 0.5) * 200)
                rows.append((u, games, winrate, w, l, d, bonus))
            rows.sort(key=lambda r: (r[2], r[1]), reverse=True)
            # Show in a small dialog
            dlg = tk.Toplevel(self.master)
            dlg.title('Learning — Current Position')
            dlg.transient(self.master)
            dlg.grab_set()
            header = tk.Label(dlg, text='Move   Games   Winrate   W  L  D   Ordering bonus', font=('Arial', 9, 'bold'))
            header.pack(padx=8, pady=4)
            box = tk.Listbox(dlg, width=50, height=10, font=('Arial', 9))
            box.pack(padx=8, pady=4)
            if not rows:
                box.insert(tk.END, 'No learning yet for this position.')
            else:
                for (u, games, wr, w, l, d, bonus) in rows[:20]:
                    box.insert(tk.END, f'{u:6}  {games:5}   {wr:7.3f}   {w:2} {l:2} {d:2}   {bonus:+d}')
            tk.Button(dlg, text='Close', command=dlg.destroy, font=('Arial', 8)).pack(pady=6)
        except Exception as e:
            messagebox.showerror('Learning', f'Failed to show learning: {e}')
    
    def load_opening_book(self) -> None:
        """Load a Polyglot opening book (.bin file)."""
        try:
            if not HAS_POLYGLOT:
                messagebox.showinfo('Opening Book', 'Polyglot support not available.\nThe opening_book module may be missing.')
                return
            
            path = filedialog.askopenfilename(
                title='Select Polyglot Book',
                filetypes=[('Polyglot Book', '*.bin'), ('All files', '*.*')]
            )
            if not path:
                return
            
            success = self.ai.load_polyglot_book(path)
            if success:
                book_name = os.path.basename(path)
                if hasattr(self, 'book_status_label'):
                    self.book_status_label.config(text=f'Loaded: {book_name}', fg='green')
                messagebox.showinfo('Opening Book', f'Successfully loaded:\n{book_name}')
            else:
                if hasattr(self, 'book_status_label'):
                    self.book_status_label.config(text='Failed to load', fg='red')
                messagebox.showerror('Opening Book', 'Failed to load book.\nCheck file format.')
        except Exception as e:
            if hasattr(self, 'book_status_label'):
                self.book_status_label.config(text='Error', fg='red')
            messagebox.showerror('Opening Book', f'Error loading book:\n{e}')
    
    def unload_opening_book(self) -> None:
        """Unload the current Polyglot book."""
        try:
            if hasattr(self, 'ai') and self.ai:
                self.ai.unload_polyglot_book()
                if hasattr(self, 'book_status_label'):
                    self.book_status_label.config(text='No book loaded', fg='gray')
                messagebox.showinfo('Opening Book', 'Book unloaded successfully.')
        except Exception as e:
            messagebox.showerror('Opening Book', f'Error unloading book:\n{e}')
    
    def reset_clock(self) -> None:
        """Reset chess clock to initial time."""
        if not self.clock or not self.config:
            return
        
        clock_time = self.config.get('clock_time', 600)
        self.clock.reset(clock_time, clock_time)
        self.update_clock_display()
    
    def update_clock_display(self) -> None:
        """Update clock display labels."""
        if not self.clock:
            return
        
        try:
            if hasattr(self, 'white_clock_label'):
                self.white_clock_label.config(text=self.clock.get_time_string(True))
            if hasattr(self, 'black_clock_label'):
                self.black_clock_label.config(text=self.clock.get_time_string(False))
            
            # Schedule next update
            self.master.after(100, self.update_clock_display)
        except Exception:
            pass

    def on_depth_change(self, val):
        try:
            d = int(self.depth_var.get())
            self.ai.depth = max(1, d)
        except Exception:
            pass

    def load_piece_images(self):
        assets_dir = os.path.join(os.path.dirname(__file__), 'assets')
        imgs = {}
        try:
            for sym in ['P','N','B','R','Q','K','p','n','b','r','q','k']:
                fname = None
                if sym.isupper():
                    short = 'w' + sym.lower()
                else:
                    short = 'b' + sym.lower()
                for candidate in (f'{short}.png', f'{sym}.png'):
                    path = os.path.join(assets_dir, candidate)
                    if os.path.exists(path):
                        fname = path
                        break
                if not fname:
                    continue
                try:
                    im = Image.open(fname).convert('RGBA')
                    im = im.resize((48, 48), Image.LANCZOS)
                    imgs[sym] = ImageTk.PhotoImage(im)
                except Exception:
                    imgs = {}
                    break
        except Exception:
            imgs = {}
        if imgs:
            self.piece_images = imgs
        else:
            # fallback: generate piece images programmatically
            try:
                gen_imgs = image_generator.create_all_piece_images(48)
                if gen_imgs and ImageTk:
                    imgs = {}
                    for sym, pil_img in gen_imgs.items():
                        imgs[sym] = ImageTk.PhotoImage(pil_img)
                    self.piece_images = imgs if imgs else None
                else:
                    self.piece_images = None
            except Exception:
                self.piece_images = None

    def load_overlay_icons(self):
        """Load or generate overlay icons for special moves."""
        try:
            gen_icons = image_generator.create_overlay_icons(48)
            if gen_icons and ImageTk:
                icons = {}
                for icon_type, pil_img in gen_icons.items():
                    icons[icon_type] = ImageTk.PhotoImage(pil_img)
                self.overlay_icons = icons if icons else None
            else:
                self.overlay_icons = None
        except Exception:
            self.overlay_icons = None

    def toggle_engine(self):
        if not self.engine_enabled:
            path = self.engine_path_var.get()
            if not path:
                messagebox.showerror('Engine', 'No engine path provided')
                return
            ok = self.engine_manager.start(path)
            if ok:
                self.engine_enabled = True
                self.engine_toggle.configure(text='Use Engine: On')
            else:
                messagebox.showerror('Engine', 'Failed to start engine (see logs)')
                self.engine_enabled = False
        else:
            try:
                self.engine_manager.stop()
            finally:
                self.engine_enabled = False
                self.engine_toggle.configure(text='Use Engine: Off')

    def on_close(self):
        try:
            if getattr(self.engine_manager, 'engine', None):
                try:
                    self.engine_manager.stop()
                except Exception:
                    pass
        finally:
            try:
                self.master.destroy()
            except Exception:
                pass

    def ask_promotion(self, color: int) -> 'Optional[int]':
        dlg = tk.Toplevel(self.master)
        dlg.title('Choose promotion')
        dlg.transient(self.master)
        dlg.grab_set()
        sel = {'choice': None}
        def choose(ch):
            sel['choice'] = ch
            dlg.destroy()
        frame = tk.Frame(dlg)
        frame.pack(padx=8, pady=8)
        use_imgs = bool(self.piece_images)
        self._promo_imgs = []
        
        piece_names = {
            chess.QUEEN: 'Queen',
            chess.ROOK: 'Rook',
            chess.BISHOP: 'Bishop',
            chess.KNIGHT: 'Knight'
        }
        
        def make_button(pt, row, colpos):
            # Create container frame for button and label
            container = tk.Frame(frame)
            container.grid(row=row, column=colpos, padx=4, pady=2)
            
            if use_imgs:
                key = {chess.QUEEN: 'Q', chess.ROOK: 'R', chess.BISHOP: 'B', chess.KNIGHT: 'N'}[pt]
                if color == chess.BLACK:
                    key = key.lower()
                img = self.piece_images.get(key) if self.piece_images else None
                if img:
                    b = tk.Button(container, image=img, width=48, height=48, command=lambda: choose(pt))
                    self._promo_imgs.append(img)
                    b.pack()
                    # Add label below the image
                    tk.Label(container, text=piece_names[pt], font=('Arial', 9)).pack()
                else:
                    b = tk.Button(container, text=piece_names[pt], width=8, command=lambda: choose(pt))
                    b.pack()
            else:
                b = tk.Button(container, text=piece_names[pt], width=8, command=lambda: choose(pt))
                b.pack()
        
        make_button(chess.QUEEN, 0, 0)
        make_button(chess.ROOK, 0, 1)
        make_button(chess.BISHOP, 1, 0)
        make_button(chess.KNIGHT, 1, 1)
        self.master.update_idletasks()
        dlg.update_idletasks()
        x = self.master.winfo_rootx() + (self.master.winfo_width() - dlg.winfo_width()) // 2
        y = self.master.winfo_rooty() + (self.master.winfo_height() - dlg.winfo_height()) // 2
        try:
            dlg.geometry(f'+{x}+{y}')
        except Exception:
            pass
        dlg.wait_window()
        try:
            self._promo_imgs = []
        except Exception:
            pass
        return sel['choice']

    def _special_hints(self) -> str:
        parts = []
        try:
            ep = self.board.ep_square
            if ep is not None:
                parts.append(f'En-passant target: {chess.square_name(ep)}')
        except Exception:
            pass
        try:
            rights = ''
            if self.board.has_kingside_castling_rights(chess.WHITE):
                rights += 'K'
            if self.board.has_queenside_castling_rights(chess.WHITE):
                rights += 'Q'
            if self.board.has_kingside_castling_rights(chess.BLACK):
                rights += 'k'
            if self.board.has_queenside_castling_rights(chess.BLACK):
                rights += 'q'
            if rights:
                parts.append(f'Castling: {rights}')
        except Exception:
            pass
        # Append AI rationale if available
        try:
            if getattr(self, 'ai_last_explanation', ''):
                parts.append(self.ai_last_explanation)
        except Exception:
            pass
        return ' | '.join(parts)

    def _apply_special_overlays(self) -> None:
        try:
            self.board_view.apply_special_overlays(self.board)
        except Exception:
            pass

    def show_legal_moves(self, square: int):
        try:
            self.board_view.show_legal_moves(self.board, square)
        except Exception:
            pass

    def undo_move(self):
        # Prevent undo while AI is thinking
        if self.ai_thinking:
            return
        try:
            if len(self.board.move_stack) > 0:
                self.board.pop()
                self.board_view.clear_highlights()
                self.selected = None
                self.update_board(force=True)
        except Exception:
            pass

    def update_controls_state(self):
        try:
            disabled = 'disabled' if self.board.is_game_over() else 'normal'
            try:
                self.depth_scale.configure(state=disabled)
            except Exception:
                pass
            try:
                self.detect_button.configure(state=disabled)
            except Exception:
                pass
            try:
                self.download_button.configure(state=disabled)
            except Exception:
                pass
            try:
                self.verify_button.configure(state=disabled)
            except Exception:
                pass
            try:
                self.engine_toggle.configure(state=disabled)
            except Exception:
                pass
        except Exception:
            pass

    def save_pgn(self):
        game = chess.pgn.Game()
        node = game
        b = chess.Board()
        for mv in self.board.move_stack:
            node = node.add_variation(mv)
            b.push(mv)
        file = filedialog.asksaveasfilename(defaultextension='.pgn', filetypes=[('PGN files', '*.pgn')])
        if file:
            with open(file, 'w', encoding='utf-8') as f:
                exporter = chess.pgn.FileExporter(f)
                game.accept(exporter)
            messagebox.showinfo('Saved', f'Saved PGN to {file}')

    def autosave_pgn(self, result: 'Optional[str]' = None) -> 'Optional[str]':
        """Automatically save the current game's PGN to an autosaves/ folder.

        Args:
            result: Optional winner string ('white'/'black'/'draw') to include in filename.

        Returns:
            The path to the saved PGN file, or None on failure.
        """
        try:
            autos_dir = os.path.join(os.path.dirname(__file__), 'autosaves')
            os.makedirs(autos_dir, exist_ok=True)
            # Build timestamped filename
            ts = time.strftime('%Y%m%d_%H%M%S')
            suffix = ''
            if result:
                suffix = f"_{result}"
            out_path = os.path.join(autos_dir, f'game_{ts}{suffix}.pgn')

            game = chess.pgn.Game()
            node = game
            b = chess.Board()
            for mv in self.board.move_stack:
                node = node.add_variation(mv)
                b.push(mv)
            with open(out_path, 'w', encoding='utf-8') as f:
                exporter = chess.pgn.FileExporter(f)
                game.accept(exporter)
            return out_path
        except Exception:
            return None

    def on_toggle_autosave(self) -> None:
        """Persist the auto-save PGN setting to config when toggled."""
        try:
            if self.config:
                var = getattr(self, 'autosave_pgn_var', None)
                val = bool(var.get()) if var is not None else False
                self.config.set('auto_save_pgn', val)
        except Exception:
            pass

    def load_pgn(self):
        file = filedialog.askopenfilename(filetypes=[('PGN files', '*.pgn')])
        if not file:
            return
        try:
            with open(file, 'r', encoding='utf-8') as f:
                game = chess.pgn.read_game(f)
            if game is None:
                messagebox.showerror('Error', 'No game found in PGN')
                return
            board = game.board()
            for mv in game.mainline_moves():
                board.push(mv)
            self.board = board
            self.update_board(force=True)
        except Exception as e:
            messagebox.showerror('Error', f'Failed to load PGN: {e}')

    def detect_engine(self):
        path = self.engine_manager.detect()
        if path:
            var = getattr(self, 'engine_path_var', None)
            if var is not None:
                var.set(path)
            messagebox.showinfo('Detected', f'Found stockfish at {path}')
        else:
            messagebox.showinfo('Not found', 'Stockfish not found (engines/ or PATH). Please install and/or provide path.')

    def download_engine(self):
        platform_var = getattr(self, 'platform_var', None)
        prefer = platform_var.get() if platform_var is not None else 'auto'
        gh_token = getattr(self, 'github_token', None)
        token = gh_token.get().strip() if gh_token is not None else ''
        proceed = messagebox.askyesno('Download Stockfish', 'Download Stockfish release from GitHub releases?\nProceed?')
        if not proceed:
            return
        found = self.engine_manager.download_stockfish(prefer_platform=prefer, token=token)
        if not found:
            messagebox.showerror('Download failed', 'Failed to download or extract Stockfish — check network or token.')
            return
        var = getattr(self, 'engine_path_var', None)
        if var is not None:
            var.set(found)
        messagebox.showinfo('Downloaded', f'Stockfish downloaded to {found}. You can now click Use Engine.')

    def verify_engine(self):
        var = getattr(self, 'engine_path_var', None)
        path = var.get() if var is not None else ''
        if not path:
            messagebox.showerror('Verify failed', 'No engine path provided')
            return
        if not os.path.exists(path) and shutil.which(path) is None:
            messagebox.showerror('Verify failed', 'Engine executable not found')
            return
        vr = getattr(self, 'verify_retries', None)
        vt = getattr(self, 'verify_timeout', None)
        bm = getattr(self, 'backoff_max', None)
        bv = getattr(self, 'backoff_var', None)
        ad = getattr(self, 'auto_download_var', None)
        retries = max(1, int(vr.get())) if vr is not None else 2
        timeout = float(vt.get()) if vt is not None else 0.05
        backoff = float(bm.get()) if bm is not None else 5.0
        strategy = bv.get() if bv is not None else 'linear'
        auto_dl = bool(ad.get()) if ad is not None else False
        platform_var = getattr(self, 'platform_var', None)
        prefer = platform_var.get() if platform_var is not None else 'auto'
        gh_token = getattr(self, 'github_token', None)
        token = gh_token.get().strip() if gh_token is not None else ''
        ok, msg, found_path = self.engine_manager.verify_engine(path, retries=retries, timeout=timeout, auto_download=auto_dl, prefer_platform=prefer, backoff=strategy, max_wait=backoff, token=token)
        if ok:
            if found_path:
                var = getattr(self, 'engine_path_var', None)
                if var is not None:
                    var.set(found_path)
            messagebox.showinfo('Verify OK', msg)
            vlog = getattr(self, 'verify_log', None)
            if vlog is not None:
                vlog.insert(tk.END, f'OK: {msg}')
        else:
            vlog = getattr(self, 'verify_log', None)
            if vlog is not None:
                vlog.insert(tk.END, f'ERR: {msg}')
            messagebox.showerror('Verify failed', msg)
