"""Generate fallback piece images and overlay icons when assets are missing.

Uses PIL to create simple colored shapes representing chess pieces and special-move markers.
"""
import io
from typing import Optional, Any

try:
    from PIL import Image, ImageDraw, ImageFont  # type: ignore
except Exception:
    Image = None
    ImageDraw = None
    ImageFont = None


def create_piece_image(piece_symbol: str, size: int = 48) -> Optional[Any]:
    """Create a simple colored piece image with the Unicode glyph.
    
    Returns a PIL Image or None if PIL is unavailable.
    """
    if not Image or not ImageDraw:
        return None
    
    # color palette - brighter colors for better visibility
    white_fill = (255, 255, 255)
    black_fill = (30, 30, 30)
    is_white = piece_symbol.isupper()
    fill_color = white_fill if is_white else black_fill
    outline_color = black_fill if is_white else white_fill
    
    img = Image.new('RGBA', (size, size), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    
    # draw a simple circle for the piece background
    margin = 2
    draw.ellipse([margin, margin, size - margin, size - margin], fill=fill_color, outline=outline_color, width=3)
    
    # try to draw the Unicode glyph in the center
    try:
        # use a larger font for better visibility
        if ImageFont:
            font = ImageFont.truetype("arial.ttf", int(size * 0.7))
        else:
            font = None
    except Exception:
        try:
            if ImageFont:
                # Try segoeui which has good chess symbols on Windows
                font = ImageFont.truetype("segoeui.ttf", int(size * 0.7))
            else:
                font = None
        except Exception:
            try:
                if ImageFont:
                    font = ImageFont.load_default()
                else:
                    font = None
            except Exception:
                font = None
    
    piece_unicode = {
        'P': '♙', 'N': '♘', 'B': '♗', 'R': '♖', 'Q': '♕', 'K': '♔',
        'p': '♟', 'n': '♞', 'b': '♝', 'r': '♜', 'q': '♛', 'k': '♚',
    }
    glyph = piece_unicode.get(piece_symbol, piece_symbol)
    
    if font:
        try:
            # compute text bounding box and center
            bbox = draw.textbbox((0, 0), glyph, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            x = (size - text_width) // 2 - bbox[0]
            y = (size - text_height) // 2 - bbox[1]
            draw.text((x, y), glyph, fill=outline_color, font=font)
        except Exception:
            pass
    
    return img


def create_overlay_icon(icon_type: str, size: int = 48) -> Optional[Any]:
    """Create a small overlay marker icon for en-passant or castling.
    
    icon_type: 'ep' for en-passant, 'castle' for castling.
    Returns a PIL Image or None if PIL is unavailable.
    """
    if not Image or not ImageDraw:
        return None
    
    img = Image.new('RGBA', (size, size), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    
    if icon_type == 'ep':
        # draw a small blue circle in the corner
        margin = size // 2
        draw.ellipse([margin, margin, size - 2, size - 2], fill=(100, 150, 255, 200), outline=(50, 100, 200, 255), width=1)
    elif icon_type == 'castle':
        # draw a small orange/yellow square in the corner
        margin = size // 2
        draw.rectangle([margin, margin, size - 2, size - 2], fill=(255, 170, 50, 200), outline=(200, 130, 30, 255), width=1)
    
    return img


def create_all_piece_images(size: int = 48) -> dict:
    """Generate all chess piece images as a dict mapping symbol -> PIL Image."""
    pieces = {}
    for sym in ['P', 'N', 'B', 'R', 'Q', 'K', 'p', 'n', 'b', 'r', 'q', 'k']:
        img = create_piece_image(sym, size)
        if img:
            pieces[sym] = img
    return pieces


def create_overlay_icons(size: int = 48) -> dict:
    """Generate overlay icons for special moves."""
    icons = {}
    for icon_type in ['ep', 'castle']:
        img = create_overlay_icon(icon_type, size)
        if img:
            icons[icon_type] = img
    return icons
