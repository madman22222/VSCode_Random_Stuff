"""TrainingAI module extracted from game_controller.
Provides the headless TrainingAI class for self-play learning batches.
"""
from __future__ import annotations

import chess  # type: ignore
import threading
import time
import random
import sys
from typing import Optional

from simple_ai import SimpleAI
try:
    from logger import info, debug, warn, error
except Exception:
    def info(*a, **k): pass
    def debug(*a, **k): pass
    def warn(*a, **k): pass
    def error(*a, **k): pass

class TrainingAI:
    """Headless high-speed AI vs AI training mode."""
    def __init__(self, ai_instance: SimpleAI, depth: int = 3, batch_size: int = 100, export_interval: int | None = None, move_time_limit: float = 0.25):
        self.ai = ai_instance
        self.depth = depth
        self.running = False
        self.games_played = 0
        self.results = {'white': 0, 'black': 0, 'draw': 0}
        self.thread: Optional[threading.Thread] = None
        self.batch_size = max(1, int(batch_size))
        self.export_interval = export_interval
        self._batches_done = 0
        self.move_time_limit = max(0.05, float(move_time_limit))
        self.current_move_count = 0
        self._last_move_print = 0.0
    def start(self):
        if self.running: return
        self.running = True
        try:
            self.ai.defer_persistence = True
            self.ai.persist_every_n = self.batch_size
            self.ai.export_readable_during_training = False if self.export_interval is None else True
            self.ai._pending_games = 0
        except Exception: pass
        self.thread = threading.Thread(target=self._training_loop, daemon=True)
        self.thread.start()
        info("==== TRAINING START ====")
        try:
            enc = getattr(sys.stdout, 'encoding', '') or ''
            if 'UTF' not in enc.upper():
                pass
        except Exception:
            pass
        info(f"Depth={self.depth} learning={self.ai.use_learning}")
        try:
            self.current_move_count = 0; self._last_move_print = 0.0
        except Exception: pass
    def stop(self):
        if not self.running: return
        self.running = False
        if self.thread: self.thread.join(timeout=2.0)
        try:
            self.ai._save_learning_db()
            try: self.ai.export_readable_learning()
            except Exception: pass
            self.ai.defer_persistence = False
            self.ai.export_readable_during_training = False
        except Exception: pass
        info("==== TRAINING STOP ====")
        info(f"Games={self.games_played} W={self.results['white']} B={self.results['black']} D={self.results['draw']}")
        if self.games_played > 0:
            white_pct = (self.results['white']/self.games_played)*100
            black_pct = (self.results['black']/self.games_played)*100
            draw_pct = (self.results['draw']/self.games_played)*100
            info(f"WinRates W={white_pct:.1f}% B={black_pct:.1f}% D={draw_pct:.1f}%")
        try: self.current_move_count = 0
        except Exception: pass
    def _training_loop(self):
        while self.running:
            try:
                debug(f"Game {self.games_played + 1} start")
                board = chess.Board(); self.ai.game_log = []
                move_count = 0; self.current_move_count = 0; max_moves = 300
                while not board.is_game_over() and move_count < max_moves and self.running:
                    move = self.ai.choose_move_iterative(board, time_limit=self.move_time_limit)
                    if move is None:
                        legal = list(board.legal_moves)
                        if not legal: break
                        move = random.choice(legal)
                    board.push(move); move_count += 1; self.current_move_count = move_count
                    try:
                        now = time.time()
                        if (move_count % 10 == 0) or (now - self._last_move_print >= 1.0):
                            debug(f"Moves={move_count}"); self._last_move_print = now
                    except Exception: pass
                if not self.running: break
                self.games_played += 1
                if board.is_checkmate():
                    winner = 'black' if board.turn == chess.WHITE else 'white'; result_text = f"{'White' if winner=='white' else 'Black'} wins by checkmate"
                elif board.is_stalemate(): winner = 'draw'; result_text = "Draw by stalemate"
                elif board.is_insufficient_material(): winner = 'draw'; result_text = "Draw by insufficient material"
                elif move_count >= max_moves: winner = 'draw'; result_text = "Draw by move limit"
                else: winner = 'draw'; result_text = "Draw"
                self.results[winner] += 1
                self.ai.finalize_game(winner)
                info(f"Game {self.games_played} {result_text} moves={move_count}")
                if self.export_interval is not None and self.ai._pending_games == 0:
                    self._batches_done += 1
                    if (self._batches_done % max(1, self.export_interval)) == 0:
                        try:
                            self.ai.export_readable_learning(); debug("Readable snapshot exported")
                        except Exception: pass
                if self.games_played % 10 == 0:
                    info(f"Stats {self.games_played}: W={self.results['white']} ({(self.results['white']/self.games_played)*100:.1f}%) B={self.results['black']} ({(self.results['black']/self.games_played)*100:.1f}%) D={self.results['draw']} ({(self.results['draw']/self.games_played)*100:.1f}%)")
            except Exception as e:
                warn(f"Training loop error: {e}"); time.sleep(0.1)
