"""Game conclusions that are independent of the board's checkmate state."""
from dataclasses import dataclass
from enum import Enum
from typing import Optional
from tkinter import messagebox
import chess
import chess.pgn


class EndReason(Enum):
    TIME_FORFEIT = 'time forfeit'
    RESIGNATION = 'resignation'
    DRAW_AGREEMENT = 'draw agreement'
    IMPORTED_RESULT = 'imported result'


@dataclass(frozen=True)
class Conclusion:
    termination: EndReason
    winner: Optional[bool]

    def result(self):
        return '1/2-1/2' if self.winner is None else ('1-0' if self.winner else '0-1')


def timeout_conclusion(board, flagged_color):
    # Material detection is conservative; this is not a general dead-position solver.
    existing = board.outcome(claim_draw=True)
    if existing:
        return existing
    winner = not flagged_color
    return Conclusion(EndReason.TIME_FORFEIT,
                      None if board.has_insufficient_material(winner) else winner)


class GameEndings:
    def _game_outcome(self):
        declared = getattr(self, '_declared_result', None)
        if getattr(self, '_activity', 'game') == 'game' and declared is not None:
            return declared
        # Explicit casual-play policy: automatically accept claimable draws.
        return self.board.outcome(claim_draw=True)

    def _clock_expired(self):
        return bool(self.clock and self.clock_enabled and self.clock.check_timeout())

    def _declare_result(self, conclusion):
        if (self._activity != 'game' or self._game_outcome() is not None
                or getattr(self, '_tools_busy', False)
                or self.training_ai and self.training_ai.running):
            return False
        self._declared_result = conclusion
        self._timed_out = conclusion.termination == EndReason.TIME_FORFEIT
        self._cancel_search()
        self.game_started = False
        if self.clock:
            self.clock.stop()
        self._update_start_pause_button()
        self.update_board(force=True)
        return True

    def resign_game(self):
        if self._activity != 'game' or self._game_outcome() is not None:
            return
        if self.play_mode == 'ai_vs_ai':
            messagebox.showinfo('Resign', 'Resignation is available in Play AI and Two players.')
            return
        color = self._human_color() if self.play_mode == 'player_vs_ai' else self.board.turn
        side = 'White' if color else 'Black'
        if messagebox.askyesno('Resign', f'{side} resigns this game?'):
            self._declare_result(Conclusion(EndReason.RESIGNATION, not color))

    def agree_draw(self):
        if self._activity != 'game' or self._game_outcome() is not None:
            return
        if self.play_mode != 'player_vs_player' or len(self.board.move_stack) < 2:
            messagebox.showinfo('Draw agreement', 'Both local players must have made a move. '
                                'Agreement is available in Two players mode; AI draw offers are not simulated.')
            return
        if messagebox.askyesno('Agree draw', 'Do both local players agree to end this game as a draw?'):
            self._declare_result(Conclusion(EndReason.DRAW_AGREEMENT, None))

    def current_pgn(self):
        game = chess.pgn.Game.from_board(self.board)
        game.headers.update(getattr(self, '_pgn_headers', {}))
        game.setup(self.board.root())
        outcome = self._game_outcome()
        game.headers['Result'] = outcome.result() if outcome else '*'
        if isinstance(outcome, Conclusion):
            game.headers['Termination'] = 'time forfeit' if outcome.termination == EndReason.TIME_FORFEIT else 'normal'
        elif outcome is None:
            game.headers.pop('Termination', None)
        return game
