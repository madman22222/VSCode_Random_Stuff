"""Version 3 keys include side, castling and legally available en-passant rights."""

def position_key(board):
    return ' '.join(board.fen(en_passant='legal').split()[:4])


def from_fen(fen):
    return ' '.join(fen.split()[:4])
