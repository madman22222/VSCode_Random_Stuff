import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Optional
import chess  # type: ignore - Handles all chess rules (movement, check, checkmate, castling, en passant, etc.)
import chess.pgn  # type: ignore
import chess.engine  # type: ignore
import threading
import time
import shutil
import os
try:
    from PIL import Image, ImageTk  # type: ignore
except Exception:
    from typing import Any
    Image: Any = None
    ImageTk: Any = None

from engine_manager import EngineManager
from board_view import BoardView
from constants import PIECE_UNICODE, LIGHT_COLOR, DARK_COLOR
import image_generator


class SimpleAI:
    """Basic negamax AI with material evaluation and alpha-beta pruning.

    Includes heuristics for promotions, captures, castling and checks to prefer
    special moves. The python-chess library ensures all moves follow official chess rules.
    """

    PIECE_VALUES = {
        chess.PAWN: 100,
        chess.KNIGHT: 320,
        chess.BISHOP: 330,
        chess.ROOK: 500,
        chess.QUEEN: 900,
        chess.KING: 20000,
    }

    def __init__(self, depth=3):
        self.depth = depth

    def evaluate(self, board: chess.Board) -> int:
        score = 0
        for piece_type in self.PIECE_VALUES:
            score += len(board.pieces(piece_type, chess.WHITE)) * self.PIECE_VALUES[piece_type]
            score -= len(board.pieces(piece_type, chess.BLACK)) * self.PIECE_VALUES[piece_type]
        return score if board.turn == chess.WHITE else -score

    def negamax(self, board: chess.Board, depth: int, alpha: int, beta: int) -> int:
        if depth == 0 or board.is_game_over():
            return self.evaluate(board)

        max_score = -9999999
        moves = list(board.legal_moves)
        moves.sort(key=lambda m: self._move_score(board, m), reverse=True)
        for move in moves:
            board.push(move)
            score = -self.negamax(board, depth - 1, -beta, -alpha)
            board.pop()
            if score > max_score:
                max_score = score
            alpha = max(alpha, score)
            if alpha >= beta:
                break
        return max_score

    def choose_move(self, board: chess.Board) -> 'Optional[chess.Move]':
        best_move = None
        best_score = -9999999
        alpha = -9999999
        beta = 9999999
        moves = list(board.legal_moves)
        moves.sort(key=lambda m: self._move_score(board, m), reverse=True)
        for move in moves:
            board.push(move)
            score = -self.negamax(board, self.depth - 1, -beta, -alpha)
            board.pop()
            if score > best_score:
                best_score = score
                best_move = move
            alpha = max(alpha, score)
        # prefer queen promotion explicitly
        try:
            if best_move is not None and best_move.promotion is not None and best_move.promotion != chess.QUEEN:
                for m in moves:
                    if m.from_square == best_move.from_square and m.to_square == best_move.to_square and m.promotion == chess.QUEEN:
                        best_move = m
                        break
        except Exception:
            pass
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


class GameController:
    """Coordinates the GUI view, AI, and engine manager.

    This class owns the game state and provides callbacks for UI events.
    """

    def __init__(self, master: tk.Tk):
        self.master = master
        self.master.title('Python Chess — AI / Engine')
        self.board = chess.Board()
        self.ai = SimpleAI(depth=3)
        self.engine_manager = EngineManager(os.path.dirname(__file__))
        self.engine_enabled = False
        self.engine = None
        self.piece_images = None
        self.overlay_icons = None
        self.selected = None
        self.ai_thinking = False  # Track when AI is making a move

        # build UI
        self.status = tk.Label(master, text='White to move', font=('Arial', 12))
        self.status.grid(row=0, column=0, columnspan=8)
        self.hints_label = tk.Label(master, text='', font=('Arial', 9), fg='#333333')
        self.hints_label.grid(row=1, column=0, columnspan=8)

        board_frame = tk.Frame(master)
        board_frame.grid(row=2, column=0, rowspan=8, columnspan=8)
        self.board_view = BoardView(board_frame, on_click=self.on_click)

        # Right-side controls (minimal copy from prior UI)
        ctrl_frame = tk.Frame(master)
        ctrl_frame.grid(row=2, column=8, rowspan=8, sticky='ns', padx=6)
        tk.Label(ctrl_frame, text='Moves').pack()
        self.move_list = tk.Listbox(ctrl_frame, width=20, height=20)
        self.move_list.pack(fill='y')

        btn_frame = tk.Frame(ctrl_frame)
        btn_frame.pack(pady=6)
        tk.Button(btn_frame, text='Save PGN', command=self.save_pgn).grid(row=0, column=0, padx=2)
        tk.Button(btn_frame, text='Load PGN', command=self.load_pgn).grid(row=0, column=1, padx=2)
        tk.Button(btn_frame, text='Undo', command=self.undo_move).grid(row=0, column=2, padx=2)

        engine_frame = tk.LabelFrame(ctrl_frame, text='Engine')
        engine_frame.pack(fill='x', pady=6)
        self.engine_path_var = tk.StringVar()
        self.engine_path_var.set(shutil.which('stockfish') or '')
        tk.Entry(engine_frame, textvariable=self.engine_path_var, width=24).pack(padx=4, pady=2)
        self.detect_button = tk.Button(engine_frame, text='Detect', command=self.detect_engine)
        self.detect_button.pack(pady=2)
        self.download_button = tk.Button(engine_frame, text='Download', command=self.download_engine)
        self.download_button.pack(pady=2)
        self.verify_button = tk.Button(engine_frame, text='Verify', command=self.verify_engine)
        self.verify_button.pack(pady=2)

        gh_frame = tk.Frame(engine_frame)
        gh_frame.pack(pady=2)
        tk.Label(gh_frame, text='Platform:').grid(row=0, column=0)
        self.platform_var = tk.StringVar()
        sysplat = os.name
        self.platform_var.set('auto')
        tk.OptionMenu(gh_frame, self.platform_var, 'auto', 'windows', 'macos', 'linux').grid(row=0, column=1)
        tk.Label(gh_frame, text='GitHub token:').grid(row=1, column=0)
        self.github_token = tk.StringVar()
        tk.Entry(gh_frame, textvariable=self.github_token, width=24, show='*').grid(row=1, column=1)

        tk.Label(ctrl_frame, text='Built-in AI depth').pack()
        self.depth_var = tk.IntVar(value=3)
        depth_scale = tk.Scale(ctrl_frame, from_=1, to=5, orient='horizontal', variable=self.depth_var, command=self.on_depth_change)
        depth_scale.pack()
        self.depth_scale = depth_scale

        self.load_piece_images()
        self.load_overlay_icons()

        # verification options
        opts = tk.Frame(engine_frame)
        opts.pack(pady=2)
        tk.Label(opts, text='Retries:').grid(row=0, column=0, sticky='w')
        self.verify_retries = tk.IntVar(value=2)
        tk.Spinbox(opts, from_=1, to=10, width=4, textvariable=self.verify_retries).grid(row=0, column=1, sticky='w')
        tk.Label(opts, text='Timeout(s):').grid(row=1, column=0, sticky='w')
        self.verify_timeout = tk.DoubleVar(value=0.05)
        tk.Entry(opts, width=6, textvariable=self.verify_timeout).grid(row=1, column=1, sticky='w')
        tk.Label(opts, text='Backoff:').grid(row=2, column=0, sticky='w')
        self.backoff_var = tk.StringVar(value='linear')
        tk.OptionMenu(opts, self.backoff_var, 'linear', 'exponential', 'constant').grid(row=2, column=1, sticky='w')
        tk.Label(opts, text='Max wait(s):').grid(row=3, column=0, sticky='w')
        self.backoff_max = tk.DoubleVar(value=5.0)
        tk.Entry(opts, width=6, textvariable=self.backoff_max).grid(row=3, column=1, sticky='w')
        self.auto_download_var = tk.BooleanVar(value=False)
        tk.Checkbutton(opts, text='Auto-download on failure', variable=self.auto_download_var).grid(row=4, column=0, columnspan=2, sticky='w')

        self.engine_toggle = tk.Button(engine_frame, text='Use Engine: Off', command=self.toggle_engine)
        self.engine_toggle.pack(pady=2)

        tk.Label(ctrl_frame, text='Verify log').pack()
        self.verify_log = tk.Listbox(ctrl_frame, width=40, height=6)
        self.verify_log.pack(fill='both', pady=2)

        # finalize
        self.update_board()
        master.protocol('WM_DELETE_WINDOW', self.on_close)

    # ---- UI callbacks and helpers (moved from previous main.py ChessGUI) ----
    def on_click(self, square):
        # Prevent moves while AI is thinking
        if self.ai_thinking:
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
                self.board.push(move)
                self.selected = None
                self.board_view.clear_highlights()
                self.update_board()
                self.master.update()
                if not self.board.is_game_over():
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
        time.sleep(0.2)
        move = None
        try:
            if self.engine_enabled and getattr(self.engine_manager, 'engine', None) is not None:
                try:
                    tm = 0.05 * depth
                    result = self.engine_manager.play(self.board, chess.engine.Limit(time=tm))
                    move = result.move
                except Exception:
                    move = None
            else:
                self.ai.depth = depth
                move = self.ai.choose_move(self.board)
            
            if move is not None:
                self.board.push(move)
        except Exception as e:
            print(f"Error in AI move: {e}")
        
        # Schedule GUI update on main thread
        self.master.after(0, self._finish_ai_move)
    
    def _finish_ai_move(self):
        """Called on main thread after AI move completes."""
        try:
            self.ai_thinking = False  # Unlock UI after AI move
            self.master.config(cursor='')  # Reset cursor to default
            self.update_board()
        except Exception as e:
            print(f"Error finishing AI move: {e}")
            self.ai_thinking = False
            self.master.config(cursor='')

    def update_board(self):
        # render pieces and move list
        try:
            self.board_view.update(self.board, self.piece_images)
            self.board_view.apply_special_overlays(self.board, self.overlay_icons)
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
        if self.board.is_checkmate():
            winner = 'Black' if self.board.turn == chess.WHITE else 'White'
            self.status.configure(text=f'Checkmate — {winner} wins')
        elif self.board.is_stalemate():
            self.status.configure(text='Stalemate — draw')
        elif self.board.is_insufficient_material():
            self.status.configure(text='Draw — insufficient material')
        else:
            turn = 'White' if self.board.turn == chess.WHITE else 'Black'
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
                self.update_board()
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
            self.update_board()
        except Exception as e:
            messagebox.showerror('Error', f'Failed to load PGN: {e}')

    def detect_engine(self):
        path = self.engine_manager.detect()
        if path:
            self.engine_path_var.set(path)
            messagebox.showinfo('Detected', f'Found stockfish at {path}')
        else:
            messagebox.showinfo('Not found', 'Stockfish not found (engines/ or PATH). Please install and/or provide path.')

    def download_engine(self):
        prefer = self.platform_var.get() if getattr(self, 'platform_var', None) else 'auto'
        token = self.github_token.get().strip() if getattr(self, 'github_token', None) else ''
        proceed = messagebox.askyesno('Download Stockfish', 'Download Stockfish release from GitHub releases?\nProceed?')
        if not proceed:
            return
        found = self.engine_manager.download_stockfish(prefer_platform=prefer, token=token)
        if not found:
            messagebox.showerror('Download failed', 'Failed to download or extract Stockfish — check network or token.')
            return
        self.engine_path_var.set(found)
        messagebox.showinfo('Downloaded', f'Stockfish downloaded to {found}. You can now click Use Engine.')

    def verify_engine(self):
        path = self.engine_path_var.get()
        if not path:
            messagebox.showerror('Verify failed', 'No engine path provided')
            return
        if not os.path.exists(path) and shutil.which(path) is None:
            messagebox.showerror('Verify failed', 'Engine executable not found')
            return
        retries = max(1, int(self.verify_retries.get())) if hasattr(self, 'verify_retries') else 2
        timeout = float(self.verify_timeout.get()) if hasattr(self, 'verify_timeout') else 0.05
        backoff = float(self.backoff_max.get()) if hasattr(self, 'backoff_max') else 5.0
        strategy = getattr(self, 'backoff_var', None) and self.backoff_var.get() or 'linear'
        auto_dl = bool(self.auto_download_var.get()) if hasattr(self, 'auto_download_var') else False
        ok, msg, found_path = self.engine_manager.verify_engine(path, retries=retries, timeout=timeout, auto_download=auto_dl, prefer_platform=self.platform_var.get(), backoff=strategy, max_wait=backoff, token=self.github_token.get().strip())
        if ok:
            if found_path:
                self.engine_path_var.set(found_path)
            messagebox.showinfo('Verify OK', msg)
            if hasattr(self, 'verify_log'):
                self.verify_log.insert(tk.END, f'OK: {msg}')
        else:
            if hasattr(self, 'verify_log'):
                self.verify_log.insert(tk.END, f'ERR: {msg}')
            messagebox.showerror('Verify failed', msg)
