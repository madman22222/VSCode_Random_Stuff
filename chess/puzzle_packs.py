"""Validated local puzzle packs with explicit legal solution moves and attribution."""
from dataclasses import dataclass
import re
import chess
from data_validation import read_json, validated_fen


@dataclass(frozen=True)
class PackPuzzle:
    id: str
    title: str
    fen: str
    hints: tuple
    solutions: tuple
    goal: str = 'solution'

    def accepts(self, board, move):
        return move in board.legal_moves and move.uci() in self.solutions


def load_pack(path):
    pack = read_json(path)
    if not isinstance(pack, dict) or type(pack.get('version')) is not int or pack.get('version') not in (1, 2):
        raise ValueError('Unsupported puzzle pack version')
    if not isinstance(pack.get('author'), str) or not pack['author'].strip():
        raise ValueError('Puzzle packs must include author/attribution')
    pack_id = pack.get('id', '')
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,40}', pack_id):
        raise ValueError('Invalid pack ID')
    rows = pack.get('puzzles')
    if not isinstance(rows, list) or not 1 <= len(rows) <= 200:
        raise ValueError('Pack must contain 1–200 puzzles')
    result, ids = [], set()
    for item in rows:
        if not isinstance(item, dict) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,40}', str(item.get('id', ''))):
            raise ValueError('Invalid puzzle ID')
        if item['id'] in ids:
            raise ValueError('Duplicate puzzle ID')
        ids.add(item['id'])
        board = validated_fen(item['fen'])
        title, hints, solutions = item.get('title'), item.get('hints'), item.get('solutions')
        if not isinstance(title, str) or not 1 <= len(title) <= 100:
            raise ValueError('Invalid puzzle title')
        if not isinstance(hints, list) or not 1 <= len(hints) <= 5 or any(not isinstance(h, str) or not 1 <= len(h) <= 500 for h in hints):
            raise ValueError('Supply 1–5 short hints')
        if pack['version'] == 1:
            if not isinstance(solutions, list) or not 1 <= len(solutions) <= 64 or any(not isinstance(m, str) or chess.Move.from_uci(m) not in board.legal_moves for m in solutions):
                raise ValueError('All solutions must be legal UCI moves')
        theme, difficulty = item.get('theme', 'Study'), item.get('difficulty', 'Unrated')
        if not isinstance(theme, str) or not isinstance(difficulty, str) or len(theme) > 40 or len(difficulty) > 40:
            raise ValueError('Invalid theme/difficulty')
        if pack['version'] == 2:
            from practice_model import SequencePuzzle, validate_lines
            goal = item.get('goal', 'line')
            if goal not in ('line', 'mate', 'promotion'):
                raise ValueError('Unsupported multi-move goal')
            explanation = item.get('explanation')
            if not isinstance(explanation, str) or not 1 <= len(explanation) <= 1000:
                raise ValueError('Supply a short lesson explanation')
            lines = validate_lines(board, item.get('lines'), goal)
            result.append(SequencePuzzle(f'{pack_id}:{item["id"]}', f'{theme} / {difficulty}: {title}',
                                         board.fen(), tuple(hints), lines, explanation, goal))
            continue
        result.append(PackPuzzle(f'{pack_id}:{item["id"]}', f'{theme} / {difficulty}: {title}',
                                 board.fen(), tuple(hints), tuple(solutions)))
    return result
