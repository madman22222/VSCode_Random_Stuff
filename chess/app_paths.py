"""Locate immutable bundled resources separately from writable user data."""
from functools import lru_cache
import os
from pathlib import Path
import sys
import tempfile


def frozen():
    return bool(getattr(sys, 'frozen', False))


def resource_dir():
    return Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent)).resolve()


def _writable(path):
    path.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryFile(dir=path):
        pass
    return path


@lru_cache(maxsize=1)
def data_dir():
    override = os.environ.get('CHESS_STUDIO_DATA_DIR')
    if override:
        return _writable(Path(override).expanduser().resolve())
    preferred = Path(sys.executable).resolve().parent / 'data' if frozen() else Path(__file__).resolve().parent
    try:
        return _writable(preferred)
    except OSError:
        # A protected install folder must not make saving or startup fail.
        local = os.environ.get('LOCALAPPDATA')
        fallback = Path(local) / 'ChessStudio' if local else Path.home() / '.local' / 'share' / 'ChessStudio'
        return _writable(fallback)


def training_command():
    if frozen():
        console = Path(sys.executable).with_name('ChessStudio-CLI.exe')
        return [str(console if console.exists() else Path(sys.executable))]
    return [sys.executable, str(resource_dir() / 'main.py')]
