"""Minimal logging helper for the chess application.

Provides thin wrappers so we can later swap out print-based logging for
structured logging without changing call sites.
"""
from __future__ import annotations
import sys, time

LEVELS = {"info": "INFO", "warn": "WARN", "error": "ERROR", "debug": "DEBUG"}
_enabled_debug = False

def set_debug(enabled: bool) -> None:
    global _enabled_debug
    _enabled_debug = bool(enabled)

def _log(level: str, msg: str) -> None:
    if level == 'debug' and not _enabled_debug:
        return
    try:
        ts = time.strftime('%H:%M:%S')
        print(f"[{ts} {LEVELS.get(level, level.upper())}] {msg}")
    except Exception:
        try:
            print(msg)
        except Exception:
            pass

def info(msg: str) -> None: _log('info', msg)
def warn(msg: str) -> None: _log('warn', msg)
def error(msg: str) -> None: _log('error', msg)
def debug(msg: str) -> None: _log('debug', msg)
