"""Small, factual explanations for move feedback and optional hints."""
import chess


def illegal_move_message(board, move):
    piece = board.piece_at(move.from_square)
    target = board.piece_at(move.to_square)
    if target and piece and target.color == piece.color:
        return 'That is your piece. Select it to choose a different move.'
    if move in board.pseudo_legal_moves:
        return 'That move would leave your king in check. Protect the king first.'
    if piece and piece.piece_type == chess.KING and abs(move.to_square - move.from_square) == 2:
        return 'Castling needs a clear path, castling rights, and safe king squares.'
    if board.is_check():
        return 'You are in check. Move the king, capture the attacker, or block the check.'
    return 'That piece cannot move there. Highlighted squares show its legal moves.'


def describe_move(board, move):
    san = board.san(move)
    piece = board.piece_at(move.from_square)
    facts = []
    if board.is_castling(move):
        facts.append('castles the king and rook')
    if board.is_capture(move):
        victim = board.piece_at(move.to_square)
        facts.append('captures a ' + (chess.piece_name(victim.piece_type) if victim else 'pawn'))
    if move.promotion:
        facts.append('promotes to a ' + chess.piece_name(move.promotion))
    if board.gives_check(move):
        facts.append('gives check')
    if not facts and piece:
        facts.append(f'moves your {chess.piece_name(piece.piece_type)} to {chess.square_name(move.to_square)}')
    return f'Suggestion: {san} — ' + '; '.join(facts) + '. This is a search suggestion, not a guaranteed best move.'
