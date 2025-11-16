"""Engine Adapter abstraction layer.
Unifies external engine (UCI) interactions behind a minimal interface so
the GUI/controller logic does not depend on concrete engine_manager details.
"""
from __future__ import annotations

from typing import Optional
import chess  # type: ignore

try:
    from logger import debug, info, warn, error
except Exception:
    def debug(*a, **k): pass
    def info(*a, **k): pass
    def warn(*a, **k): pass
    def error(*a, **k): pass


class EngineAdapter:
    """Wraps an EngineManager instance providing simplified calls."""
    def __init__(self, engine_manager):
        self._mgr = engine_manager
        self._started = False

    def detect(self) -> Optional[str]:
        return self._mgr.detect()

    def start(self, path: str) -> bool:
        ok = self._mgr.start(path)
        self._started = ok
        if ok:
            info(f"Engine started at {path}")
        else:
            warn(f"Failed to start engine at {path}")
        return ok

    def stop(self) -> None:
        try:
            self._mgr.stop()
            if self._started:
                info("Engine stopped")
        finally:
            self._started = False

    def is_running(self) -> bool:
        return bool(getattr(self._mgr, 'engine', None))

    def play_move(self, board: chess.Board, time_seconds: float) -> Optional[chess.Move]:
        if not self.is_running():
            return None
        try:
            limit = chess.engine.Limit(time=max(0.01, time_seconds))
            result = self._mgr.play(board, limit)
            return getattr(result, 'move', None)
        except Exception as e:
            warn(f"Engine play failed: {e}")
            return None

    def verify(self, path: str, **kwargs):
        return self._mgr.verify_engine(path, **kwargs)

    def download_stockfish(self, prefer_platform: str = 'auto', token: str = ''):
        """Download Stockfish via underlying manager.

        Returns path to downloaded binary or None.
        """
        try:
            return self._mgr.download_stockfish(prefer_platform=prefer_platform, token=token)
        except Exception as e:
            warn(f"Engine download failed: {e}")
            return None
