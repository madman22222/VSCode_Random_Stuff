"""Validated, atomic storage for the actual unfinished game, never practice/review."""
import math
from pathlib import Path
import json
import chess
from learning_keys import position_key
from training_ai import atomic_json


class SessionStore:
    def __init__(self, path):
        self.path = Path(path)

    def save(self, board, mode, side, clock, log, flipped=False):
        if board.is_game_over(claim_draw=True):
            self.clear()
            return
        atomic_json(self.path, {'version': 1, 'root_fen': board.root().fen(),
            'moves': [m.uci() for m in board.move_stack], 'final_fen': board.fen(),
            'mode': mode, 'side': side, 'clock': clock, 'log': log, 'flipped': bool(flipped)})

    def load(self):
        if not self.path.exists():
            return None
        data = json.loads(self.path.read_text(encoding='utf-8'))
        if not isinstance(data, dict) or data.get('version') != 1:
            raise ValueError('Unsupported saved-game format')
        board = chess.Board(data['root_fen'])
        if not board.is_valid() or not isinstance(data['moves'], list) or len(data['moves']) > 10000:
            raise ValueError('Invalid saved game')
        valid_log = set()
        for uci in data['moves']:
            move = chess.Move.from_uci(uci)
            if move not in board.legal_moves:
                raise ValueError('Saved game contains an illegal move')
            valid_log.add((board.board_fen(), uci, board.turn))
            valid_log.add((position_key(board), uci, board.turn))
            board.push(move)
        if board.fen() != data['final_fen']:
            raise ValueError('Saved position does not match move history')
        if data['mode'] not in ('player_vs_ai', 'player_vs_player', 'ai_vs_ai') or data['side'] not in ('White', 'Black'):
            raise ValueError('Invalid saved game settings')
        clock = data.get('clock', {})
        if not isinstance(clock, dict):
            raise ValueError('Invalid clock data')
        for name in ('white', 'black', 'increment'):
            value = float(clock.get(name, 600 if name != 'increment' else 0))
            if not math.isfinite(value) or value < 0:
                raise ValueError('Invalid clock value')
            clock[name] = value
        log = [tuple(item) for item in data.get('log', []) if isinstance(item, list) and len(item) == 3]
        data['log'] = [item for item in log if item in valid_log]
        data['board'] = board
        return data

    def clear(self):
        self.path.unlink(missing_ok=True)
