"""Search draw checks equivalent to python-chess, with cheap impossibility guards."""
import chess


def search_outcome(board):
    outcome = board.outcome(claim_draw=False)
    if outcome is not None:
        return outcome
    if board.halfmove_clock >= 99 and board.can_claim_fifty_moves():
        return chess.Outcome(chess.Termination.FIFTY_MOVES, None)
    # A repeated standard-chess position needs at least four half-moves per cycle.
    # A prospective third occurrence needs at least seven reversible half-moves.
    if board.halfmove_clock >= 7 and len(board.move_stack) >= 7 and board.can_claim_threefold_repetition():
        return chess.Outcome(chess.Termination.THREEFOLD_REPETITION, None)
    return None
