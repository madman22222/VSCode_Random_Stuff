"""Enhanced board view with animations, drag-drop, themes, and more."""
import tkinter as tk
import os
from typing import Callable, Dict, Optional, Tuple
import chess
from constants import (
    PIECE_UNICODE, SQUARE_SIZE, THEMES, FILES, RANKS,
    ANIMATION_FRAMES, ANIMATION_DELAY,
    LIGHT_COLOR, DARK_COLOR, HIGHLIGHT_COLOR, LEGAL_MOVE_COLOR,
    CAPTURE_COLOR, LAST_MOVE_COLOR
)


class EnhancedBoardView:
    """Advanced chess board view with modern features.
    
    Features:
    - Theme support (light/dark)
    - Last move highlighting
    - Coordinate labels
    - Board flipping
    - Drag-and-drop
    - Move animations
    - Captured pieces display
    """

    def __init__(self, parent: tk.Widget, on_click: Callable[[int], None],
                 theme: str = 'light', show_coordinates: bool = True,
                 flipped: bool = False):
        self.parent = parent
        self.on_click = on_click
        self.theme = theme
        self.show_coordinates = show_coordinates
        self.flipped = flipped
        self.canvases: Dict[int, tk.Canvas] = {}
        self.piece_items: Dict[int, Optional[int]] = {}
        self.last_move: Optional[chess.Move] = None
        self.dragging_piece: Optional[int] = None
        self.drag_item: Optional[int] = None
        self.drag_canvas: Optional[tk.Canvas] = None
        self.animating = False
        self.high_contrast = False
        self.piece_style = 'Images'
        self.focus_square = chess.E2
        self._rendered_pieces = {}
        self._focus_render_key = None
        self._focused_canvas = None
        self.square_size = SQUARE_SIZE
        self._board = None
        self._piece_images = None
        self._scaled_images = {}
        self._source_images = None
        self._build_grid()
    
    def _get_colors(self) -> Dict[str, str]:
        """Get color palette for current theme."""
        return THEMES.get(self.theme, THEMES['light'])
    
    def _get_grid_position(self, square: int) -> Tuple[int, int]:
        """Convert chess square to grid row/col, accounting for flip."""
        rank = chess.square_rank(square)
        file = chess.square_file(square)
        
        if self.flipped:
            row = rank
            col = 7 - file
        else:
            row = 7 - rank
            col = file
        
        return row, col
    
    def _build_grid(self):
        """Build the board grid with canvases."""
        colors = self._get_colors()

        # Drop stale focus targets before widget destruction can dispatch FocusOut.
        self.canvases.clear()
        self._focused_canvas = None
        self._focus_render_key = None
        # Clear existing grid
        for widget in self.parent.winfo_children():
            widget.destroy()
        self.canvases.clear()
        self.piece_items.clear()
        self._rendered_pieces.clear()
        self._focus_render_key = None
        self._focused_canvas = None
        
        # Create coordinate labels if enabled
        if self.show_coordinates:
            # File labels (a-h) at bottom
            for c in range(8):
                file_idx = (7 - c) if self.flipped else c
                label = tk.Label(self.parent, text=FILES[file_idx],
                               font=('Arial', 10, 'bold'),
                               bg=colors['bg'], fg=colors['fg'])
                label.grid(row=8, column=c, sticky='n')
            
            # Rank labels (1-8) on right
            for r in range(8):
                rank_idx = r if self.flipped else (7 - r)
                label = tk.Label(self.parent, text=RANKS[rank_idx],
                               font=('Arial', 10, 'bold'),
                               bg=colors['bg'], fg=colors['fg'])
                label.grid(row=r, column=8, sticky='w', padx=2)
        
        # Create board squares
        for square in range(64):
            row, col = self._get_grid_position(square)
            rank = chess.square_rank(square)
            file = chess.square_file(square)
            
            # Determine square color
            # Theme should NOT affect base board squares; use fixed classic colors
            is_light = (rank + file) % 2 == 1
            square_color = self._base_color(is_light)
            
            canvas = tk.Canvas(self.parent, width=self.square_size, height=self.square_size,
                             bg=square_color, highlightthickness=0)
            canvas.grid(row=row, column=col)
            
            # Bind events
            canvas.bind('<Button-1>', lambda e, s=square: self._on_press(e, s))
            canvas.bind('<B1-Motion>', lambda e, s=square: self._on_drag(e, s))
            canvas.bind('<ButtonRelease-1>', lambda e, s=square: self._on_release(e, s))
            canvas.bind('<FocusIn>', lambda event: self._paint_focus())
            canvas.bind('<FocusOut>', lambda event: self._paint_focus())
            canvas.configure(cursor='hand2')
            
            self.canvases[square] = canvas
            self.piece_items[square] = None
    
    def _on_press(self, event: tk.Event, square: int) -> None:
        """Handle mouse press - start drag."""
        self.focus(square)
        self.dragging_piece = square
        # Will handle in on_click callback
    
    def _on_drag(self, event: tk.Event, square: int) -> None:
        """Handle mouse drag."""
        if self.dragging_piece is None or self.animating:
            return
        
        canvas = self.canvases.get(self.dragging_piece)
        if not canvas:
            return
        
        # Create floating piece if not already created
        if self.drag_item is None and self.piece_items.get(self.dragging_piece):
            # Store original item
            self.drag_item = self.piece_items[self.dragging_piece]
            self.drag_canvas = canvas
    
    def _on_release(self, event: tk.Event, square: int) -> None:
        """Handle mouse release - complete move."""
        if self.dragging_piece is not None:
            # Call the click handler with from and to squares
            self.on_click(self.dragging_piece)
            if square != self.dragging_piece:
                self.on_click(square)
        
        self.dragging_piece = None
        self.drag_item = None
        self.drag_canvas = None
    
    def flip_board(self) -> None:
        """Flip board orientation."""
        self.flipped = not self.flipped
        self._build_grid()
        self._restore_position()
    
    def set_theme(self, theme: str) -> None:
        """Change color theme."""
        if theme in THEMES:
            self.theme = theme
            self._build_grid()
            self._restore_position()
    
    def set_show_coordinates(self, show: bool) -> None:
        """Toggle coordinate labels."""
        self.show_coordinates = show
        self._build_grid()
        self._restore_position()
    
    def update(self, board: chess.Board, piece_images: Optional[dict]):
        """Render pieces for current board state."""
        self._board = board.copy()
        self._piece_images = piece_images
        if piece_images is not self._source_images:
            self._source_images = piece_images
            self._scaled_images.clear()

        for square, canvas in self.canvases.items():
            piece = board.piece_at(square)
            rank = chess.square_rank(square)
            file = chess.square_file(square)
            
            # Determine base square color
            # Use fixed base board colors regardless of theme
            is_light = (rank + file) % 2 == 1
            square_color = self._base_color(is_light)
            
            # Apply last move highlighting
            if self.last_move and square in [self.last_move.from_square, self.last_move.to_square]:
                square_color = self._highlight_color('last')
            
            canvas.configure(bg=square_color)
            
            stamp = (piece.symbol() if piece else None, self.square_size,
                     self.piece_style, id(piece_images), self.high_contrast)
            if self._rendered_pieces.get(square) == stamp:
                continue
            self._rendered_pieces[square] = stamp
            canvas.delete('piece')
            self.piece_items[square] = None
            if piece is None:
                continue
            img = self._scaled_piece(piece.symbol(), piece_images.get(piece.symbol())) if (
                piece_images and self.piece_style == 'Images') else None
            center = self.square_size // 2
            if img:
                item = canvas.create_image(center, center, image=img, tags='piece')
                setattr(canvas, '_img_ref', img)
            else:
                text = PIECE_UNICODE[piece.symbol()]
                fill = '#111827'
                if self.piece_style == 'Letters':
                    pad = self.square_size * .15
                    canvas.create_oval(pad, pad, self.square_size-pad, self.square_size-pad,
                        fill='white' if piece.color else '#111827', outline='#64748b', tags='piece')
                    text = piece.symbol().upper()
                    fill = '#111827' if piece.color else 'white'
                elif self.high_contrast:
                    # Symbols are drawn on a contrasting badge too.
                    pad = self.square_size * .08
                    canvas.create_oval(pad, pad, self.square_size-pad, self.square_size-pad,
                        fill='white', outline='#64748b', tags='piece')
                item = canvas.create_text(center, center, text=text, fill=fill, tags='piece',
                    font=('Segoe UI Symbol' if os.name == 'nt' else 'DejaVu Sans', max(10, int(self.square_size * (.42 if self.piece_style == 'Letters' else .65)))))
            self.piece_items[square] = item
        self._paint_focus()

    def _base_color(self, light):
        if self.high_contrast:
            return '#ffffff' if light else '#26364a'
        return LIGHT_COLOR if light else DARK_COLOR

    def _highlight_color(self, kind):
        normal = {'selected': HIGHLIGHT_COLOR, 'legal': LEGAL_MOVE_COLOR,
                  'capture': CAPTURE_COLOR, 'last': LAST_MOVE_COLOR}
        contrast = {'selected': '#ffcf00', 'legal': '#26c6da', 'capture': '#ff8a65', 'last': '#ffd180'}
        return (contrast if self.high_contrast else normal)[kind]

    def set_accessibility(self, high_contrast, piece_style):
        self.high_contrast = high_contrast
        self.piece_style = piece_style if piece_style in ('Images', 'Symbols', 'Letters') else 'Images'
        self._scaled_images.clear()
        self._rendered_pieces.clear()
        self._restore_position()

    def focus(self, square):
        self.focus_square = square
        self.canvases[square].focus_set()
        self._paint_focus()

    def _paint_focus(self):
        canvas = self.canvases.get(self.focus_square)
        active = bool(canvas and canvas.focus_get() == canvas)
        key = (self.focus_square, self.square_size, active)
        if key == self._focus_render_key:
            return
        self._focus_render_key = key
        if self._focused_canvas is not None:
            self._focused_canvas.delete('keyboard-focus')
        self._focused_canvas = canvas if active else None
        if active:
            edge = self.square_size - 2
            canvas.create_rectangle(2, 2, edge, edge, outline='#2563eb', width=3, tags='keyboard-focus')

    def _scaled_piece(self, key, image):
        if image is None:
            return None
        cache_key = (key, self.square_size)
        if cache_key not in self._scaled_images:
            from PIL import Image, ImageTk
            pixels = max(12, int(self.square_size * 0.82))
            original = ImageTk.getimage(image)
            self._scaled_images[cache_key] = ImageTk.PhotoImage(
                original.resize((pixels, pixels), Image.Resampling.LANCZOS), master=self.parent)
        return self._scaled_images[cache_key]

    def _restore_position(self):
        if self._board is not None:
            self.update(self._board, self._piece_images)

    def resize(self, square_size):
        """Resize existing cells; never rebuild widgets during a resize gesture."""
        if square_size == self.square_size:
            return
        self.square_size = square_size
        self._scaled_images.clear()
        for canvas in self.canvases.values():
            canvas.configure(width=square_size, height=square_size)
        self._restore_position()

    def animate_move(self, move: chess.Move, board: chess.Board,
                    piece_images: Optional[dict], callback: Optional[Callable] = None) -> None:
        """Animate a move from source to destination."""
        if self.animating:
            return
        
        self.animating = True
        from_square = move.from_square
        to_square = move.to_square
        
        from_row, from_col = self._get_grid_position(from_square)
        to_row, to_col = self._get_grid_position(to_square)
        
        # Get piece info
        piece = board.piece_at(from_square)
        if not piece:
            self.animating = False
            if callback:
                callback()
            return
        
        # Create animation canvas
        anim_canvas = tk.Canvas(self.parent, width=self.square_size, height=self.square_size,
                               bg='', highlightthickness=0)
        anim_canvas.grid(row=from_row, column=from_col)
        try:
            anim_canvas.lift(aboveThis=self.parent)  # type: ignore
        except Exception:
            pass
        
        # Draw piece on animation canvas
        if piece_images and piece.symbol() in piece_images:
            img = piece_images[piece.symbol()]
            anim_canvas.create_image(self.square_size // 2, self.square_size // 2, image=img)
            setattr(anim_canvas, '_img_ref', img)
        else:
            text = PIECE_UNICODE[piece.symbol()]
            anim_canvas.create_text(self.square_size // 2, self.square_size // 2,
                                               text=text,
                                               font=('Arial', int(self.square_size * 0.65), 'bold'),
                                               fill='black')
        
        # Calculate movement
        delta_row = to_row - from_row
        delta_col = to_col - from_col
        
        def animate_frame(frame: int = 0):
            if frame >= ANIMATION_FRAMES:
                anim_canvas.destroy()
                self.animating = False
                if callback:
                    callback()
                return
            
            # Calculate position
            progress = frame / ANIMATION_FRAMES
            new_row = from_row + (delta_row * progress)
            new_col = from_col + (delta_col * progress)
            
            # Move canvas
            anim_canvas.grid(row=from_row, column=from_col, rowspan=1, columnspan=1)
            anim_canvas.place(x=int(new_col * self.square_size), y=int(new_row * self.square_size))
            
            # Schedule next frame
            self.parent.after(ANIMATION_DELAY, lambda: animate_frame(frame + 1))
        
        # Start animation
        animate_frame()
    
    def highlight_last_move(self, move: Optional[chess.Move]) -> None:
        """Store last move for highlighting."""
        self.last_move = move
    
    def highlight(self, square: int):
        """Highlight a specific square."""
        canvas = self.canvases.get(square)
        if canvas:
            canvas.configure(bg=self._highlight_color('selected'))
    
    def clear_highlights(self):
        """Reset all squares to normal colors."""
        for square, canvas in self.canvases.items():
            rank = chess.square_rank(square)
            file = chess.square_file(square)
            # Restore fixed base board colors
            is_light = (rank + file) % 2 == 1
            square_color = self._base_color(is_light)
            
            # Preserve last move highlighting
            if self.last_move and square in [self.last_move.from_square, self.last_move.to_square]:
                square_color = self._highlight_color('last')
            
            canvas.configure(bg=square_color)
    
    def show_legal_moves(self, board: chess.Board, square: int):
        """Show legal moves for a piece."""
        self.clear_highlights()
        
        for move in board.legal_moves:
            if move.from_square == square:
                to_square = move.to_square
                canvas = self.canvases.get(to_square)
                if canvas:
                    if board.is_capture(move):
                        canvas.configure(bg=self._highlight_color('capture'))
                    else:
                        canvas.configure(bg=self._highlight_color('legal'))
    
    def apply_special_overlays(self, board: chess.Board, overlay_icons: Optional[dict] = None):
        """Apply overlays for special moves."""
        # Implementation similar to original
        pass
