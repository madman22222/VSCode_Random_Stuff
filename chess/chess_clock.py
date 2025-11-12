"""Chess clock with time controls and increment support."""
import tkinter as tk
from typing import Optional, Callable
import time


class ChessClock:
    """Chess clock with time control and increment support."""
    
    def __init__(self, white_time: int = 600, black_time: int = 600,
                 increment: int = 0, on_timeout: Optional[Callable[[bool], None]] = None):
        """
        Args:
            white_time: Initial time for white in seconds
            black_time: Initial time for black in seconds
            increment: Increment per move in seconds
            on_timeout: Callback when time runs out, receives is_white boolean
        """
        self.white_time = white_time
        self.black_time = black_time
        self.increment = increment
        self.on_timeout = on_timeout
        self.running = False
        self.active_color = True  # True = white, False = black
        self.last_update = 0.0
        self.timer_id: Optional[str] = None
        self.root: Optional[tk.Tk] = None
    
    def start(self, root: tk.Tk, is_white: bool = True) -> None:
        """Start the clock for the specified color."""
        self.root = root
        self.running = True
        self.active_color = is_white
        self.last_update = time.time()
        self._tick()
    
    def stop(self) -> None:
        """Stop the clock."""
        self.running = False
        if self.timer_id and self.root:
            try:
                self.root.after_cancel(self.timer_id)
            except Exception:
                pass
            self.timer_id = None
    
    def switch(self) -> None:
        """Switch active color and add increment."""
        if not self.running:
            return
        
        # Add increment to current player
        if self.active_color:
            self.white_time += self.increment
        else:
            self.black_time += self.increment
        
        # Switch colors
        self.active_color = not self.active_color
        self.last_update = time.time()
    
    def _tick(self) -> None:
        """Update clock every 100ms."""
        if not self.running or not self.root:
            return
        
        # Calculate elapsed time
        now = time.time()
        elapsed = now - self.last_update
        self.last_update = now
        
        # Update active clock
        if self.active_color:
            self.white_time -= elapsed
            if self.white_time <= 0:
                self.white_time = 0
                self.stop()
                if self.on_timeout:
                    self.on_timeout(True)
                return
        else:
            self.black_time -= elapsed
            if self.black_time <= 0:
                self.black_time = 0
                self.stop()
                if self.on_timeout:
                    self.on_timeout(False)
                return
        
        # Schedule next tick
        self.timer_id = self.root.after(100, self._tick)
    
    def get_time_string(self, is_white: bool) -> str:
        """Get formatted time string for display."""
        time_sec = self.white_time if is_white else self.black_time
        minutes = int(time_sec // 60)
        seconds = int(time_sec % 60)
        tenths = int((time_sec * 10) % 10)
        
        if time_sec < 20:  # Show tenths when under 20 seconds
            return f"{minutes}:{seconds:02d}.{tenths}"
        else:
            return f"{minutes}:{seconds:02d}"
    
    def reset(self, white_time: int, black_time: int) -> None:
        """Reset clock to initial times."""
        self.stop()
        self.white_time = white_time
        self.black_time = black_time
        self.active_color = True
    
    def is_running(self) -> bool:
        """Check if clock is running."""
        return self.running
