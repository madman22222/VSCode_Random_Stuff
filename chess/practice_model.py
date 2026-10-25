"""Author-validated multi-move practice, independent of game/learning state."""
from dataclasses import dataclass
import chess


@dataclass(frozen=True)
class SequencePuzzle:
    id: str
    title: str
    fen: str
    hints: tuple
    lines: tuple
    explanation: str
    goal: str = 'line'


class PuzzleSession:
    def __init__(self, puzzle, variant=0):
        self.puzzle = puzzle
        self.board = chess.Board(puzzle.fen)
        self.solver = self.board.turn
        self.prefix = ()
        self.variant = variant
        self.done = False

    def attempt(self, move):
        if self.done or self.board.turn != self.solver or move not in self.board.legal_moves:
            return {'accepted': False, 'message': 'Choose a legal move for the side being practiced.'}
        proposed = self.prefix + (move.uci(),)
        after = self.board.copy()
        after.push(move)
        # A different immediate mate is still a valid solution to a mating goal.
        direct_mate = self.puzzle.goal == 'mate' and after.is_checkmate()
        matching = [line for line in self.puzzle.lines if line[:len(proposed)] == proposed]
        if not matching and not direct_mate:
            from study_coach import explain_attempt
            return {'accepted': False, 'message': explain_attempt(self.board, move, self.puzzle.explanation)}
        self.board.push(move)
        self.prefix = proposed
        self.done = direct_mate or any(len(line) == len(proposed) for line in matching)
        reply_san = None
        if not self.done:
            replies = list(dict.fromkeys(line[len(proposed)] for line in matching))
            reply = chess.Move.from_uci(replies[self.variant % len(replies)])
            reply_san = self.board.san(reply)
            self.board.push(reply)
            self.prefix += (reply.uci(),)
        return {'accepted': True, 'completed': self.done, 'reply': reply_san,
                'message': ('Solved. ' if self.done else 'Correct. Continue the calculation. ') + self.puzzle.explanation}


def validate_lines(board, lines, goal):
    if not isinstance(lines, list) or not 1 <= len(lines) <= 32:
        raise ValueError('Supply 1–32 solution lines')
    result = []
    for line in lines:
        if not isinstance(line, list) or not 1 <= len(line) <= 15 or len(line) % 2 != 1:
            raise ValueError('Each line must contain 1–15 half-moves and finish with the solver')
        copy = board.copy()
        for uci in line:
            if not isinstance(uci, str):
                raise ValueError('Solution moves must be UCI strings')
            move = chess.Move.from_uci(uci)
            if move not in copy.legal_moves or copy.is_game_over(claim_draw=True):
                raise ValueError('Solution contains an illegal move or continues a finished game')
            copy.push(move)
        if goal == 'mate' and not copy.is_checkmate():
            raise ValueError('A mate solution must end in checkmate')
        if goal == 'promotion' and not chess.Move.from_uci(line[-1]).promotion:
            raise ValueError('A promotion solution must finish by promoting')
        result.append(tuple(line))
    if len(set(result)) != len(result):
        raise ValueError('Duplicate solution line')
    # A completed line cannot also require more moves in another line.
    for line in result:
        if any(len(other) > len(line) and other[:len(line)] == line for other in result):
            raise ValueError('A solution line cannot be a prefix of another')
    return tuple(result)
