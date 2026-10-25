"""Rotating local application log; no gameplay databases are logged."""
import logging
from logging.handlers import RotatingFileHandler
from app_paths import data_dir

_log = logging.getLogger('chess_studio')
_log.setLevel(logging.INFO)
_log.propagate = False


def setup_logging():
    if _log.handlers:
        return _log
    try:
        folder = data_dir() / 'logs'
        folder.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(folder / 'application.log', maxBytes=512 * 1024,
                                      backupCount=3, encoding='utf-8')
        handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
        _log.addHandler(handler)
    except OSError:
        _log.addHandler(logging.NullHandler())
    return _log


def set_debug(enabled):
    _log.setLevel(logging.DEBUG if enabled else logging.INFO)


def info(msg):
    setup_logging().info(msg)


def warn(msg):
    setup_logging().warning(msg)


def error(msg):
    setup_logging().error(msg)


def debug(msg):
    if _log.isEnabledFor(logging.DEBUG):
        setup_logging().debug(msg)
