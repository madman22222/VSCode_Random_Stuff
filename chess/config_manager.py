"""Configuration manager for persisting user preferences."""
import json
import os
from typing import Any, Dict, Optional


class ConfigManager:
    """Handles loading and saving application configuration to JSON file."""
    
    def __init__(self, config_file: str = 'chess_config.json'):
        self.config_file = config_file
        self.config: Dict[str, Any] = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file or return defaults."""
        default_config = {
            'ai_depth': 3,
            'engine_path': '',
            'window_width': 900,
            'window_height': 700,
            'theme': 'light',
            'sound_enabled': True,
            'board_flipped': False,
            'show_coordinates': True,
            'last_move_highlight': True,
            'animations_enabled': True,
            'animation_speed': 10,  # ms per frame
            'show_eval_bar': True,
            'clock_enabled': False,
            'clock_time': 600,  # 10 minutes default
            'clock_increment': 0,
            'statistics': {
                'games_played': 0,
                'white_wins': 0,
                'black_wins': 0,
                'draws': 0,
                'total_moves': 0
            }
        }
        
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    loaded = json.load(f)
                    # Merge with defaults to handle new keys
                    default_config.update(loaded)
                    return default_config
            except Exception as e:
                print(f"Error loading config: {e}")
                return default_config
        return default_config
    
    def save_config(self) -> None:
        """Save current configuration to file."""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        return self.config.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set configuration value and save."""
        self.config[key] = value
        self.save_config()
    
    def update_statistics(self, result: str) -> None:
        """Update game statistics. result: 'white', 'black', 'draw'"""
        stats = self.config.get('statistics', {})
        stats['games_played'] = stats.get('games_played', 0) + 1
        if result == 'white':
            stats['white_wins'] = stats.get('white_wins', 0) + 1
        elif result == 'black':
            stats['black_wins'] = stats.get('black_wins', 0) + 1
        elif result == 'draw':
            stats['draws'] = stats.get('draws', 0) + 1
        self.config['statistics'] = stats
        self.save_config()
    
    def increment_move_count(self) -> None:
        """Increment total moves played."""
        stats = self.config.get('statistics', {})
        stats['total_moves'] = stats.get('total_moves', 0) + 1
        self.config['statistics'] = stats
        self.save_config()
