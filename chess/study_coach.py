"""Factual tactical descriptions; no unsupported best-move or win guarantees."""
import chess


def loose_pieces(board, color):
    """Legal captures of unprotected non-pawn pieces, at this position only."""
    probe = board.copy(stack=False)
    probe.turn = not color
    probe.ep_square = None
    found = set()
    for move in probe.legal_moves:
        victim = probe.piece_at(move.to_square)
        if victim and victim.color == color and victim.piece_type not in (chess.KING, chess.PAWN):
            after = probe.copy(stack=False)
            after.push(move)
            if not after.is_attacked_by(color, move.to_square):
                found.add(f'{chess.piece_name(victim.piece_type)} on {chess.square_name(move.to_square)}')
    return sorted(found)


def move_features(board, move):
    if move not in board.legal_moves:
        return ['Move is not legal in this position.']
    mover = board.turn
    after = board.copy()
    after.push(move)
    features = []
    if after.is_checkmate():
        features.append('This move delivers checkmate.')
    elif after.is_check():
        features.append('The opponent must answer check.')
    pinned = [chess.square_name(s) for s in chess.SQUARES
              if after.piece_at(s) and after.color_at(s) != mover and after.is_pinned(not mover, s)]
    if pinned:
        features.append('Absolute pin on ' + ', '.join(pinned) + '.')
    moving = after.piece_at(move.to_square)
    if moving:
        targets = [chess.piece_name(after.piece_at(s).piece_type) + ' on ' + chess.square_name(s)
                   for s in after.attacks(move.to_square)
                   if after.piece_at(s) and after.color_at(s) != mover
                   and after.piece_type_at(s) != chess.PAWN]
        if len(targets) >= 2:
            features.append('Attacks multiple pieces: ' + ', '.join(targets) + '. Check legal defenses before assuming a gain.')
    loose = loose_pieces(after, mover)
    if loose:
        features.append('Immediate capture to inspect: ' + ', '.join(loose) + '. Exchanges and tactics can change the outcome.')
    return features


def explain_attempt(board, move, goal):
    facts = move_features(board, move)
    return ('Legal, but outside the authored solution. Goal: ' + goal + '\n' +
            (' '.join(facts) if facts else 'Compare forcing checks, captures and the opponent\'s reply.'))
