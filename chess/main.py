"""Simple Python chess GUI with a basic AI.

Run: python main.py

Dependencies: python-chess, Pillow (optional for PNG piece images)

Controls:
- Click a square to select a piece, then click destination to move.
- After your move (white by default), the AI or engine will reply.

Notes for the editor/linter:
This file interacts with external packages (python-chess, Pillow). If the
editor reports missing imports or unknown attributes, make sure the Python
environment used by the editor has the dependencies installed. The repository
also includes a `chess/requirements.txt` with the required packages.

To reduce noisy diagnostics in editors that use Pyright/Pylance, some checks
are disabled below when the analyzer is used.
"""

# pyright: reportMissingImports=false, reportUnknownMemberType=false

import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Optional
import chess  # type: ignore
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
import urllib.request
import json
import zipfile
import platform
import tempfile
import subprocess

# Map pieces to Unicode symbols for display
PIECE_UNICODE = {
    'P': '♙', 'N': '♘', 'B': '♗', 'R': '♖', 'Q': '♕', 'K': '♔',
    'p': '♟', 'n': '♞', 'b': '♝', 'r': '♜', 'q': '♛', 'k': '♚',
}

LIGHT_COLOR = '#F0D9B5'
DARK_COLOR = '#B58863'


class SimpleAI:
    """Basic negamax AI with material evaluation and alpha-beta pruning."""

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
        """Simple material evaluation: positive means advantage for white."""
        score = 0
        for piece_type in self.PIECE_VALUES:
            score += len(board.pieces(piece_type, chess.WHITE)) * self.PIECE_VALUES[piece_type]
            score -= len(board.pieces(piece_type, chess.BLACK)) * self.PIECE_VALUES[piece_type]
        return score if board.turn == chess.WHITE else -score

    def negamax(self, board: chess.Board, depth: int, alpha: int, beta: int) -> int:
        if depth == 0 or board.is_game_over():
            return self.evaluate(board)

        max_score = -9999999
        for move in board.legal_moves:
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
        for move in board.legal_moves:
            board.push(move)
            score = -self.negamax(board, self.depth - 1, -beta, -alpha)
            board.pop()
            if score > best_score:
                best_score = score
                best_move = move
            alpha = max(alpha, score)
        return best_move


class ChessGUI:
    def __init__(self, master):
        self.master = master
        master.title('Python Chess — AI / Engine')

        self.board = chess.Board()
        self.ai = SimpleAI(depth=3)
        self.engine = None
        self.engine_enabled = False
        self.buttons = {}
        self.selected = None
        self.piece_images = None

        # top status
        self.status = tk.Label(master, text='White to move', font=('Arial', 12))
        self.status.grid(row=0, column=0, columnspan=8)

        # board
        board_frame = tk.Frame(master)
        board_frame.grid(row=1, column=0, rowspan=8, columnspan=8)

        for r in range(8):
            for c in range(8):
                sq = chess.square(c, 7 - r)  # map row/col to square (a1 bottom-left)
                btn = tk.Button(board_frame, text='', font=('Arial', 24), width=2, height=1,
                                command=lambda s=sq: self.on_click(s))
                color = LIGHT_COLOR if (r + c) % 2 == 0 else DARK_COLOR
                btn.configure(bg=color)
                btn.grid(row=r, column=c)
                self.buttons[sq] = btn

        # right-side controls: move list, PGN save/load, engine toggle
        ctrl_frame = tk.Frame(master)
        ctrl_frame.grid(row=1, column=8, rowspan=8, sticky='ns', padx=6)

        tk.Label(ctrl_frame, text='Moves').pack()
        self.move_list = tk.Listbox(ctrl_frame, width=20, height=20)
        self.move_list.pack(fill='y')

        btn_frame = tk.Frame(ctrl_frame)
        btn_frame.pack(pady=6)

        tk.Button(btn_frame, text='Save PGN', command=self.save_pgn).grid(row=0, column=0, padx=2)
        tk.Button(btn_frame, text='Load PGN', command=self.load_pgn).grid(row=0, column=1, padx=2)
        tk.Button(btn_frame, text='Undo', command=self.undo_move).grid(row=0, column=2, padx=2)

        # engine controls
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
        # GitHub token and platform selector for downloads
        gh_frame = tk.Frame(engine_frame)
        gh_frame.pack(pady=2)
        tk.Label(gh_frame, text='Platform:').grid(row=0, column=0)
        self.platform_var = tk.StringVar()
        # detect default platform
        sysplat = platform.system().lower()
        if sysplat.startswith('win'):
            default_plat = 'windows'
        elif sysplat.startswith('darwin'):
            default_plat = 'macos'
        else:
            default_plat = 'linux'
        self.platform_var.set('auto')
        tk.OptionMenu(gh_frame, self.platform_var, 'auto', 'windows', 'macos', 'linux').grid(row=0, column=1)
        tk.Label(gh_frame, text='GitHub token:').grid(row=1, column=0)
        self.github_token = tk.StringVar()
        tk.Entry(gh_frame, textvariable=self.github_token, width=24, show='*').grid(row=1, column=1)

        # AI depth slider for built-in AI
        tk.Label(ctrl_frame, text='Built-in AI depth').pack()
        self.depth_var = tk.IntVar(value=3)
        depth_scale = tk.Scale(ctrl_frame, from_=1, to=5, orient='horizontal', variable=self.depth_var, command=self.on_depth_change)
        depth_scale.pack()
        self.depth_scale = depth_scale

        # try to load piece images (assets/)
        self.load_piece_images()

        # verification options
        opts = tk.Frame(engine_frame)
        opts.pack(pady=2)
        tk.Label(opts, text='Retries:').grid(row=0, column=0, sticky='w')
        self.verify_retries = tk.IntVar(value=2)
        tk.Spinbox(opts, from_=1, to=10, width=4, textvariable=self.verify_retries).grid(row=0, column=1, sticky='w')
        tk.Label(opts, text='Timeout(s):').grid(row=1, column=0, sticky='w')
        self.verify_timeout = tk.DoubleVar(value=0.05)
        tk.Entry(opts, width=6, textvariable=self.verify_timeout).grid(row=1, column=1, sticky='w')
        # backoff strategy and max wait
        tk.Label(opts, text='Backoff:').grid(row=2, column=0, sticky='w')
        self.backoff_var = tk.StringVar(value='linear')
        tk.OptionMenu(opts, self.backoff_var, 'linear', 'exponential', 'constant').grid(row=2, column=1, sticky='w')
        tk.Label(opts, text='Max wait(s):').grid(row=3, column=0, sticky='w')
        self.backoff_max = tk.DoubleVar(value=5.0)
        tk.Entry(opts, width=6, textvariable=self.backoff_max).grid(row=3, column=1, sticky='w')
        # auto-download on failure
        self.auto_download_var = tk.BooleanVar(value=False)
        tk.Checkbutton(opts, text='Auto-download on failure', variable=self.auto_download_var).grid(row=4, column=0, columnspan=2, sticky='w')

        self.engine_toggle = tk.Button(engine_frame, text='Use Engine: Off', command=self.toggle_engine)
        self.engine_toggle.pack(pady=2)

        # verification log
        tk.Label(ctrl_frame, text='Verify log').grid(row=9, column=0)
        self.verify_log = tk.Listbox(ctrl_frame, width=40, height=6)
        self.verify_log.grid(row=10, column=0)

        self.update_board()

        # ensure engine cleaned on close
        master.protocol('WM_DELETE_WINDOW', self.on_close)

    def on_click(self, square):
        if self.board.is_game_over():
            return
        piece = self.board.piece_at(square)
        if self.selected is None:
            # select a piece
            if piece is None:
                return
            if piece.color != self.board.turn:
                return
            self.selected = square
            self.highlight(square)
            # highlight legal moves from this square
            self.show_legal_moves(square)
        else:
            # handle promotions: if a pawn moves to the last rank, ask which piece
            move = None
            sel_piece = self.board.piece_at(self.selected)
            promotes = False
            if sel_piece is not None and sel_piece.piece_type == chess.PAWN:
                r = chess.square_rank(square)
                # white promotes on rank 7, black promotes on rank 0
                if (sel_piece.color == chess.WHITE and r == 7) or (sel_piece.color == chess.BLACK and r == 0):
                    promotes = True

            if promotes:
                assert sel_piece is not None
                promo = self.ask_promotion(sel_piece.color)  # type: ignore[attr-defined]
                if promo is None:
                    # user cancelled promotion selection
                    self.selected = None
                    self.update_board()
                    return
                move = chess.Move(self.selected, square, promotion=promo)
            else:
                move = chess.Move(self.selected, square)

            if move in self.board.legal_moves:
                self.board.push(move)
                self.selected = None
                self.clear_highlights()
                self.update_board()
                self.master.update()
                # run AI/engine move in background thread so UI stays responsive
                if not self.board.is_game_over():
                    threading.Thread(target=self.run_ai_move, daemon=True).start()
            else:
                # if clicking another piece of same color, change selection
                if piece is not None and piece.color == self.board.turn:
                    self.selected = square
                    self.update_board()

    def run_ai_move(self):
        # small delay to make AI feel more human
        time.sleep(0.2)
        move = None
        if self.engine_enabled and self.engine is not None:
            try:
                tm = 0.05 * max(1, self.depth_var.get())
                result = self.engine.play(self.board, chess.engine.Limit(time=tm))
                move = result.move
            except Exception:
                move = None
        else:
            self.ai.depth = max(1, self.depth_var.get())
            move = self.ai.choose_move(self.board)

        if move is not None:
            self.board.push(move)
        self.update_board()

    def highlight(self, square):
        for sq, btn in self.buttons.items():
            r = 7 - chess.square_rank(sq)
            c = chess.square_file(sq)
            color = LIGHT_COLOR if (r + c) % 2 == 0 else DARK_COLOR
            btn.configure(bg=color)
        # highlight selected
        self.buttons[square].configure(bg='#AAFF88')

    def update_board(self):
        for sq, btn in self.buttons.items():
            piece = self.board.piece_at(sq)
            if self.piece_images and piece is not None:
                key = piece.symbol()
                img = self.piece_images.get(key)
                if img:
                    btn.configure(image=img, text='')
                    btn.image = img
                else:
                    btn.configure(image='', text=PIECE_UNICODE[piece.symbol()])
            else:
                text = PIECE_UNICODE[piece.symbol()] if piece is not None else ''
                btn.configure(text=text, image='')

        # update move list (show SAN moves grouped by move number)
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

    def on_depth_change(self, val):
        """Handler for depth scale changes."""
        try:
            d = int(self.depth_var.get())
            self.ai.depth = max(1, d)
        except Exception:
            pass

    def load_piece_images(self):
        """Try to load PNG piece images from chess/assets/. If Pillow isn't present or files
        are missing, fall back to Unicode glyphs.
        """
        assets_dir = os.path.join(os.path.dirname(__file__), 'assets')
        imgs = {}
        try:
            for sym in ['P','N','B','R','Q','K','p','n','b','r','q','k']:
                # try filename patterns: wp.png, wn.png, ... and uppercase/lowercase
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
                    # skip if Pillow missing or image invalid
                    imgs = {}
                    break
        except Exception:
            imgs = {}

        if imgs:
            self.piece_images = imgs
        else:
            self.piece_images = None

    def toggle_engine(self):
        """Enable or disable using the external engine."""
        if not self.engine_enabled:
            path = self.engine_path_var.get()
            if not path:
                messagebox.showerror('Engine', 'No engine path provided')
                return
            try:
                # try to start engine
                self.engine = chess.engine.SimpleEngine.popen_uci(path)
                self.engine_enabled = True
                self.engine_toggle.configure(text='Use Engine: On')
            except Exception as e:
                messagebox.showerror('Engine', f'Failed to start engine: {e}')
                self.engine = None
                self.engine_enabled = False
        else:
            # disable
            try:
                if self.engine:
                    try:
                        self.engine.quit()
                    except Exception:
                        pass
            finally:
                self.engine = None
                self.engine_enabled = False
                self.engine_toggle.configure(text='Use Engine: Off')

    def on_close(self):
        try:
            if self.engine:
                try:
                    self.engine.quit()
                except Exception:
                    pass
        finally:
            try:
                self.master.destroy()
            except Exception:
                pass

    def ask_promotion(self, color: int) -> 'Optional[int]':
        """Show a small dialog asking the player which piece to promote to.

        Returns the chess piece type constant (chess.QUEEN, chess.ROOK, ...)
        or None if the user cancels.
        """
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

        # order: Queen, Rook, Bishop, Knight
        # if piece images available, use them on the buttons
        use_imgs = bool(self.piece_images)

        # store promo images on self to keep references while dialog is open
        self._promo_imgs = []

        def make_button(pt, row, colpos):
            if use_imgs:
                # map piece type to symbol key
                key = {chess.QUEEN: 'Q', chess.ROOK: 'R', chess.BISHOP: 'B', chess.KNIGHT: 'N'}[pt]
                if color == chess.BLACK:
                    key = key.lower()
                img = self.piece_images.get(key) if self.piece_images else None
                if img:
                    b = tk.Button(frame, image=img, width=48, height=48, command=lambda: choose(pt))
                    self._promo_imgs.append(img)
                else:
                    b = tk.Button(frame, text={chess.QUEEN: 'Queen', chess.ROOK: 'Rook', chess.BISHOP: 'Bishop', chess.KNIGHT: 'Knight'}[pt], width=8, command=lambda: choose(pt))
            else:
                b = tk.Button(frame, text={chess.QUEEN: 'Queen', chess.ROOK: 'Rook', chess.BISHOP: 'Bishop', chess.KNIGHT: 'Knight'}[pt], width=8, command=lambda: choose(pt))
            b.grid(row=row, column=colpos, padx=4, pady=2)

        make_button(chess.QUEEN, 0, 0)
        make_button(chess.ROOK, 0, 1)
        make_button(chess.BISHOP, 1, 0)
        make_button(chess.KNIGHT, 1, 1)

        # center dialog over parent
        self.master.update_idletasks()
        dlg.update_idletasks()
        x = self.master.winfo_rootx() + (self.master.winfo_width() - dlg.winfo_width()) // 2
        y = self.master.winfo_rooty() + (self.master.winfo_height() - dlg.winfo_height()) // 2
        try:
            dlg.geometry(f'+{x}+{y}')
        except Exception:
            pass

        dlg.wait_window()
        # clear references after dialog closed
        try:
            self._promo_imgs = []
        except Exception:
            pass
        return sel['choice']

    def show_legal_moves(self, square: int):
        """Highlight legal destination squares for the selected square.

        Capture squares are highlighted differently.
        """
        # clear previous highlights first
        self.clear_highlights()
        for mv in self.board.legal_moves:
            if mv.from_square == square:
                to_sq = mv.to_square
                btn = self.buttons.get(to_sq)
                if not btn:
                    continue
                # capture or quiet
                if self.board.is_capture(mv):
                    btn.configure(bg='#FF8888')
                else:
                    btn.configure(bg='#88FFDD')

    def clear_highlights(self):
        """Restore board square colors to normal (but keep selected highlight if any)."""
        for sq, btn in self.buttons.items():
            r = 7 - chess.square_rank(sq)
            c = chess.square_file(sq)
            color = LIGHT_COLOR if (r + c) % 2 == 0 else DARK_COLOR
            btn.configure(bg=color)
        if self.selected is not None:
            # re-highlight selection
            try:
                self.buttons[self.selected].configure(bg='#AAFF88')
            except Exception:
                pass

    def undo_move(self):
        """Undo the last move if possible."""
        try:
            if len(self.board.move_stack) > 0:
                self.board.pop()
                self.clear_highlights()
                self.selected = None
                self.update_board()
        except Exception:
            pass

    def save_pgn(self):
        # build PGN from current game
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
        path = shutil.which('stockfish')
        if path:
            self.engine_path_var.set(path)
            messagebox.showinfo('Detected', f'Found stockfish at {path}')
        else:
            messagebox.showinfo('Not found', 'Stockfish not found in PATH. Please install and/or provide path.')

    def download_engine(self):
        """Download a Stockfish binary from GitHub releases and extract to engines/stockfish(.exe).

        Strategy: query GitHub releases for the official-stockfish/Stockfish repo, pick a Windows asset if available.
        """
        repo_api = 'https://api.github.com/repos/official-stockfish/Stockfish/releases/latest'
        headers = {'Accept': 'application/vnd.github.v3+json'}
        token = self.github_token.get().strip() if getattr(self, 'github_token', None) else ''
        if token:
            headers['Authorization'] = f'token {token}'

        try:
            req = urllib.request.Request(repo_api, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.load(resp)
        except Exception as e:
            messagebox.showerror('Download failed', f'Could not query GitHub API: {e}')
            return

        assets = data.get('assets', []) if isinstance(data, dict) else []
        if not assets:
            messagebox.showerror('Download failed', 'No release assets found for Stockfish.')
            return

        # determine platform preference
        prefer = self.platform_var.get() if getattr(self, 'platform_var', None) else 'auto'
        sysplat = platform.system().lower()
        if prefer == 'auto':
            if sysplat.startswith('win'):
                prefer = 'windows'
            elif sysplat.startswith('darwin'):
                prefer = 'macos'
            else:
                prefer = 'linux'

        candidate = None
        candidate_name = None
        # heuristics: look for asset names containing platform keywords and zip executables
        for a in assets:
            name = a.get('name', '').lower()
            url = a.get('browser_download_url')
            if not url:
                continue
            if prefer == 'windows' and ('win' in name or 'windows' in name) and name.endswith('.zip'):
                candidate = url
                candidate_name = name
                break
            if prefer == 'macos' and ('mac' in name or 'osx' in name or 'macos' in name) and name.endswith('.zip'):
                candidate = url
                candidate_name = name
                break
            if prefer == 'linux' and ('linux' in name) and name.endswith('.zip'):
                candidate = url
                candidate_name = name
                break

        # fallback: any zip
        if not candidate:
            for a in assets:
                name = a.get('name', '').lower()
                url = a.get('browser_download_url')
                if name.endswith('.zip'):
                    candidate = url
                    candidate_name = name
                    break

        if not candidate:
            messagebox.showerror('Download failed', 'No downloadable zip asset found for the latest Stockfish release.')
            return

        proceed = messagebox.askyesno('Download Stockfish', f'Download Stockfish asset:\n{candidate_name}\n\nProceed?')
        if not proceed:
            return

        engines_dir = os.path.join(os.path.dirname(__file__), 'engines')
        os.makedirs(engines_dir, exist_ok=True)

        try:
            tmpf = tempfile.NamedTemporaryFile(delete=False)
            tmp_path = tmpf.name
            tmpf.close()
            # download with headers (token if provided)
            req = urllib.request.Request(candidate, headers=headers)
            with urllib.request.urlopen(req, timeout=60) as resp, open(tmp_path, 'wb') as out:
                shutil.copyfileobj(resp, out)

            # extract zip and find engine executable
            with zipfile.ZipFile(tmp_path, 'r') as z:
                z.extractall(engines_dir)

            os.unlink(tmp_path)

            # search for stockfish executable in extracted files
            exe_name = 'stockfish'
            if platform.system().lower().startswith('windows'):
                exe_name = 'stockfish.exe'

            found = None
            for root, dirs, files in os.walk(engines_dir):
                for f in files:
                    if f.lower().startswith('stockfish') and (f.lower() == exe_name or f.lower().endswith('.exe') or 'stockfish' in f.lower()):
                        candidate_path = os.path.join(root, f)
                        dest = os.path.join(engines_dir, exe_name)
                        try:
                            shutil.copyfile(candidate_path, dest)
                            found = dest
                            break
                        except Exception:
                            continue
                if found:
                    break

            if not found:
                messagebox.showerror('Download failed', f'Downloaded and extracted, but no Stockfish executable found in {engines_dir}.')
                return

            # make sure executable bit set (POSIX)
            try:
                os.chmod(found, 0o755)
            except Exception:
                pass

            self.engine_path_var.set(found)
            messagebox.showinfo('Downloaded', f'Stockfish downloaded to {found}. You can now click Use Engine.')
        except Exception as e:
            messagebox.showerror('Download failed', f'Failed to download or extract Stockfish: {e}')
            return

    def verify_engine(self):
        """Launch the engine binary and request a short move to verify it responds.

        Shows result via messagebox.
        """
        path = self.engine_path_var.get()
        if not path:
            messagebox.showerror('Verify failed', 'No engine path provided')
            return
        if not os.path.exists(path) and shutil.which(path) is None:
            messagebox.showerror('Verify failed', 'Engine executable not found')
            return

        retries = max(1, int(self.verify_retries.get())) if hasattr(self, 'verify_retries') else 2
        timeout = float(self.verify_timeout.get()) if hasattr(self, 'verify_timeout') else 0.05

        last_err = None
        tried_download = False
        base_backoff = 0.5
        for attempt in range(1, retries + 1):
            try:
                eng = chess.engine.SimpleEngine.popen_uci(path)
                b = chess.Board()
                res = eng.play(b, chess.engine.Limit(time=timeout))
                try:
                    eng.quit()
                except Exception:
                    pass
                if res is None or not hasattr(res, 'move') or res.move is None:
                    last_err = 'Engine started but did not return a move'
                else:
                    info = self._probe_engine_identity(path)
                    msg = f'Engine responded with move: {res.move} (attempt {attempt}/{retries})'
                    if info:
                        msg += f' — {info}'
                    messagebox.showinfo('Verify OK', msg)
                    if hasattr(self, 'verify_log'):
                        self.verify_log.insert(tk.END, f'OK: {msg}')
                    return
            except Exception as e:
                last_err = str(e)
                if hasattr(self, 'verify_log'):
                    self.verify_log.insert(tk.END, f'Attempt {attempt}: error: {e}')

            # If enabled, attempt to auto-download once (before exhausting all retries)
            if self.auto_download_var.get() and not tried_download:
                tried_download = True
                try:
                    self.download_engine()
                    # if download_engine set path, update local variable
                    path = self.engine_path_var.get() or path
                    # if no path after download, continue retry loop
                except Exception as e:
                    last_err = f'Auto-download failed: {e}'

            # compute backoff wait
            if attempt < retries:
                strategy = getattr(self, 'backoff_var', None) and self.backoff_var.get() or 'linear'
                max_wait = getattr(self, 'backoff_max', None) and float(self.backoff_max.get()) or 5.0
                if strategy == 'constant':
                    wait = min(max_wait, base_backoff)
                elif strategy == 'exponential':
                    wait = min(max_wait, base_backoff * (2 ** (attempt - 1)))
                else:  # linear
                    wait = min(max_wait, base_backoff * attempt)
                time.sleep(wait)

        messagebox.showerror('Verify failed', f'Engine verification failed after {retries} attempts: {last_err}')

    def _probe_engine_identity(self, path: str) -> str:
        """Run the engine with a short UCI handshake to extract id name/author.

        Returns a short string like 'name (author)'."""
        try:
            proc = subprocess.Popen([path], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            out, err = proc.communicate('uci\nquit\n', timeout=5)
            name = None
            author = None
            for line in out.splitlines():
                line = line.strip()
                if line.lower().startswith('id name'):
                    name = line[7:].strip()
                elif line.lower().startswith('id author'):
                    author = line[9:].strip()
            parts = []
            if name:
                parts.append(name)
            if author:
                parts.append(f'by {author}')
            return ' '.join(parts)
        except Exception:
            return ''


def main():
    root = tk.Tk()
    app = ChessGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()
