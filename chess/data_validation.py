"""Bounded, version-aware profile inputs. Validate before mutating live state."""
import gzip
import json
import math
import chess

MAX_JSON_BYTES = 32 * 1024 * 1024
MAX_RECORDS = 100000


def read_json(path):
    opener = gzip.open if str(path).endswith('.gz') else open
    with opener(path, 'rb') as stream:
        data = stream.read(MAX_JSON_BYTES + 1)
    if len(data) > MAX_JSON_BYTES:
        raise ValueError('JSON exceeds the 32 MiB uncompressed limit')
    try:
        return json.loads(data)
    except RecursionError as exc:
        raise ValueError('JSON nesting is excessive') from exc


def learning_records(data):
    if not isinstance(data, dict):
        raise ValueError('Learning data must be an object')
    if 'data' in data or ('meta' in data and 'positions' not in data):
        meta = data.get('meta')
        if not isinstance(meta, dict) or type(meta.get('version')) is not int or meta.get('version') not in (1, 2, 3):
            raise ValueError('Unsupported learning format version')
        data = data.get('data')
    elif 'positions' in data:
        meta = data.get('meta', {'version': 1})
        if not isinstance(meta, dict) or type(meta.get('version')) is not int or meta.get('version') != 1:
            raise ValueError('Unsupported readable learning format version')
        positions = data['positions']
        if not isinstance(positions, dict):
            raise ValueError('Invalid readable learning data')
        converted = {}
        for position, entry in positions.items():
            if not isinstance(entry, dict) or not isinstance(entry.get('moves'), dict):
                raise ValueError('Invalid readable moves')
            for move, counts in entry['moves'].items():
                if not isinstance(counts, dict):
                    raise ValueError('Invalid readable counts')
                converted[position + '|' + move] = {k: counts.get(v, 0) for k, v in
                                                       (('w', 'wins'), ('l', 'losses'), ('d', 'draws'))}
                if len(converted) > MAX_RECORDS:
                    raise ValueError('Too many learning entries')
        data = converted
    if not isinstance(data, dict) or len(data) > MAX_RECORDS:
        raise ValueError('Invalid learning record collection')
    result = {}
    for key, counts in data.items():
        if not isinstance(key, str) or len(key) > 256 or '|' not in key:
            raise ValueError('Invalid position/move key')
        try:
            chess.Move.from_uci(key.rsplit('|', 1)[1])
        except ValueError as exc:
            raise ValueError('Invalid recorded move') from exc
        if not isinstance(counts, dict) or any(type(counts.get(k)) is not int or
                not 0 <= counts[k] <= 10**12 for k in ('w', 'l', 'd')):
            raise ValueError('Learning counts must be nonnegative integers')
        result[key] = {k: counts[k] for k in ('w', 'l', 'd')}
        if 'ts' in counts:
            if type(counts['ts']) is not int or not 0 <= counts['ts'] <= 10**12:
                raise ValueError('Invalid learning timestamp')
            result[key]['ts'] = counts['ts']
    return result


def configuration(data):
    if not isinstance(data, dict) or type(data.get('schema_version', 1)) is not int or data.get('schema_version', 1) != 1:
        raise ValueError('Unsupported preferences format')
    for key, low, high in (('transposition_limit', 1000, 200000), ('learning_max_entries', 1000, 100000), ('ai_depth', 1, 12), ('clock_time', 0, 86400),
                            ('clock_increment', 0, 3600), ('window_width', 100, 20000),
                            ('window_height', 100, 20000)):
        if key in data and (type(data[key]) not in (int, float) or
                            not math.isfinite(data[key]) or not low <= data[key] <= high):
            raise ValueError(f'Invalid preference: {key}')
    for key in ('sound_enabled', 'clock_enabled', 'board_flipped', 'high_contrast'):
        if key in data and type(data[key]) is not bool:
            raise ValueError(f'Invalid preference: {key}')
    for key, values in (('theme', ('light', 'dark')), ('piece_style', ('Images', 'Symbols', 'Letters')),
                        ('text_size', ('Normal', 'Large'))):
        if key in data and data[key] not in values:
            raise ValueError(f'Invalid preference: {key}')
    if 'learning_profile' in data:
        name = data['learning_profile']
        if not isinstance(name, str):
            raise ValueError('Invalid learning profile name')
        if name:
            from profile_store import profile_path
            profile_path('.', name)
    if 'statistics' in data:
        if not isinstance(data['statistics'], dict) or any(type(v) is not int or v < 0
                                                         for v in data['statistics'].values()):
            raise ValueError('Invalid statistics')
    return data


def validated_fen(text):
    if not isinstance(text, str) or len(text) > 256:
        raise ValueError('Enter a FEN of at most 256 characters')
    board = chess.Board(text.strip())
    if not board.is_valid():
        raise ValueError('Position is not a valid chess position (check kings, pawns and side to move)')
    return board


def training_checkpoint(data):
    if not isinstance(data, dict) or data.get('version', 1) != 1:
        raise ValueError('Unsupported training checkpoint version')
    results = data.get('results')
    if not isinstance(results, dict) or any(type(results.get(k)) is not int or results[k] < 0
                                            for k in ('white', 'black', 'draw')):
        raise ValueError('Invalid training results')
    elapsed = data.get('elapsed_seconds', 0)
    if type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0:
        raise ValueError('Invalid training elapsed time')
    settings = data.get('settings', {})
    if not isinstance(settings, dict):
        raise ValueError('Invalid training settings')
    for name, low, high in (('depth', 1, 100), ('move_ms', 1, 3600000), ('exploration', 0, 1)):
        if name in settings:
            value = settings[name]
            if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
                raise ValueError(f'Invalid training setting: {name}')
    if 'varied_starts' in settings and type(settings['varied_starts']) is not bool:
        raise ValueError('Invalid varied-starts setting')
    if 'seed' in settings and type(settings['seed']) is not int:
        raise ValueError('Invalid training seed')
    return data
