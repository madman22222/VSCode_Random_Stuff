"""Self-play training with bounded games, clean shutdown and saved learning."""
from __future__ import annotations

import threading
import chess
from simple_ai import SimpleAI
from logger import info, error


class TrainingAI:
    def __init__(self, ai_instance: SimpleAI, depth=3, batch_size=100,
                 export_interval=None, move_time_limit=0.25,
                 max_games=0, max_moves=300):
        self.ai = ai_instance
        self.depth = max(1, int(depth))
        self.batch_size = max(1, int(batch_size))
        self.export_interval = export_interval
        self.move_time_limit = max(0.001, float(move_time_limit))
        self.max_games = max(0, int(max_games))
        self.max_moves = max(1, int(max_moves))
        self.games_played = 0
        self.results = {'white': 0, 'black': 0, 'draw': 0}
        self.current_move_count = 0
        self.running = False
        self.thread = None
        self.last_error = None
        self._stop = threading.Event()

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self._stop.clear()
        self.last_error = None
        self.ai.depth = self.depth
        self.ai.defer_persistence = True
        self.ai.persist_every_n = self.batch_size
        self.ai.export_readable_during_training = False
        self.ai._pending_games = 0
        self.running = True
        self.thread = threading.Thread(target=self._training_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self._stop.set()
        if self.thread and self.thread is not threading.current_thread():
            self.thread.join()
        self.running = False

    def _training_loop(self):
        try:
            while not self._stop.is_set() and (
                    not self.max_games or self.games_played < self.max_games):
                board = chess.Board()
                self.ai.game_log = []
                self.ai.transposition_table.clear()
                self.current_move_count = 0
                while (not board.is_game_over(claim_draw=True)
                       and self.current_move_count < self.max_moves
                       and not self._stop.is_set()):
                    move = self.ai.choose_move_iterative(board, self.move_time_limit)
                    if move is None or move not in board.legal_moves:
                        raise RuntimeError('AI did not return a legal move')
                    board.push(move)
                    self.current_move_count += 1
                if self._stop.is_set():
                    # An interrupted game has no outcome to learn from.
                    self.ai.game_log = []
                    break
                outcome = board.outcome(claim_draw=True)
                winner = 'draw' if outcome is None or outcome.winner is None else (
                    'white' if outcome.winner == chess.WHITE else 'black')
                self.ai.finalize_game(winner)
                self.results[winner] += 1
                self.games_played += 1
                info(f'Game {self.games_played}: {winner}; '
                     f'{self.current_move_count} half-moves; '
                     f'{len(self.ai.learning_db)} learned moves')
                if (self.export_interval and self.games_played %
                        (self.batch_size * self.export_interval) == 0):
                    self.ai.export_readable_learning()
        except Exception as exc:
            self.last_error = exc
            error(f'Training failed: {exc}')
        finally:
            try:
                self.ai._save_learning_db()
                self.ai.export_readable_learning()
            except Exception as exc:
                self.last_error = exc
                error(f'Could not save training: {exc}')
            self.ai.defer_persistence = False
            self.ai.export_readable_during_training = False
            self.running = False
            info(f'Training stopped: {self.games_played} games; {self.results}')
