"""Profile backup/restore with checksums, bounded inputs, leases and rollback."""
from contextlib import ExitStack, contextmanager
import hashlib
import gzip
import io
import json
import os
from pathlib import Path, PurePosixPath
import tempfile
import time
import zipfile
from learning_storage import writer_lease

MAX_ARCHIVE_BYTES = 128 * 1024 * 1024
MAX_FILES = 2000


def allowed(name):
    p = PurePosixPath(name)
    if not name or '\\' in name or p.is_absolute() or '..' in p.parts or ':' in name:
        return False
    if len(p.parts) == 1:
        return (name in ('chess_config.json', 'last_session.json') or
                name.startswith(('ai_learn', 'last_session.invalid-')) and
                name.endswith(('.json', '.json.gz')))
    return p.parts[0] in ('profiles', 'autosaves', 'comparison-history', 'puzzle-packs') and p.suffix in ('.json', '.gz', '.pgn')


class ProfileStore:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def files(self):
        result = {}
        for path in self.root.rglob('*'):
            name = path.relative_to(self.root).as_posix()
            if allowed(name) and path.is_file() and not path.is_symlink():
                if any(parent.is_symlink() for parent in path.parents if parent != self.root):
                    raise ValueError('Profile contains a symbolic link')
                result[name] = path
        return result

    @contextmanager
    def lease(self, extra=()):
        # Lock every known memory profile, including empty ones and incoming files.
        paths = {'ai_learn.json'}
        for name in list(self.files()) + list(extra):
            if name.endswith('.json.gz'):
                paths.add(name[:-3])
            elif name.endswith('.json') and ('ai_learn' in name or name.startswith('profiles/')):
                paths.add(name)
        with ExitStack() as stack:
            stack.enter_context(writer_lease(self.root / '.profile'))
            for name in sorted(paths):
                path = self.root / name
                if not path.resolve().is_relative_to(self.root) or path.is_symlink():
                    raise ValueError('Profile path escapes the data folder')
                stack.enter_context(writer_lease(self.root / name))
            yield

    def backup(self, target):
        with self.lease():
            return self._backup(Path(target))

    def _backup(self, target):
        files = self.files()
        if len(files) > MAX_FILES or sum(p.stat().st_size for p in files.values()) > MAX_ARCHIVE_BYTES:
            raise ValueError('Profile exceeds the backup size/file limit')
        if target.resolve().is_relative_to(self.root) and allowed(target.resolve().relative_to(self.root).as_posix()):
            raise ValueError('Choose a backup outside runtime files')
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, temp = tempfile.mkstemp(dir=target.parent, suffix='.zip.tmp')
        os.close(fd)
        try:
            manifest = {'version': 1, 'files': {}}
            with zipfile.ZipFile(temp, 'w', zipfile.ZIP_DEFLATED) as archive:
                for name, path in sorted(files.items()):
                    content = path.read_bytes()
                    archive.writestr(name, content)
                    manifest['files'][name] = hashlib.sha256(content).hexdigest()
                archive.writestr('MANIFEST.json', json.dumps(manifest))
            os.replace(temp, target)
        finally:
            Path(temp).unlink(missing_ok=True)
        return target

    def inspect(self, archive_path):
        with zipfile.ZipFile(archive_path) as archive:
            entries = archive.infolist()
            names = [e.filename for e in entries]
            if len(names) > MAX_FILES + 1 or len(set(names)) != len(names):
                raise ValueError('Duplicate or excessive archive entries')
            if sum(e.file_size for e in entries) > MAX_ARCHIVE_BYTES:
                raise ValueError('Archive exceeds the 128 MiB extraction limit')
            if 'MANIFEST.json' not in names or any(n != 'MANIFEST.json' and not allowed(n) for n in names):
                raise ValueError('Archive contains unsupported profile paths')
            manifest = json.loads(archive.read('MANIFEST.json'))
            if not isinstance(manifest, dict) or manifest.get('version') != 1 or not isinstance(manifest.get('files'), dict):
                raise ValueError('Unsupported backup format')
            if set(names) != set(manifest['files']) | {'MANIFEST.json'}:
                raise ValueError('Backup manifest does not match archive')
            files = {}
            for name, digest in manifest['files'].items():
                content = archive.read(name)
                if hashlib.sha256(content).hexdigest() != digest:
                    raise ValueError(f'Checksum mismatch: {name}')
                files[name] = content
            from data_validation import configuration, learning_records, training_checkpoint, MAX_JSON_BYTES
            for name, content in files.items():
                if name.endswith('.gz'):
                    with gzip.GzipFile(fileobj=io.BytesIO(content)) as stream:
                        content = stream.read(MAX_JSON_BYTES + 1)
                if name.endswith(('.json', '.gz')):
                    if len(content) > MAX_JSON_BYTES:
                        raise ValueError('Profile JSON exceeds the input limit')
                    value = json.loads(content)
                    if not isinstance(value, dict):
                        raise ValueError('Profile JSON must be an object')
                    if name == 'chess_config.json':
                        configuration(value)
                    elif Path(name).name.startswith('ai_learn') and not name.endswith(('.training.json', '.benchmark.json')):
                        learning_records(value)
                    elif name.endswith('.training.json'):
                        training_checkpoint(value)
                    elif name == 'last_session.json':
                        from session_store import SessionStore
                        with tempfile.TemporaryDirectory() as temp:
                            staged = Path(temp) / 'last_session.json'
                            staged.write_bytes(content)
                            SessionStore(staged).load()
                    elif name.startswith('puzzle-packs/'):
                        from puzzle_packs import load_pack
                        with tempfile.TemporaryDirectory() as temp:
                            staged = Path(temp) / 'pack.json'
                            staged.write_bytes(content)
                            load_pack(staged)
            return files

    def restore(self, archive_path):
        incoming = self.inspect(archive_path)  # Validate everything before mutation.
        with self.lease(incoming):
            original = {n: p.read_bytes() for n, p in self.files().items()}
            rollback = self.root / 'backups' / f'before-restore-{time.time_ns()}.zip'
            self._backup(rollback)
            try:
                self._replace(incoming)
            except Exception:
                self._replace(original)
                raise
        return rollback

    def _replace(self, files):
        # Refuse symlinks even for incoming paths not present in the old profile.
        for name in files:
            path = self.root / name
            if not path.resolve().is_relative_to(self.root) or path.is_symlink():
                raise ValueError('Restore path escapes the profile')
        for name, content in files.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, temporary = tempfile.mkstemp(dir=path.parent)
            try:
                with os.fdopen(fd, 'wb') as stream:
                    stream.write(content)
                os.replace(temporary, path)
            finally:
                Path(temporary).unlink(missing_ok=True)
        for name, path in self.files().items():
            if name not in files:
                path.unlink()


def profile_path(root, name):
    import re
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,39}', name):
        raise ValueError('Use 1–40 letters, digits, underscores or hyphens')
    return Path(root) / 'profiles' / name / 'ai_learn.json'
