"""Versioned evaluation roots independent of the training opening catalogue."""
import hashlib
import json
import chess
from app_paths import resource_dir
from learning_keys import position_key


def load_corpus(ai=None):
    raw = (resource_dir() / 'assets/evaluation/independent-v1.json').read_bytes()
    data = json.loads(raw)
    positions = data['positions']
    keys = []
    ids = set()
    for item in positions:
        board = chess.Board(item['fen'])
        if item['id'] in ids or not board.is_valid() or board.is_game_over(claim_draw=True):
            raise ValueError('Invalid evaluation position')
        ids.add(item['id'])
        keys.append(position_key(board))
    if len(set(keys)) != len(keys):
        raise ValueError('Duplicate evaluation root')
    remembered = {key.rsplit('|', 1)[0] for key in ai.learning_db} if ai else set()
    return positions, {'id': data['id'], 'version': data['version'],
                       'sha256': hashlib.sha256(raw).hexdigest(), 'position_count': len(positions),
                       'remembered_roots': sum(key in remembered for key in keys),
                       'selection': 'seeded random pairs with replacement; same root for both colors',
                       'scope': 'Internal comparison, not an Elo estimate or proof of general strength.'}
