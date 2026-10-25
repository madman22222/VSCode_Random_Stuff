"""An OS-held writer lease prevents competing processes overwriting move memory."""
from contextlib import contextmanager
import os
from pathlib import Path


@contextmanager
def writer_lease(learning_path):
    path = Path(str(learning_path) + '.lock')
    path.parent.mkdir(parents=True, exist_ok=True)
    stream = open(path, 'a+b')
    try:
        try:
            if os.name == 'nt':
                import msvcrt
                if path.stat().st_size == 0:
                    stream.write(b'0')
                    stream.flush()
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise RuntimeError('This learning file is already in use by another writer. '
                               'Stop that training process or choose a different learning file.') from exc
        yield
    finally:
        # Closing the handle releases the lock, including on process exit.
        # Keep the file: deleting it would let a new writer lock a different inode.
        stream.close()
