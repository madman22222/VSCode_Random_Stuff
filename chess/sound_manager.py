"""Sound effect manager for chess moves and events."""
import os
from typing import Optional

try:
    import winsound  # type: ignore
    HAS_WINSOUND = True
except ImportError:
    HAS_WINSOUND = False
    winsound = None


class SoundManager:
    """Manages sound playback for chess events."""
    
    def __init__(self, base_path: str, enabled: bool = True):
        self.base_path = base_path
        self.enabled = enabled
        self.sounds_loaded = False
        self._check_sounds()
    
    def _check_sounds(self) -> None:
        """Check if sound files exist."""
        sounds_dir = os.path.join(self.base_path, 'assets', 'sounds')
        self.sounds_loaded = os.path.exists(sounds_dir)
    
    def play(self, sound_type: str) -> None:
        """Play a sound effect. sound_type: 'move', 'capture', 'check', 'checkmate', 'castle', 'illegal'"""
        if not self.enabled or not HAS_WINSOUND:
            return
        
        sound_file = self._get_sound_path(sound_type)
        if sound_file and os.path.exists(sound_file):
            try:
                # Play async so it doesn't block
                winsound.PlaySound(sound_file, winsound.SND_FILENAME | winsound.SND_ASYNC)  # type: ignore
            except Exception as e:
                print(f"Error playing sound {sound_type}: {e}")
        else:
            # Fallback to system beep for important sounds
            if sound_type in ['check', 'checkmate', 'illegal']:
                try:
                    winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)  # type: ignore
                except Exception:
                    pass
    
    def _get_sound_path(self, sound_type: str) -> Optional[str]:
        """Get full path to sound file."""
        sounds_dir = os.path.join(self.base_path, 'assets', 'sounds')
        sound_files = {
            'move': os.path.join(sounds_dir, 'move.wav'),
            'capture': os.path.join(sounds_dir, 'capture.wav'),
            'check': os.path.join(sounds_dir, 'check.wav'),
            'checkmate': os.path.join(sounds_dir, 'checkmate.wav'),
            'castle': os.path.join(sounds_dir, 'castle.wav'),
            'illegal': os.path.join(sounds_dir, 'illegal.wav'),
        }
        return sound_files.get(sound_type)
    
    def toggle(self) -> bool:
        """Toggle sound on/off. Returns new state."""
        self.enabled = not self.enabled
        return self.enabled
    
    def set_enabled(self, enabled: bool) -> None:
        """Set sound enabled state."""
        self.enabled = enabled
