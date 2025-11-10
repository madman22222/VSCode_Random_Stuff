import tkinter as tk
from typing import Callable, Dict, Optional
import chess
from constants import PIECE_UNICODE, LIGHT_COLOR, DARK_COLOR


class BoardView:
    """Encapsulates the 8x8 grid of tkinter Buttons that represent the chessboard.

    Responsibilities:
    - Create the button grid inside a provided container
    - Render pieces (using provided piece_images mapping or unicode fallback)
    - Provide highlight/clear functions and apply overlays for special moves
    - Forward clicks through a provided callback
    """

    def __init__(self, parent: tk.Widget, on_click: Callable[[int], None]):
        self.parent = parent
        self.on_click = on_click
        self.canvases: Dict[int, tk.Canvas] = {}
        self.piece_items: Dict[int, Optional[int]] = {}  # Canvas text/image item IDs
        self._build_grid()

    def _build_grid(self):
        for r in range(8):
            for c in range(8):
                sq = chess.square(c, 7 - r)
                
                # Use Canvas instead of Button+Label for better control
                color = LIGHT_COLOR if (r + c) % 2 == 0 else DARK_COLOR
                canvas = tk.Canvas(self.parent, width=60, height=60,
                                  bg=color, highlightthickness=0)
                canvas.grid(row=r, column=c)
                canvas.bind('<Button-1>', lambda e, s=sq: self.on_click(s))
                canvas.configure(cursor='hand2')
                self.canvases[sq] = canvas
                
                # Create a placeholder for the piece (will be updated later)
                self.piece_items[sq] = None

    def update(self, board: chess.Board, piece_images: Optional[dict]):
        """Render pieces for current board state.

        piece_images: dict mapping piece.symbol() to PhotoImage (or None)
        """
        for sq, canvas in self.canvases.items():
            piece = board.piece_at(sq)
            
            # Always keep square color
            r = 7 - chess.square_rank(sq)
            c = chess.square_file(sq)
            color = LIGHT_COLOR if (r + c) % 2 == 0 else DARK_COLOR
            canvas.configure(bg=color)
            
            # Clear existing piece
            if self.piece_items[sq] is not None:
                try:
                    item_id = self.piece_items[sq]
                    if item_id is not None:
                        canvas.delete(item_id)
                except Exception:
                    pass
                self.piece_items[sq] = None
            
            # Display piece
            if piece is not None:
                if piece_images:
                    key = piece.symbol()
                    img = piece_images.get(key)
                    if img:
                        # Draw image at center
                        item_id = canvas.create_image(30, 30, image=img)
                        self.piece_items[sq] = item_id
                        # Keep reference to prevent GC
                        setattr(canvas, '_img_ref', img)
                    else:
                        # Fallback to Unicode
                        text = PIECE_UNICODE[piece.symbol()]
                        item_id = canvas.create_text(30, 30, text=text, 
                                                     font=('Arial', 36, 'bold'), 
                                                     fill='black')
                        self.piece_items[sq] = item_id
                else:
                    # Use Unicode characters for pieces
                    text = PIECE_UNICODE[piece.symbol()]
                    item_id = canvas.create_text(30, 30, text=text, 
                                                 font=('Arial', 36, 'bold'), 
                                                 fill='black')
                    self.piece_items[sq] = item_id

    def highlight(self, square: int):
        # Reset all squares to normal color
        for sq, canvas in self.canvases.items():
            r = 7 - chess.square_rank(sq)
            c = chess.square_file(sq)
            color = LIGHT_COLOR if (r + c) % 2 == 0 else DARK_COLOR
            canvas.configure(bg=color)
        
        # Highlight selected square with bright color
        try:
            self.canvases[square].configure(bg='#AAFF88')
        except Exception:
            pass

    def clear_highlights(self):
        for sq, canvas in self.canvases.items():
            r = 7 - chess.square_rank(sq)
            c = chess.square_file(sq)
            color = LIGHT_COLOR if (r + c) % 2 == 0 else DARK_COLOR
            canvas.configure(bg=color)

    def show_legal_moves(self, board: chess.Board, square: int):
        self.clear_highlights()
        for mv in board.legal_moves:
            if mv.from_square == square:
                to_sq = mv.to_square
                canvas = self.canvases.get(to_sq)
                if not canvas:
                    continue
                if board.is_capture(mv):
                    canvas.configure(bg='#FF8888')
                else:
                    canvas.configure(bg='#88FFDD')

    def apply_special_overlays(self, board: chess.Board, overlay_icons: Optional[dict] = None):
        """Apply small icon overlays for en-passant and castling markers.
        
        overlay_icons: dict with 'ep' and 'castle' keys mapping to PhotoImage icons.
        """
        # en-passant target
        try:
            ep = board.ep_square
            if ep is not None:
                canvas = self.canvases.get(ep)
                if canvas and overlay_icons and 'ep' in overlay_icons:
                    # Draw small overlay icon
                    try:
                        canvas.create_image(45, 45, image=overlay_icons['ep'], anchor='se')
                        setattr(canvas, '_overlay_ref', overlay_icons['ep'])
                    except Exception:
                        pass
        except Exception:
            pass

        # castling destinations
        try:
            for mv in board.legal_moves:
                piece = board.piece_at(mv.from_square)
                if piece is not None and piece.piece_type == chess.KING:
                    try:
                        if abs(chess.square_file(mv.from_square) - chess.square_file(mv.to_square)) == 2:
                            canvas = self.canvases.get(mv.to_square)
                            if canvas:
                                # Add subtle border to indicate castling square
                                canvas.configure(highlightthickness=2, highlightbackground='#FFAA00')
                    except Exception:
                        pass
        except Exception:
            pass
