"""Bounded local game library, opening repertoires and progress summaries."""
import calendar
import copy
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import time
import uuid
import chess
import chess.pgn
from data_validation import read_json
from training_ai import atomic_json
from learning_storage import writer_lease

MAX_STUDY_BYTES = 16 * 1024 * 1024


def validate_study(data):
    if not isinstance(data, dict) or data.get('version') != 1:
        raise ValueError('Unsupported study library format')
    for key, limit in (('games', 1000), ('repertoires', 200)):
        rows = data.get(key, [])
        if not isinstance(rows, list) or len(rows) > limit:
            raise ValueError('Invalid study collection')
        ids = set()
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get('id'), str) or row['id'] in ids:
                raise ValueError('Invalid/duplicate study ID')
            ids.add(row['id'])
            for name in ('title', 'notes', 'pgn', 'tags'):
                if name in row and (not isinstance(row[name], str) or len(row[name]) > (500000 if name == 'pgn' else 5000)):
                    raise ValueError('Study text exceeds its limit')
            if key == 'games':
                parse_game(row.get('pgn', ''))
            else:
                validate_repertoire(row)
    return data


def parse_game(text):
    if not isinstance(text, str) or not text.strip() or len(text) > 500000:
        raise ValueError('Supply a PGN of at most 500,000 characters')
    game = chess.pgn.read_game(io.StringIO(text))
    if game is None or game.errors:
        raise ValueError('PGN contains an invalid game')
    board = game.board()
    if not board.is_valid():
        raise ValueError('Invalid PGN start position')
    for move in game.mainline_moves():
        if move not in board.legal_moves:
            raise ValueError('Illegal PGN continuation')
        board.push(move)
    return game


def validate_repertoire(row):
    fen = row.get('fen', chess.STARTING_FEN)
    board = chess.Board(fen)
    if not board.is_valid():
        raise ValueError('Invalid repertoire position')
    lines = row.get('lines')
    if not isinstance(lines, list) or not 1 <= len(lines) <= 100:
        raise ValueError('Use 1–100 repertoire lines')
    for line in lines:
        if not isinstance(line, list) or not 1 <= len(line) <= 100:
            raise ValueError('Each line needs 1–100 UCI half-moves')
        probe = board.copy()
        for uci in line:
            if not isinstance(uci, str):
                raise ValueError('Invalid repertoire move')
            move = chess.Move.from_uci(uci)
            if move not in probe.legal_moves or probe.is_game_over(claim_draw=True):
                raise ValueError('Illegal repertoire continuation')
            probe.push(move)
    if row.get('side', 'white') not in ('white', 'black'):
        raise ValueError('Choose White or Black')
    return row


class StudyStore:
    def __init__(self, root):
        self.path = Path(root) / 'study.json'

    def load(self):
        return validate_study(read_json(self.path)) if self.path.exists() else {'version': 1, 'games': [], 'repertoires': []}

    def save(self, data):
        validate_study(data)
        if len(json.dumps(data).encode()) > MAX_STUDY_BYTES:
            raise ValueError('Study library exceeds 16 MiB; export and remove older entries')
        atomic_json(self.path, data)

    def _transaction(self, work):
        with writer_lease(self.path.parent / '.profile'):
            data = self.load()
            result = work(data)
            self.save(data)
            return result

    def add_game(self, pgn, title='', notes='', tags=''):
        game = parse_game(pgn)
        row = {'id': uuid.uuid4().hex, 'title': title or game.headers.get('Event', 'Saved game'),
               'pgn': str(game), 'notes': notes, 'tags': tags}
        return self._transaction(lambda data: (data['games'].append(row), row)[1])

    def edit_game(self, id, notes, tags):
        def update(data):
            row = next(row for row in data['games'] if row['id'] == id)
            row.update(notes=notes, tags=tags)
        self._transaction(update)

    def delete(self, collection, id):
        if collection not in ('games', 'repertoires'):
            raise ValueError('Unknown collection')
        self._transaction(lambda data: data.update({collection: [row for row in data[collection] if row['id'] != id]}))

    def search(self, query=''):
        query = query.casefold().strip()
        found = []
        for row in self.load()['games']:
            game = parse_game(row['pgn'])
            text = ' '.join([row['title'], row['notes'], row['tags']] + list(game.headers.values())).casefold()
            if query in text:
                found.append((row, game))
        return found

    def add_repertoire(self, title, text, side='white'):
        # Accept normal PGN, including side variations. Each leaf becomes a line.
        game = parse_game(text)
        lines = []
        def visit(node, prefix):
            if not node.variations:
                if prefix: lines.append(prefix)
                return
            for child in node.variations:
                visit(child, prefix + [child.move.uci()])
                if len(lines) > 100:
                    raise ValueError('Too many repertoire branches')
        visit(game, [])
        row = {'id': uuid.uuid4().hex, 'title': title, 'fen': game.board().fen(), 'side': side,
               'lines': lines, 'notes': '', 'tags': ''}
        validate_repertoire(row)
        return self._transaction(lambda data: (data['repertoires'].append(row), row)[1])


class VariationSession:
    def __init__(self, board, continuation=()):
        self.root = board.copy()
        self.board = board.copy()
        self.base = len(board.move_stack)
        probe = board.copy()
        self.line = []
        for san in continuation:
            move = probe.parse_san(san)
            self.line.append(move); probe.push(move)

    def push(self, text):
        try:
            move = self.board.parse_san(text)
        except ValueError:
            move = chess.Move.from_uci(text)
        if move not in self.board.legal_moves:
            raise ValueError('Choose a legal continuation')
        self.board.push(move)

    def next(self):
        offset = len(self.board.move_stack) - self.base
        if self.board.move_stack[self.base:] != self.line[:offset]:
            raise ValueError('Reset to follow the suggested line')
        if offset < len(self.line):
            self.board.push(self.line[offset])

    def back(self):
        if len(self.board.move_stack) > self.base:
            self.board.pop()

    def reset(self):
        self.board = self.root.copy()


class RepertoireSession:
    def __init__(self, row, variant=0):
        validate_repertoire(row)
        self.row = row
        self.board = chess.Board(row['fen'])
        self.side = row.get('side', 'white') == 'white'
        self.prefix = []
        self.variant = variant
        self.done = False
        self._reply()

    def _reply(self):
        matching = [line for line in self.row['lines'] if line[:len(self.prefix)] == self.prefix]
        if any(len(line) == len(self.prefix) for line in matching):
            self.done = True; return
        if self.board.turn != self.side:
            choices = list(dict.fromkeys(line[len(self.prefix)] for line in matching))
            move = choices[self.variant % len(choices)]
            self.board.push_uci(move); self.prefix.append(move)
            self._reply()

    def attempt(self, uci):
        move = chess.Move.from_uci(uci)
        proposed = self.prefix + [uci]
        if self.done or move not in self.board.legal_moves:
            raise ValueError('Choose a legal repertoire move')
        if not any(line[:len(proposed)] == proposed for line in self.row['lines']):
            return False
        self.board.push(move); self.prefix = proposed; self._reply()
        return True


def learning_dashboard(config, now=None):
    from curriculum import LESSONS
    now = time.time() if now is None else now
    stats = config.get('practice_stats', {})
    solved = set(config.get('practice_solved', []))
    rows = []
    for id, title, description, ids in LESSONS:
        items = [stats.get(key, {}) for key in ids]
        rows.append({'id': id, 'title': title, 'completed': len(solved & set(ids)), 'total': len(ids),
                     'successes': sum(x.get('successes', 0) for x in items),
                     'mistakes': sum(x.get('mistakes', 0) for x in items),
                     'due': sum(bool(x) and x.get('due', 0) <= now for x in items)})
    return rows


def review_calendar(stats):
    days = {}
    for id, item in stats.items():
        stamp = item.get('due', 0)
        day = datetime.fromtimestamp(stamp, timezone.utc).strftime('%Y-%m-%d')
        days.setdefault(day, []).append(id)
    return sorted(days.items())


def plan_session(puzzles, stats, solved=(), minutes=10, now=None):
    from adaptive_practice import recommend
    remaining = list(puzzles); chosen = []
    for _ in range(max(1, min(15, int(minutes) // 2))):
        puzzle, reason = recommend(remaining, stats, solved, now)
        if puzzle is None: break
        chosen.append(puzzle.id)
        remaining = [row for row in remaining if row.id != puzzle.id]
    return chosen


def training_health(records, progress=None):
    positions = {}
    sides = {'white': 0, 'black': 0, 'legacy/unknown': 0}
    low = 0
    for key, value in records.items():
        position = key.rsplit('|', 1)[0]
        total = sum(value.get(k, 0) for k in ('w', 'l', 'd'))
        positions[position] = positions.get(position, 0) + total
        low += total < 5
        tokens = position.split()
        side = ('white' if tokens[1] == 'w' else 'black') if len(tokens) >= 4 and tokens[1] in ('w', 'b') else 'legacy/unknown'
        sides[side] += total
    progress = progress or {}
    games = sum(progress.get('results', {}).values())
    cutoffs = progress.get('move_limit_draws', 0)
    total = sum(positions.values())
    return {'records': len(records), 'positions': len(positions), 'records_below_five_samples': low,
            'outcome_samples_by_side': sides, 'largest_position_share_percent': round(100 * max(positions.values(), default=0) / total, 2) if total else 0,
            'saved_games': games, 'move_limit_draws': cutoffs,
            'cutoff_draw_percent': round(100 * cutoffs / games, 1) if games else None,
            'scope': 'Coverage/quality indicators, not evidence of playing strength.'}
