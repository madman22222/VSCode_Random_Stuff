"""Rolling checkpoints and a staged, checksum-verified portable upgrade assistant."""
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
import time
import zipfile
from data_validation import MAX_JSON_BYTES, read_json
from training_journal import validate_journal
from profile_store import ProfileStore


def rotate_checkpoint(path, keep=3, trusted=False):
    path = Path(path)
    if not path.exists():
        return
    if not 1 <= int(keep) <= 10:
        raise ValueError('Keep 1–10 checkpoint generations')
    if path.stat().st_size > MAX_JSON_BYTES:
        raise ValueError('Checkpoint exceeds recovery input limit')
    invalid = False
    if not trusted:
        try: validate_journal(read_json(path))
        except (OSError, ValueError, TypeError, EOFError): invalid = True
    directory = path.parent / 'checkpoints'
    directory.mkdir(parents=True, exist_ok=True)
    suffix = '.invalid-' if invalid else '-'
    target = directory / (path.name + suffix + str(time.time_ns()) + '.json')
    fd, temp = tempfile.mkstemp(dir=directory)
    os.close(fd)
    try:
        shutil.copyfile(path, temp)
        os.replace(temp, target)
    finally:
        Path(temp).unlink(missing_ok=True)
    valid = sorted(directory.glob(path.name + '-*.json'), reverse=True)
    for old in valid[int(keep):]:
        old.unlink()


def checkpoint_choices(memory):
    memory = Path(memory)
    return sorted((memory.parent / 'checkpoints').glob(memory.name + '.checkpoint.json-*.json'), reverse=True)


def checkpoint_preview(path):
    data = read_json(path)
    records = validate_journal(data)
    return {'records': len(records), 'games': sum(data['progress']['results'].values()),
            'results': data['progress']['results'], 'settings': data['progress'].get('settings', {}),
            'fingerprint': data['fingerprint']}


def _archive(files, target):
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items(): archive.writestr(name, content)
        archive.writestr('MANIFEST.json', json.dumps({'version': 1, 'files':
            {name: hashlib.sha256(content).hexdigest() for name, content in files.items()}}))


def restore_checkpoint(root, memory, snapshot):
    root, memory = Path(root).resolve(), Path(memory).resolve()
    if not memory.is_relative_to(root):
        raise ValueError('Checkpoint restore requires a profile inside the data folder')
    data = read_json(snapshot)
    validate_journal(data)
    store = ProfileStore(root)
    # ProfileStore handles validation, leases, rollback backup and atomic replacement.
    files = {name: path.read_bytes() for name, path in store.files().items()}
    name = memory.relative_to(root).as_posix()
    files.pop(name + '.gz', None)
    files[name] = json.dumps(data['memory']).encode()
    files[name + '.checkpoint.json'] = json.dumps(data).encode()
    files[name + '.training.json'] = json.dumps(data['progress']).encode()
    with tempfile.TemporaryDirectory() as temp:
        archive = Path(temp) / 'recovery.zip'
        _archive(files, archive)
        return store.restore(archive)


def inspect_upgrade(archive_path, checksum_path):
    path = Path(archive_path)
    expected = Path(checksum_path).read_text(encoding='utf-8').split()[0].lower()
    if len(expected) != 64 or any(c not in '0123456789abcdef' for c in expected):
        raise ValueError('Invalid SHA-256 file')
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''): digest.update(block)
    if digest.hexdigest() != expected:
        raise ValueError('ZIP checksum does not match; no upgrade files were changed')
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        if len(entries) > 10000 or sum(x.file_size for x in entries) > 512 * 1024 * 1024:
            raise ValueError('Upgrade archive exceeds extraction limits')
        names = [x.filename for x in entries]
        if len(set(names)) != len(names):
            raise ValueError('Duplicate ZIP paths')
        for item in entries:
            p = PurePosixPath(item.filename)
            if not item.filename or '\\' in item.filename or p.is_absolute() or '..' in p.parts or ':' in item.filename or stat.S_ISLNK(item.external_attr >> 16):
                raise ValueError('Unsafe upgrade ZIP path')
        roots = {PurePosixPath(name).parts[0] for name in names}
        if len(roots) != 1 or next(iter(roots)) not in ('ChessStudio', 'ChessStudio-VSCode'):
            raise ValueError('Choose an official Windows or VS Code edition ZIP')
        folder = next(iter(roots))
        info_name = folder + '/BUILD_INFO.json'
        if info_name not in names or archive.getinfo(info_name).file_size > 65536:
            raise ValueError('Missing/oversized build information')
        info = json.loads(archive.read(info_name))
        revision = info.get('revision')
        if not isinstance(revision, str) or len(revision) != 40 or any(c not in '0123456789abcdef' for c in revision.lower()):
            raise ValueError('Invalid build revision')
        entry = folder + ('/ChessStudio.exe' if folder == 'ChessStudio' else '/chess/main.py')
        if entry not in names:
            raise ValueError('Missing edition launcher')
        return {'revision': revision, 'folder': folder, 'sha256': expected, 'files': len(entries),
                'uncompressed_bytes': sum(x.file_size for x in entries),
                'notice': 'A checksum verifies file integrity, not publisher identity. Use ZIP/checksum files from this repository release.'}


def _prepare_upgrade(root, archive_path, checksum_path, destination_parent):
    info = inspect_upgrade(archive_path, checksum_path)
    root = Path(root).resolve()
    parent = Path(destination_parent).resolve()
    if parent == root or parent.is_relative_to(root):
        raise ValueError('Choose a destination outside the existing data folder')
    target = parent / ('ChessStudio-upgrade-' + info['revision'][:7])
    if target.exists():
        raise ValueError('Prepared destination already exists; choose another parent folder')
    parent.mkdir(parents=True, exist_ok=True)
    store = ProfileStore(root)
    backup = root / 'backups' / ('before-upgrade-' + str(time.time_ns()) + '.zip')
    with store.lease():
        store._backup(backup)
        files = store.files()
        with tempfile.TemporaryDirectory(prefix='.chess-upgrade-', dir=parent) as temp:
            stage = Path(temp) / 'prepared'; stage.mkdir()
            with zipfile.ZipFile(archive_path) as archive:
                # Inspection bounded and checked every path; extract only into staging.
                for item in archive.infolist():
                    output = stage / item.filename
                    if item.is_dir(): output.mkdir(parents=True, exist_ok=True); continue
                    output.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(item) as source, output.open('wb') as sink:
                        remaining = item.file_size
                        while remaining:
                            block = source.read(min(1024 * 1024, remaining))
                            if not block: raise ValueError('Truncated ZIP entry')
                            sink.write(block); remaining -= len(block)
                        if source.read(1): raise ValueError('ZIP entry exceeds declared size')
            profile = stage / info['folder'] / ('data' if info['folder'] == 'ChessStudio' else 'chess')
            profile.mkdir(parents=True, exist_ok=True)
            for name, source in files.items():
                output = profile / name
                if output.exists(): raise ValueError('Upgrade archive unexpectedly contains user profile data')
                output.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, output)
            os.replace(stage, target)
    return {'folder': str(target / info['folder']), 'backup': str(backup), 'revision': info['revision'],
            'next': 'Close the old copy, then open the launcher in the prepared folder. The old installation remains available.'}


def prepare_upgrade(root, archive_path, checksum_path, destination_parent):
    # Verify and extract the same private copy, even if the download path changes.
    with tempfile.TemporaryDirectory(prefix='chess-release-') as temp:
        copied = Path(temp) / 'release.zip'
        shutil.copyfile(archive_path, copied)
        return _prepare_upgrade(root, copied, checksum_path, destination_parent)
