"""An atomic recovery record couples move memory to its training counters."""
import hashlib
import json
from pathlib import Path
from data_validation import read_json, learning_records, training_checkpoint


def fingerprint(records):
    return hashlib.sha256(json.dumps(records, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def disk_records(ai):
    path = Path(ai._learning_path_gz)
    if not path.exists():
        path = Path(ai._learning_path)
    return learning_records(read_json(path)) if path.exists() else {}


def validate_journal(data):
    if not isinstance(data, dict) or type(data.get('version')) is not int or data['version'] != 1:
        raise ValueError('Unsupported training recovery format')
    records = learning_records(data.get('memory'))
    training_checkpoint(data.get('progress'))
    if fingerprint(records) != data.get('fingerprint'):
        raise ValueError('Training recovery memory checksum mismatch')
    previous = data.get('previous_fingerprint')
    if not isinstance(previous, str) or len(previous) != 64 or any(c not in '0123456789abcdef' for c in previous):
        raise ValueError('Invalid previous recovery fingerprint')
    return records


def recoverable(ai, path):
    data = read_json(path)
    records = validate_journal(data)
    current = fingerprint(disk_records(ai))
    if current not in (data['fingerprint'], data['previous_fingerprint']):
        raise ValueError('Move memory changed since this checkpoint. Start a new run to retain the newer memory; exact resume is unavailable.')
    return data['progress'], records
