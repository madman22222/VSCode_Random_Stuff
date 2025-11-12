"""Shared constants for the chess GUI project."""
from typing import Dict

PIECE_UNICODE = {
    'P': '♙', 'N': '♘', 'B': '♗', 'R': '♖', 'Q': '♕', 'K': '♔',
    'p': '♟', 'n': '♞', 'b': '♝', 'r': '♜', 'q': '♛', 'k': '♚',
}

# Board colors - Light theme
LIGHT_COLOR = '#F0D9B5'
DARK_COLOR = '#B58863'
HIGHLIGHT_COLOR = '#AAFF88'
LEGAL_MOVE_COLOR = '#88FFDD'
CAPTURE_COLOR = '#FF8888'
LAST_MOVE_COLOR = '#FFEB99'

# Dark theme colors
DARK_LIGHT_COLOR = '#4A4A4A'
DARK_DARK_COLOR = '#2B2B2B'
DARK_HIGHLIGHT_COLOR = '#6B8E23'
DARK_LEGAL_MOVE_COLOR = '#4682B4'
DARK_CAPTURE_COLOR = '#DC143C'
DARK_LAST_MOVE_COLOR = '#FFD700'

# Theme palettes
THEMES: Dict[str, Dict[str, str]] = {
    'light': {
        'light_square': LIGHT_COLOR,
        'dark_square': DARK_COLOR,
        'highlight': HIGHLIGHT_COLOR,
        'legal_move': LEGAL_MOVE_COLOR,
        'capture': CAPTURE_COLOR,
        'last_move': LAST_MOVE_COLOR,
        'bg': '#F5F5F5',
        'fg': '#000000',
        'button_bg': '#E0E0E0',
    },
    'dark': {
        'light_square': DARK_LIGHT_COLOR,
        'dark_square': DARK_DARK_COLOR,
        'highlight': DARK_HIGHLIGHT_COLOR,
        'legal_move': DARK_LEGAL_MOVE_COLOR,
        'capture': DARK_CAPTURE_COLOR,
        'last_move': DARK_LAST_MOVE_COLOR,
        'bg': '#1E1E1E',
        'fg': '#FFFFFF',
        'button_bg': '#3C3C3C',
    }
}

# Board dimensions
SQUARE_SIZE = 60
BOARD_SIZE = 8

# AI defaults
DEFAULT_AI_DEPTH = 3
MIN_AI_DEPTH = 1
MAX_AI_DEPTH = 6

# Animation settings
ANIMATION_FRAMES = 10
ANIMATION_DELAY = 10  # milliseconds

# Sound file paths (relative to chess directory)
SOUNDS = {
    'move': 'assets/sounds/move.wav',
    'capture': 'assets/sounds/capture.wav',
    'check': 'assets/sounds/check.wav',
    'checkmate': 'assets/sounds/checkmate.wav',
    'castle': 'assets/sounds/castle.wav',
    'illegal': 'assets/sounds/illegal.wav',
}

# Coordinate labels
FILES = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']
RANKS = ['1', '2', '3', '4', '5', '6', '7', '8']
