"""
Chess Game Controller with AI Learning
======================================

This module provides a complete chess GUI application with:
- Built-in AI with bounded iterative alpha-beta search and ordering heuristics
- Persistent learning system that improves move ordering based on game outcomes
- Human-readable learning export and import
- Support for external engines (Stockfish)
- Multiple game modes: Player vs Player, Player vs AI, AI vs AI
- Themes, sound effects, chess clock, and game statistics
- PGN save/load functionality

Architecture:
- SimpleAI and TrainingAI are imported from their dedicated modules.
- GameController coordinates the desktop UI, board and optional UCI engine.
"""

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Optional
import chess  # type: ignore - Python-chess library handles all chess rules (legal moves, check, checkmate, castling, en passant, etc.)
from simple_ai import SimpleAI
from studio_features import StudioFeatures
from studio_tools import StudioTools
from training_controls import TrainingControls
from app_paths import data_dir, resource_dir, training_command
from tools.batch_pgn_converter import batch_convert
from engine_manager import EngineManager
from engine_adapter import EngineAdapter

import os
from learning_keys import position_key
import time
import threading
import queue
import copy
from chess_coach import illegal_move_message, describe_move
import shutil
import csv
from pathlib import Path
import chess.pgn
from PIL import Image, ImageTk
from board_view import BoardView
from config_manager import ConfigManager
from sound_manager import SoundManager
from chess_clock import ChessClock
import image_generator

class Tooltip:
    def __init__(self, widget, text):
        self.window = None
        self.widget = widget
        self.text = text
        widget.bind('<Enter>', self.show)
        widget.bind('<Leave>', self.hide)
        widget.bind('<Destroy>', self.hide)

    def show(self, event=None):
        if self.window is not None:
            return
        self.window = tk.Toplevel(self.widget)
        self.window.wm_overrideredirect(True)
        self.window.geometry(f'+{self.widget.winfo_rootx() + 15}+{self.widget.winfo_rooty() + 25}')
        tk.Label(self.window, text=self.text, wraplength=300,
                 background='#fff9c4', relief='solid', borderwidth=1).pack()

    def hide(self, event=None):
        if self.window is not None:
            self.window.destroy()
            self.window = None


HAS_UPGRADES = True


class GameController(TrainingControls, StudioTools, StudioFeatures):
    """Coordinates the GUI view, AI, and engine manager.

    This class owns the game state and provides callbacks for UI events.
    """

    def __init__(self, master: tk.Tk, config=None):
        self.master = master
        self.ui_font = "Segoe UI" if os.name == "nt" else "DejaVu Sans"
        
        # Initialize config manager first
        if HAS_UPGRADES and ConfigManager:
            self.config = config if config is not None else ConfigManager()
        else:
            self.config = None
        
        self.master.title('Python Chess — AI / Engine (Enhanced)')
        self.board = chess.Board()
        
        # Get AI depth from config
        ai_depth = self.config.get('ai_depth', 3) if self.config else 3
        selected = self.config.get('learning_profile', '') if self.config else ''
        from profile_store import profile_path
        try:
            learning = profile_path(Path(self.config.config_file).parent, selected) if selected else None
        except ValueError:
            learning = None
        self.ai = SimpleAI(depth=ai_depth, learning_path=learning)
        self.ai.transposition_limit = int(self.config.get('transposition_limit', 40000)) if self.config else 40000
        self.ai.learning_max_entries = int(self.config.get('learning_max_entries', 50000)) if self.config else 50000
        self.ai.learning_min_keep = int(self.ai.learning_max_entries * .8)
        
        # Initialize engine adapter (wraps EngineManager)
        self.engine_adapter = EngineAdapter(EngineManager(os.fspath(data_dir())))
        self.engine_enabled = False
        self.engine = None
        self.piece_images = None
        self.overlay_icons = None
        self.selected = None
        self.ai_thinking = False  # Track when AI is making a move
        self.move_history: list = []  # Store move history for last move highlighting
        self.play_mode = 'player_vs_ai'  # New: 'player_vs_player' or 'player_vs_ai'
        # Track AI session to safely abort background moves on new game/mode changes
        self._ai_session_id = 0
        # Auto-restart control for AI vs AI mode
        self._auto_restart_scheduled = False
        # Track autosave state to avoid duplicate saves per game
        self._autosave_done = False
        # Game started flag - prevents AI from moving until Start is pressed
        self.game_started = False
        # UI update throttling for smoother high-speed AI
        self._last_ui_update = 0
        self._ui_update_interval = 0.05  # Minimum 50ms between UI updates
        # Training AI instance for headless mode
        self.training_ai = None
        self.benchmark = None
        self._training_synced = True
        self._closed = False
        self._ui_queue = queue.Queue()
        self._ai_started_at = None
        self._hint_thinking = False
        self._timed_out = False
        self._rendered_moves = None
        self._finished_learning_backup = None
        self._finished_stats_backup = None
        self._finished_log = None
        self._init_studio_state()
        
        # Initialize sound manager
        if HAS_UPGRADES and SoundManager:
            self.sound = SoundManager(
                base_path=os.fspath(resource_dir()),
                enabled=self.config.get('sound_enabled', True) if self.config else True
            )
        else:
            self.sound = None
        
        # Initialize chess clock
        if HAS_UPGRADES and ChessClock:
            clock_time = self.config.get('clock_time', 600) if self.config else 600
            clock_increment = self.config.get('clock_increment', 0) if self.config else 0
            self.clock = ChessClock(
                white_time=clock_time,
                black_time=clock_time,
                increment=clock_increment,
                on_timeout=self.on_clock_timeout
            )
            self.clock_enabled = self.config.get('clock_enabled', False) if self.config else False
        else:
            self.clock = None
            self.clock_enabled = False

        # A weighted two-column shell keeps the board and controls usable on resize.
        master.title('Chess Studio')
        master.minsize(980, 720)
        master.geometry('1220x820')
        master.columnconfigure(0, weight=3, minsize=500)
        master.columnconfigure(1, weight=1, minsize=440)
        master.rowconfigure(2, weight=1)
        header = tk.Frame(master)
        header.grid(row=0, column=0, columnspan=2, sticky='ew', padx=24, pady=(18, 4))
        self.title_label = tk.Label(header, text='CHESS STUDIO', font=(self.ui_font, 19, 'bold'))
        self.title_label.pack(side='left')
        tk.Label(header, text='Play · Learn · Improve', font=(self.ui_font, 10)).pack(side='right')
        self.status = tk.Label(master, text='White to move', font=(self.ui_font, 12, 'bold'), anchor='w')
        self.status.grid(row=1, column=0, sticky='ew', padx=24, pady=(4, 8))
        self.hints_label = tk.Label(master, text='', font=(self.ui_font, 9), anchor='w', wraplength=420)
        self.hints_label.grid(row=1, column=1, sticky='ew', padx=16)
        self.ai_last_explanation = ''

        self.board_area = tk.Frame(master)
        self.board_area.grid(row=2, column=0, sticky='nsew', padx=(24, 12), pady=(0, 20))
        board_frame = tk.Frame(self.board_area)
        board_frame.place(relx=0.5, rely=0.5, anchor='center', width=500, height=500)
        self.board_view = BoardView(board_frame, on_click=self.on_click)
        self._board_resize_job = None
        self.board_area.bind('<Configure>', self._schedule_board_resize)

        ctrl_frame = tk.Frame(master, width=440)
        ctrl_frame.pack_propagate(False)
        ctrl_frame.grid(row=2, column=1, sticky='nsew', padx=(8, 24), pady=(0, 20))
        self.ctrl_frame = ctrl_frame
        # Native notebook pages replace the very long canvas of child windows.
        # Scrolling that canvas copied stale child-window pixels on Windows.
        self.controls_notebook = ttk.Notebook(ctrl_frame)
        self.controls_notebook.pack(fill='both', expand=True)
        pages = []
        for title in ('Play', 'Training', 'Settings', 'Tools', 'Compare'):
            page = tk.Frame(self.controls_notebook, padx=12, pady=12)
            self.controls_notebook.add(page, text=title)
            pages.append(page)
        scrollable_frame, training_page, settings_page, tools_page, compare_page = pages
        self.scrollable_frame = scrollable_frame
        self.control_pages = pages

        settings_tabs = ttk.Notebook(settings_page)
        settings_tabs.pack(fill='both', expand=True)
        appearance_page, accessibility_page, tuning_page, files_page = [tk.Frame(settings_tabs) for _ in range(4)]
        for page, title in ((appearance_page, 'Appearance'), (accessibility_page, 'Access'),
                             (tuning_page, 'AI'), (files_page, 'Files')):
            settings_tabs.add(page, text=title)

        # Small helper to add an info icon with a tooltip
        def _info(parent: tk.Widget, text: str) -> tk.Label:
            lbl = tk.Label(parent, text='ℹ', font=('Arial', 8, 'bold'), fg='#3f51b5', cursor='question_arrow')
            try:
                Tooltip(lbl, text)
            except Exception:
                pass
            return lbl

        setup = tk.LabelFrame(scrollable_frame, text='Start a game')
        setup.pack(fill='x', pady=(0, 8))
        self.mode_var = tk.StringVar(master=self.master, value='player_vs_ai')
        self.mode_display_var = tk.StringVar(master=self.master, value='Play AI')
        self.difficulty_var = tk.StringVar(master=self.master, value='Medium')
        self.player_color_var = tk.StringVar(master=self.master, value='White')
        for label, variable, values, callback in (
            ('Mode', self.mode_display_var, ('Play AI', 'Two players', 'Watch AI'), self._choose_mode),
            ('Difficulty', self.difficulty_var, ('Beginner', 'Easy', 'Medium', 'Hard'), self._choose_difficulty),
            ('Your side', self.player_color_var, ('White', 'Black'), self._choose_side),
        ):
            row = tk.Frame(setup)
            row.pack(fill='x', pady=3)
            tk.Label(row, text=label, width=10, anchor='w').pack(side='left')
            chooser = ttk.Combobox(row, textvariable=variable, values=values, state='readonly', width=18)
            chooser.pack(side='right', fill='x', expand=True)
            chooser.bind('<<ComboboxSelected>>', callback)
        play_actions = tk.Frame(setup)
        play_actions.pack(fill='x', pady=8)
        self.start_pause_button = tk.Button(play_actions, text='Play', command=self.toggle_game_started)
        self.start_pause_button.pack(side='left', fill='x', expand=True, padx=2)
        self.hint_button = tk.Button(play_actions, text='Hint', command=self.request_hint)
        self.hint_button.pack(side='right', padx=2)
        self.feedback_var = tk.StringVar(master=self.master, value='Choose a mode and press Play. Click a piece to see legal moves.')
        tk.Label(scrollable_frame, textvariable=self.feedback_var, wraplength=380,
                 justify='left', anchor='w').pack(fill='x', pady=(0, 8))

        self.workspace = ttk.Notebook(scrollable_frame)
        self.workspace.pack(fill='both', expand=True)
        self.game_workspace = tk.Frame(self.workspace)
        self.practice_workspace = tk.Frame(self.workspace)
        self.review_workspace = tk.Frame(self.workspace)
        for page, label in ((self.game_workspace, 'Game'), (self.practice_workspace, 'Practice'),
                            (self.review_workspace, 'Review')):
            self.workspace.add(page, text=label)
        # Move list - more compact
        tk.Label(self.game_workspace, text='Moves', font=('Arial', 9, 'bold')).pack()
        self.move_list = tk.Listbox(self.game_workspace, width=20, height=7, font=('Arial', 8))
        self.move_list.pack(fill='both', expand=True, padx=2, pady=6)

        btn_frame = tk.Frame(self.game_workspace)
        btn_frame.pack(pady=2)
        tk.Button(btn_frame, text='Save', command=self.save_pgn, font=('Arial', 8)).grid(row=0, column=0, padx=1)
        tk.Button(btn_frame, text='Load', command=self.load_pgn, font=('Arial', 8)).grid(row=0, column=1, padx=1)
        tk.Button(btn_frame, text='Undo', command=self.undo_move, font=('Arial', 8)).grid(row=0, column=2, padx=1)
        # New Game button available in all modes
        tk.Button(btn_frame, text='New', command=self.new_game, font=('Arial', 8)).grid(row=0, column=3, padx=1)
        tk.Button(btn_frame, text='Restart', command=self.restart_game, font=('Arial', 8)).grid(row=0, column=4, padx=1)
        
        # AI depth - header with info
        depth_header = tk.Frame(tuning_page)
        depth_header.pack(fill='x')
        tk.Label(depth_header, text='AI Depth', font=('Arial', 9, 'bold')).pack(side='left')
        _info(depth_header, 'Search depth for AI in GUI modes. Higher = stronger, slower.\nFor Training AI, use Per-move time to control speed.').pack(side='left', padx=4)
        self.depth_var = tk.IntVar(master=self.master, value=ai_depth)
        depth_scale = tk.Scale(tuning_page, from_=1, to=6, orient='horizontal',
                              variable=self.depth_var, command=self.on_depth_change,
                              length=180, sliderlength=20)
        depth_scale.pack(padx=2)
        self.depth_scale = depth_scale
        # Metrics display
        self.metrics_var = tk.StringVar(master=self.master, value='Metrics: (none)')
        tk.Label(tools_page, textvariable=self.metrics_var, font=('Arial', 8), fg='#555', wraplength=370, justify='left').pack(pady=2)
        export_btn = tk.Button(tools_page, text='Export Metrics CSV', command=self.export_metrics_csv, font=('Arial', 8))
        export_btn.pack(pady=2)
        
        # Advanced timing controls stay in Settings.
        mode_frame = tk.LabelFrame(tuning_page, text='AI timing')
        mode_frame.pack(fill='x', pady=4)
        self.auto_restart_var = tk.BooleanVar(master=self.master, value=False)
        tk.Checkbutton(mode_frame, text='Restart finished Watch AI games', variable=self.auto_restart_var).pack(anchor='w')
        # AI move pacing to ensure UI keeps up (ms)
        pace_frame = tk.Frame(mode_frame)
        pace_frame.pack(fill='x', padx=8, pady=2)
        tk.Label(pace_frame, text='AI Move Delay (ms):', font=('Arial', 8)).pack(side='left')
        _info(pace_frame, 'Applies only to AI vs AI (UI) to slow moves for visibility. Training AI uses Per-move time instead.').pack(side='left', padx=4)
        self.ai_delay_var = tk.IntVar(master=self.master, value=200)
        tk.Scale(pace_frame, from_=0, to=1000, orient='horizontal', variable=self.ai_delay_var, length=120, sliderlength=14).pack(side='left', padx=4)

        # Per-move time for GUI AI (separate from Training)
        pace2_frame = tk.Frame(mode_frame)
        pace2_frame.pack(fill='x', padx=8, pady=2)
        tk.Label(pace2_frame, text='Move budget (ms):', font=('Arial', 8)).pack(side='left')
        _info(pace2_frame, 'Time cap per move for built-in AI in Player vs AI and AI vs AI (UI). Training AI uses its own Per-move time setting below.').pack(side='left', padx=4)
        self.gui_move_time_var = tk.IntVar(master=self.master, value=(self.config.get('gui_move_time_ms', 250) if self.config else 250))
        gui_move_scale = tk.Scale(pace2_frame, from_=50, to=2000, orient='horizontal', variable=self.gui_move_time_var, length=120, sliderlength=14, command=lambda _=None: self.on_gui_move_time_change())
        gui_move_scale.pack(side='left', padx=4)

        # General options
        options_frame = tk.LabelFrame(files_page, text='Options', font=('Arial', 9, 'bold'))
        options_frame.pack(fill='x', pady=2, padx=2)
        self.autosave_pgn_var = tk.BooleanVar(master=self.master, value=self.config.get('auto_save_pgn', False) if self.config else False)
        # Row for autosave option + info icon
        opts_row1 = tk.Frame(options_frame)
        opts_row1.pack(fill='x', padx=2, pady=1)
        autosave_cb = tk.Checkbutton(opts_row1, text='Auto-save PGN on game end', variable=self.autosave_pgn_var, command=self.on_toggle_autosave, font=('Arial', 8))
        autosave_cb.pack(side='left')
        _info(opts_row1, 'When enabled, saves PGN automatically at game end.').pack(side='left', padx=4)
        # Compress learning data (gzip)
        self.compress_learning_var = tk.BooleanVar(master=self.master, value=(self.config.get('compress_learning', getattr(self.ai, 'compress_learning', True)) if self.config else getattr(self.ai, 'compress_learning', True)))
        opts_row2 = tk.Frame(options_frame)
        opts_row2.pack(fill='x', padx=2, pady=1)
        compress_cb = tk.Checkbutton(opts_row2, text='Compress learning data (gzip)', variable=self.compress_learning_var,
                                     command=self.on_toggle_compress, font=('Arial', 8))
        compress_cb.pack(side='left')
        _info(opts_row2, 'Store learning as ai_learn.json.gz (smaller, faster I/O).').pack(side='left', padx=4)
        # Apply initial compression setting to AI
        try:
            self.ai.compress_learning = bool(self.compress_learning_var.get())
        except Exception:
            pass

        training_tabs = ttk.Notebook(training_page)
        training_tabs.pack(fill='both', expand=True)
        dashboard_page = tk.Frame(training_tabs)
        training_settings_page = tk.Frame(training_tabs)
        learning_page = tk.Frame(training_tabs)
        for page, title in ((dashboard_page, 'Dashboard'), (training_settings_page, 'Run settings'),
                            (learning_page, 'Memory')):
            training_tabs.add(page, text=title)
        dashboard = tk.LabelFrame(dashboard_page, text='Training dashboard')
        dashboard.pack(fill='x', pady=(0, 8))
        dashboard_actions = tk.Frame(dashboard)
        dashboard_actions.pack(fill='x')
        for label, command in (('Start', self.start_training_ai), ('Stop and save', self.stop_training_ai),
                               ('Resume', lambda: self.start_training_ai(resume=True))):
            tk.Button(dashboard_actions, text=label, command=command).pack(side='left', fill='x', expand=True, padx=2)
        self.training_dashboard_var = tk.StringVar(master=self.master, value='Ready. Resume reloads saved counters and move memory.')
        tk.Label(dashboard, textvariable=self.training_dashboard_var, justify='left',
                 wraplength=380).pack(fill='x', pady=8)
        self.training_progress = ttk.Progressbar(dashboard, mode='determinate', maximum=100)
        self.training_progress.pack(fill='x', pady=(0, 4))
        # Training settings
        training_frame = tk.LabelFrame(training_settings_page, text='Training Settings', font=('Arial', 9, 'bold'))
        training_frame.pack(fill='x', pady=2, padx=2)
        self.training_batch_size_var = tk.IntVar(master=self.master, value=(self.config.get('training_batch_size', 100) if self.config else 100))
        self.training_move_time_var = tk.IntVar(master=self.master, value=(self.config.get('training_move_time_ms', 250) if self.config else 250))  # milliseconds per move
        self.training_snapshot_interval_var = tk.IntVar(master=self.master, value=(self.config.get('training_snapshot_batches', 0) if self.config else 0))  # 0 = off
        self.training_games_var = tk.IntVar(master=self.master, value=(self.config.get('training_games', 0) if self.config else 0))
        row = tk.Frame(training_frame)
        row.pack(fill='x', padx=4, pady=1)
        tk.Label(row, text='Batch size (games):', font=('Arial', 8)).pack(side='left')
        batch_entry = tk.Entry(row, textvariable=self.training_batch_size_var, width=6, font=('Arial', 8))
        batch_entry.pack(side='left', padx=6)
        _info(row, 'Save learning after this many games. Larger = fewer writes, faster training.').pack(side='left', padx=4)
        row2 = tk.Frame(training_frame)
        row2.pack(fill='x', padx=4, pady=1)
        tk.Label(row2, text='Per-move time (ms):', font=('Arial', 8)).pack(side='left')
        move_scale = tk.Scale(row2, from_=50, to=1000, orient='horizontal', variable=self.training_move_time_var, length=120, sliderlength=14)
        move_scale.pack(side='left', padx=6)
        _info(row2, 'Time budget per move during training. Guarantees progress at high depths.').pack(side='left', padx=4)
        row3 = tk.Frame(training_frame)
        row3.pack(fill='x', padx=4, pady=1)
        tk.Label(row3, text='Snapshot interval (batches, 0=off):', font=('Arial', 8)).pack(side='left')
        snap_entry = tk.Entry(row3, textvariable=self.training_snapshot_interval_var, width=6, font=('Arial', 8))
        snap_entry.pack(side='left', padx=6)
        _info(row3, 'Export readable learning after N batches. 0 disables periodic snapshots.').pack(side='left', padx=4)
        row4 = tk.Frame(training_frame)
        row4.pack(fill='x', padx=4, pady=1)
        tk.Label(row4, text='Games to run (0=until stop):', font=('Arial', 8)).pack(side='left')
        games_entry = tk.Entry(row4, textvariable=self.training_games_var, width=8, font=('Arial', 8))
        games_entry.pack(side='left', padx=6)
        _info(row4, 'End training automatically after this many games. 0 keeps training until you stop it.').pack(side='left', padx=4)
        # Reset to defaults button
        reset_btn = tk.Button(training_frame, text='Reset Training Defaults', font=('Arial', 8), command=self.reset_training_defaults)
        reset_btn.pack(anchor='e', padx=4, pady=4)
        # Quick actions: Copy command / Run training
        actions_row = tk.Frame(training_frame)
        actions_row.pack(fill='x', padx=4, pady=4)
        tk.Button(actions_row, text='Copy command', font=('Arial', 8), command=self.copy_training_command).pack(side='left')
        tk.Button(actions_row, text='Run in console', font=('Arial', 8), command=self.run_training_now).pack(side='left', padx=6)
        _info(actions_row, 'Copy: puts a ready-to-run CLI command on clipboard. Run: opens a new console window executing training.').pack(side='left', padx=6)
        # Tooltip for reset action
        try:
            Tooltip(reset_btn, 'Restore batch=100, per-move=250ms, snapshots off, compression on.')
        except Exception:
            pass

        # Live training progress label
        stats_row = tk.Frame(training_frame)
        stats_row.pack(fill='x', padx=4, pady=2)
        tk.Label(stats_row, text='Training Progress:', font=('Arial', 8, 'bold')).pack(side='left')
        self.training_stats_label = tk.Label(stats_row, text='—', font=('Arial', 8))
        self.training_stats_label.pack(side='left', padx=6)

        exploration_row = tk.Frame(training_frame)
        exploration_row.pack(fill='x')
        self.exploration_var = tk.DoubleVar(master=self.master, value=0.10)
        self.varied_starts_var = tk.BooleanVar(master=self.master, value=True)
        tk.Label(exploration_row, text='Explore early moves:').pack(side='left')
        tk.Scale(exploration_row, from_=0, to=0.5, resolution=0.05, orient='horizontal',
                 variable=self.exploration_var, length=120).pack(side='left')
        tk.Checkbutton(training_frame, text='Vary opening positions', variable=self.varied_starts_var).pack(anchor='w')

        # New features frame - more compact
        if HAS_UPGRADES:
            features_frame = tk.LabelFrame(appearance_page, text='Features', font=('Arial', 9, 'bold'))
            features_frame.pack(fill='x', pady=2, padx=2)
            self.features_frame = features_frame
            
            # Flip board button - smaller
            tk.Button(features_frame, text='Flip Board', command=self.flip_board, 
                     font=('Arial', 8)).pack(fill='x', pady=1, padx=2)
            
            # Theme toggle - more compact
            theme_frame = tk.Frame(features_frame)
            theme_frame.pack(fill='x', pady=1, padx=2)
            tk.Label(theme_frame, text='Theme:', font=('Arial', 8)).pack(side='left')
            self.theme_var = tk.StringVar(master=self.master, value=self.config.get('theme', 'light') if self.config else 'light')
            theme_menu = tk.OptionMenu(theme_frame, self.theme_var, 'light', 'dark')
            theme_menu.config(font=('Arial', 8))
            theme_menu.pack(side='left', fill='x', expand=True)
            self.theme_var.trace_add('write', lambda *args: self.change_theme(self.theme_var.get()))
            # Apply theme on startup to ensure board colors match saved preference
            try:
                self.change_theme(self.theme_var.get())
            except Exception:
                pass
            
            # Sound toggle - smaller
            if self.sound:
                self.sound_button = tk.Button(features_frame, 
                                             text=f"Sound: {'On' if self.sound.enabled else 'Off'}",
                                             command=self.toggle_sound,
                                             font=('Arial', 8))
                self.sound_button.pack(fill='x', pady=1, padx=2)
            
            # Clock controls - more compact
            if self.clock:
                clock_frame = tk.LabelFrame(features_frame, text='Clock', font=('Arial', 8))
                clock_frame.pack(fill='x', pady=2, padx=2)
                
                self.white_clock_label = tk.Label(clock_frame, text="10:00",
                                                  font=('Arial', 11, 'bold'), fg='white', bg='black')
                self.white_clock_label.pack(fill='x', padx=2, pady=1)
                
                self.black_clock_label = tk.Label(clock_frame, text="10:00",
                                                  font=('Arial', 11, 'bold'), fg='black', bg='white')
                self.black_clock_label.pack(fill='x', padx=2, pady=1)
                
                clock_btn_frame = tk.Frame(clock_frame)
                clock_btn_frame.pack(fill='x', padx=2)
                
                self.clock_toggle_button = tk.Button(clock_btn_frame,
                                                     text='Enable',
                                                     command=self.toggle_clock,
                                                     font=('Arial', 8))
                self.clock_toggle_button.pack(side='left', fill='x', expand=True)
                
                tk.Button(clock_btn_frame, text='Reset', command=self.reset_clock,
                         font=('Arial', 8)).pack(side='left', padx=1)
                
                # Start updating clock display
                self.update_clock_display()
            
            # Statistics display - more compact
            if self.config:
                stats_frame = tk.LabelFrame(files_page, text='Stats', font=('Arial', 9, 'bold'))
                stats_frame.pack(fill='x', pady=2, padx=2)
                
                stats = self.config.get('statistics', {})
                games = stats.get('games_played', 0)
                white_wins = stats.get('white_wins', 0)
                black_wins = stats.get('black_wins', 0)
                draws = stats.get('draws', 0)
                
                stats_text = f"Games: {games}\nW: {white_wins} | B: {black_wins} | D: {draws}"
                self.stats_label = tk.Label(stats_frame, text=stats_text, justify='left', font=('Arial', 8))
                self.stats_label.pack(padx=2, pady=2)

        # Learning panel
        learn_frame = tk.LabelFrame(learning_page, text='Learning', font=('Arial', 9, 'bold'))
        learn_frame.pack(fill='x', pady=2, padx=2)
        self.learn_use_var = tk.BooleanVar(master=self.master, value=True)
        def toggle_learning():
            try:
                self.ai.use_learning = bool(self.learn_use_var.get())
            except Exception:
                pass
        tk.Checkbutton(learn_frame, text='Use Learning Bias', variable=self.learn_use_var,
                       command=toggle_learning, font=('Arial', 8)).pack(anchor='w', padx=2)
        btns = tk.Frame(learn_frame)
        btns.pack(fill='x', padx=2, pady=2)
        tk.Button(btns, text='Show Position', command=self.show_learning_for_position,
                  font=('Arial', 8)).pack(side='left', padx=1)
        tk.Button(btns, text='Export', command=self.export_learning,
                  font=('Arial', 8)).pack(side='left', padx=1)
        tk.Button(btns, text='Import', command=self.import_learning,
                  font=('Arial', 8)).pack(side='left', padx=1)
        tk.Button(btns, text='Reset', command=self.reset_learning,
                  font=('Arial', 8)).pack(side='left', padx=1)

        # Engine frame - more compact
        engine_frame = tk.LabelFrame(tools_page, text='Engine (Advanced)', font=('Arial', 9, 'bold'))
        engine_frame.pack(fill='x', pady=2, padx=2)
        self.engine_frame = engine_frame
        self.engine_path_var = tk.StringVar(master=self.master)
        self.engine_path_var.set(shutil.which('stockfish') or '')
        tk.Entry(engine_frame, textvariable=self.engine_path_var, width=22, font=('Arial', 8)).pack(padx=2, pady=1)
        
        engine_btn_frame = tk.Frame(engine_frame)
        engine_btn_frame.pack(fill='x', padx=2)
        self.detect_button = tk.Button(engine_btn_frame, text='Detect', command=self.detect_engine, font=('Arial', 8))
        self.detect_button.pack(side='left', fill='x', expand=True, padx=1)
        self.download_button = tk.Button(engine_btn_frame, text='Download', command=self.download_engine, font=('Arial', 8))
        self.download_button.pack(side='left', fill='x', expand=True, padx=1)
        self.verify_button = tk.Button(engine_btn_frame, text='Verify', command=self.verify_engine, font=('Arial', 8))
        self.verify_button.pack(side='left', fill='x', expand=True, padx=1)
        
        # Engine settings - simple defaults
        self.platform_var = tk.StringVar(master=self.master, value='auto')
        self.github_token = tk.StringVar(master=self.master)
        self.verify_retries = tk.IntVar(master=self.master, value=2)
        self.verify_timeout = tk.DoubleVar(master=self.master, value=0.05)
        self.backoff_var = tk.StringVar(master=self.master, value='linear')
        self.backoff_max = tk.DoubleVar(master=self.master, value=5.0)
        self.auto_download_var = tk.BooleanVar(master=self.master, value=False)
        self.verify_log = tk.Listbox(tools_page, width=22, height=4, font=('Arial', 7))
        
        self.engine_toggle = tk.Button(engine_frame, text='Use Engine: Off', command=self.toggle_engine, font=('Arial', 8))
        self.engine_toggle.pack(fill='x', pady=1, padx=2)

        # Batch PGN Converter frame
        converter_frame = tk.LabelFrame(tools_page, text='Batch PGN Converter', font=('Arial', 9, 'bold'))
        converter_frame.pack(fill='x', pady=2, padx=2)
        self.converter_format_var = tk.StringVar(master=self.master, value='json')
        self.converter_input_dir_var = tk.StringVar(master=self.master, value='')
        self.converter_output_dir_var = tk.StringVar(master=self.master, value='')
        self.converter_status_var = tk.StringVar(master=self.master, value='Idle')
        tk.Label(converter_frame, text='Format:', font=('Arial', 8)).pack(anchor='w', padx=2)
        fmt_menu = tk.OptionMenu(converter_frame, self.converter_format_var, 'json', 'summary', 'csv', 'minimal')
        fmt_menu.config(font=('Arial', 8))
        fmt_menu.pack(fill='x', padx=2)
        dir_btn_row = tk.Frame(converter_frame)
        dir_btn_row.pack(fill='x', padx=2, pady=1)
        tk.Button(dir_btn_row, text='Input Dir…', command=self.open_batch_converter_input_dir, font=('Arial', 8)).pack(side='left', padx=1)
        tk.Button(dir_btn_row, text='Output Dir…', command=self.open_batch_converter_output_dir, font=('Arial', 8)).pack(side='left', padx=1)
        tk.Button(converter_frame, text='Run Conversion', command=self.start_batch_conversion, font=('Arial', 8, 'bold')).pack(fill='x', padx=2, pady=3)
        tk.Label(converter_frame, textvariable=self.converter_status_var, font=('Arial', 8), fg='#333').pack(anchor='w', padx=2, pady=1)

        comparison = tk.LabelFrame(compare_page, text='Compare learning against a fixed baseline')
        comparison.pack(fill='x')
        tk.Label(comparison, text='The saved AI plays an identical AI without move memory. '
                 'Each opening is played twice with colors swapped. Search budgets are equal.',
                 wraplength=380, justify='left').pack(fill='x', pady=8)
        self.benchmark_games_var = tk.IntVar(master=self.master, value=20)
        self.benchmark_nodes_var = tk.IntVar(master=self.master, value=500)
        for label, variable in (('Games (even number)', self.benchmark_games_var),
                                 ('Search nodes per move', self.benchmark_nodes_var)):
            row = tk.Frame(comparison)
            row.pack(fill='x', pady=4)
            tk.Label(row, text=label).pack(side='left')
            tk.Entry(row, textvariable=variable, width=8).pack(side='right')
        row = tk.Frame(comparison)
        row.pack(fill='x', pady=8)
        tk.Button(row, text='Run comparison', command=self.start_benchmark).pack(side='left')
        tk.Button(row, text='Cancel', command=self.stop_benchmark).pack(side='right')
        self.experimental_scoring_var = tk.BooleanVar(master=self.master, value=False)
        tk.Checkbutton(comparison, text='Test confidence-weighted scoring (experimental)',
                       variable=self.experimental_scoring_var).pack(anchor='w')
        tk.Button(comparison, text='Enable only if evidence supports it',
                  command=self._approve_outcome_scoring).pack(fill='x', pady=4)
        self.benchmark_var = tk.StringVar(master=self.master, value='No comparison yet. Small samples do not establish a strength rating.')
        tk.Label(comparison, textvariable=self.benchmark_var, wraplength=380,
                 justify='left').pack(fill='x', pady=8)
        tk.Label(compare_page, text='Score = wins + half of draws. Move-limit draws are reported separately. '
                 'These results measure this comparison, not Elo or a guaranteed improvement.',
                 wraplength=380, justify='left').pack(fill='x', pady=12)
        self._load_benchmark_result()
        self._build_studio_features(accessibility_page)
        self._build_tools_menu(header)

        self.load_piece_images()
        self.load_overlay_icons()

        # Finalize styles after every control exists.
        self.apply_theme_to_ui(self.theme_var.get())
        self.update_board()
        self._restore_session()
        for problem in (getattr(self.ai, 'load_error', None), getattr(self.config, 'load_error', None)):
            if problem:
                self.feedback_var.set(problem)
        self.master.after(80, self._poll_ui_queue)
        master.protocol('WM_DELETE_WINDOW', self.on_close)

    # ---- UI callbacks and helpers (moved from previous main.py ChessGUI) ----
    def on_click(self, square):
        if getattr(self, '_tools_busy', False):
            return
        if self._activity == 'practice':
            return self._practice_click(square)
        if self._activity == 'review':
            return
        if self.training_ai and self.training_ai.running:
            self.feedback_var.set('Stop and save training before playing.')
            return
        # Prevent moves while AI is thinking
        if self.ai_thinking:
            return
        # In AI vs AI mode, ignore manual input
        if self.play_mode == 'ai_vs_ai':
            return
        # In training AI mode, ignore manual input
        if self.play_mode == 'training_ai':
            return
        # In player vs AI mode, only allow moves if game has started
        if self.play_mode == 'player_vs_ai' and not self.game_started:
            return
        if self._is_ai_turn() or self._timed_out:
            return
        if self.board.is_game_over(claim_draw=True):
            return
        piece = self.board.piece_at(square)
        if self.selected is None:
            if piece is None:
                return
            if piece.color != self.board.turn:
                return
            self.selected = square
            self.board_view.show_legal_moves(self.board, square)
            self.board_view.highlight(square)
        else:
            move = None
            sel_piece = self.board.piece_at(self.selected)
            promotes = False
            if sel_piece is not None and sel_piece.piece_type == chess.PAWN:
                r = chess.square_rank(square)
                if (sel_piece.color == chess.WHITE and r == 7) or (sel_piece.color == chess.BLACK and r == 0):
                    promotes = True
            if promotes and chess.Move(self.selected, square, promotion=chess.QUEEN) not in self.board.pseudo_legal_moves:
                promotes = False
            if promotes:
                assert sel_piece is not None
                promo = self.ask_promotion(sel_piece.color)
                if promo is None:
                    self.selected = None
                    self.update_board()
                    return
                move = chess.Move(self.selected, square, promotion=promo)
            else:
                move = chess.Move(self.selected, square)
            if move in self.board.legal_moves:
                # Determine move type for sound effects
                is_capture = self.board.is_capture(move)
                is_castle = sel_piece is not None and sel_piece.piece_type == chess.KING and abs(chess.square_file(self.selected) - chess.square_file(square)) == 2
                
                # Make the move
                self.board.push(move)
                self.move_history.append(move)
                
                # Store move for statistics
                if self.config:
                    self.config.increment_move_count()
                
                # Update clock
                if self.clock and self.clock_enabled and self.clock.is_running():
                    self.clock.switch()
                
                # Play sound effects
                if self.sound:
                    if self.board.is_checkmate():
                        self.sound.play('checkmate')
                    elif self.board.is_check():
                        self.sound.play('check')
                    elif is_castle:
                        self.sound.play('castle')
                    elif is_capture:
                        self.sound.play('capture')
                    else:
                        self.sound.play('move')
                
                self.selected = None
                self.board_view.clear_highlights()
                self.update_board()
                
                self.feedback_var.set('Your move is on the board.')
                if not self.board.is_game_over(claim_draw=True) and self.game_started and self._is_ai_turn():
                    self._launch_ai_thread(max(1, self.depth_var.get()))
            else:
                self.feedback_var.set(illegal_move_message(self.board, move))
                if piece is not None and piece.color == self.board.turn:
                    self.selected = square
                    self.update_board(force=True)
                    self.board_view.show_legal_moves(self.board, square)
                    self.board_view.highlight(square)

    def _human_color(self):
        return chess.BLACK if self.player_color_var.get() == 'Black' else chess.WHITE

    def _is_ai_turn(self):
        return self.play_mode == 'ai_vs_ai' or (
            self.play_mode == 'player_vs_ai' and self.board.turn != self._human_color())

    def _choose_mode(self, event=None):
        self._return_to_game()
        modes = {'Play AI': 'player_vs_ai', 'Two players': 'player_vs_player', 'Watch AI': 'ai_vs_ai'}
        self.mode_var.set(modes[self.mode_display_var.get()])
        self.change_mode()

    def _choose_difficulty(self, event=None):
        depth, milliseconds = {'Beginner': (1, 100), 'Easy': (2, 250),
                               'Medium': (3, 500), 'Hard': (4, 1200)}[self.difficulty_var.get()]
        self.depth_var.set(depth)
        self.gui_move_time_var.set(milliseconds)
        self.on_depth_change(depth)
        self.on_gui_move_time_change()

    def _choose_side(self, event=None):
        self.new_game()
        flip = self._human_color() == chess.BLACK
        if self.board_view.flipped != flip:
            self.board_view.flip_board()
        self.update_board(force=True)

    def _cancel_search(self):
        self._ai_session_id += 1
        self.ai_thinking = False
        self._hint_thinking = False
        self._ai_started_at = None
        self.master.configure(cursor='')

    def _post_ui(self, callback, *args):
        # Workers never call Tk, even to schedule an after callback.
        if not self._closed:
            self._ui_queue.put((callback, args))

    def _poll_ui_queue(self):
        if self._closed:
            return
        for _ in range(30):
            try:
                callback, args = self._ui_queue.get_nowait()
            except queue.Empty:
                break
            callback(*args)
        if self.ai_thinking and self._ai_started_at:
            elapsed = time.monotonic() - self._ai_started_at
            self.status.configure(text=f'AI thinking… {elapsed:.1f}s')
        self._feature_tick()
        self._poll_training_status()
        if self.benchmark is not None:
            self._show_benchmark(self.benchmark.result)
        self.master.after(80, self._poll_ui_queue)

    def run_ai_move(self, depth=None, snapshot=None):
        # Direct calls are synchronous for tooling/tests. GUI launches pass a frozen snapshot.
        direct = snapshot is None
        if direct:
            snapshot = (self._ai_session_id, self.board.copy(), self.ai.fork(),
                        int(depth or self.depth_var.get()), float(self.gui_move_time_var.get()) / 1000,
                        self.engine_enabled and self.engine_adapter.is_running())
        session, board, ai, depth, budget, use_engine = snapshot
        ai.depth = max(1, depth)
        started = time.monotonic()
        try:
            move = self.engine_adapter.play_move(board, budget) if use_engine else None
            if move is not None:
                metrics = {'move': move.uci(), 'source': 'engine', 'depth': depth,
                           'nodes': None, 'branching': board.legal_moves.count(),
                           'time': time.monotonic() - started}
            else:
                move = ai.choose_move_iterative(board, max(0.01, budget), record=False)
                metrics = dict(ai.last_move_metrics)
            result = (session, board.fen(), move, metrics, None)
        except Exception as exc:
            result = (session, board.fen(), None, {}, str(exc))
        if direct:
            self._accept_ai_move(*result)
        else:
            self._post_ui(self._accept_ai_move, *result)

    def _accept_ai_move(self, session, fen, move, metrics, error):
        if session != self._ai_session_id or fen != self.board.fen():
            return
        self.ai_thinking = False
        self._ai_started_at = None
        self.master.configure(cursor='')
        if error or move is None or move not in self.board.legal_moves:
            self.feedback_var.set(f'AI could not move: {error or "no legal move returned"}')
            self.game_started = False
            self._update_start_pause_button()
            return
        san = self.board.san(move)
        self.ai._log_choice(position_key(self.board), move.uci(), self.board.turn)
        self.board.push(move)
        self.move_history.append(move)
        if self.config:
            self.config.increment_move_count()
        self.ai.last_move_metrics = metrics
        self.metrics_history = getattr(self, 'metrics_history', []) + [metrics]
        self.feedback_var.set(f'AI played {san} in {metrics.get("time", 0):.2f}s.')
        if self.clock and self.clock_enabled and self.clock.is_running():
            self.clock.switch()
        self.update_board(force=True)
        self.metrics_var.set(f'{san}: depth {metrics.get("depth", 0)}, '
                             f'{metrics.get("nodes", 0)} nodes, {metrics.get("source", "AI")}')
        if self.play_mode == 'ai_vs_ai' and self.game_started and not self.board.is_game_over(claim_draw=True):
            token = self._ai_session_id
            delay = max(40, int(self.ai_delay_var.get()))
            self.master.after(delay, lambda: self._launch_ai_thread() if (
                token == self._ai_session_id and self.game_started) else None)

    def _launch_ai_thread(self, depth=None):
        if self.ai_thinking or self._closed or self.board.is_game_over(claim_draw=True):
            return
        self.ai_thinking = True
        self._ai_started_at = time.monotonic()
        self.status.configure(text='AI thinking… 0.0s')
        snapshot = (self._ai_session_id, self.board.copy(), self.ai.fork(),
                    max(1, int(depth or self.depth_var.get())),
                    max(0.01, int(self.gui_move_time_var.get()) / 1000),
                    self.engine_enabled and self.engine_adapter.is_running())
        threading.Thread(target=self.run_ai_move, kwargs={'snapshot': snapshot}, daemon=True).start()

    def _finish_ai_move(self):
        self.ai_thinking = False
        self.update_board(force=True)

    def request_hint(self):
        if self._activity == 'practice':
            return self._practice_hint()
        if self._activity == 'review':
            return self._analyze_review()
        if self.ai_thinking or self._hint_thinking or self.board.is_game_over(claim_draw=True):
            return
        self._hint_thinking = True
        session, board, ai = self._ai_session_id, self.board.copy(), self.ai.fork()
        ai.depth = max(2, int(self.depth_var.get()))
        self.feedback_var.set('Finding a hint…')
        def work():
            try:
                move = ai.choose_move_iterative(board, 0.5, record=False)
                text = describe_move(board, move) if move else 'No legal moves.'
            except Exception as exc:
                move, text = None, f'Hint unavailable: {exc}'
            self._post_ui(self._accept_hint, session, board.fen(), move, text)
        threading.Thread(target=work, daemon=True).start()

    def _accept_hint(self, session, fen, move, text):
        if session != self._ai_session_id:
            return
        self._hint_thinking = False
        if fen != self.board.fen():
            return
        self.feedback_var.set(text)
        if move:
            self.board_view.clear_highlights()
            self.board_view.highlight(move.from_square)
            self.board_view.highlight(move.to_square)

    def export_metrics_csv(self):
        """Export collected metrics history to a CSV file chosen by user."""
        if not hasattr(self, 'metrics_history') or not self.metrics_history:
            messagebox.showinfo('Metrics', 'No metrics collected yet.')
            return
        path = filedialog.asksaveasfilename(defaultextension='.csv', filetypes=[('CSV','*.csv')], title='Save Metrics CSV')
        if not path:
            return
        try:
            keys = ['move','depth','nodes','branching','time','source']
            with open(path, 'w', newline='', encoding='utf-8') as f:
                w = csv.writer(f)
                w.writerow(keys)
                for m in self.metrics_history:
                    w.writerow([m.get(k) for k in keys])
            messagebox.showinfo('Metrics', f'Metrics exported to {path}')
        except Exception as e:
            messagebox.showerror('Metrics', f'Failed to export metrics: {e}')

    def update_board(self, force=False):
        # render pieces and move list
        try:
            self.board_view.highlight_last_move(self.board.peek() if self.board.move_stack else None)
            self.board_view.update(self.board, self.piece_images)
            self.board_view.apply_special_overlays(self.board, self.overlay_icons)
        except Exception:
            pass
        
        # If player is in check, show all legal moves to escape using fixed board highlight colors
        if self.board.is_check() and not self.ai_thinking:
            from constants import CAPTURE_COLOR, LEGAL_MOVE_COLOR

            # Highlight king in check with fixed capture color
            king_square = self.board.king(self.board.turn)
            if king_square is not None:
                try:
                    self.board_view.canvases[king_square].configure(bg=CAPTURE_COLOR)
                except Exception:
                    pass

            # Show all legal moves that get out of check with fixed legal move color
            try:
                for move in self.board.legal_moves:
                    to_square = move.to_square
                    canvas = self.board_view.canvases.get(to_square)
                    if canvas:
                        canvas.configure(bg=LEGAL_MOVE_COLOR)
            except Exception:
                pass
        
        moves_key = (self.board.root().fen(), tuple(self.board.move_stack))
        if moves_key != self._rendered_moves:
            self._rendered_moves = moves_key
            self.move_list.delete(0, tk.END)
            b = self.board.root()
            lines = []
            for mv in self.board.move_stack:
                san = b.san(mv)
                if b.turn == chess.WHITE:
                    lines.append(f'{b.fullmove_number}. {san}')
                elif lines:
                    lines[-1] += f' {san}'
                else:
                    lines.append(f'{b.fullmove_number}… {san}')
                b.push(mv)
            for line in lines:
                self.move_list.insert(tk.END, line)
            self.move_list.see(tk.END)
        outcome = self.board.outcome(claim_draw=True)
        game_over_now = outcome is not None
        if self._timed_out:
            self.status.configure(text="Game ended on time. Press New for another game.")
        elif outcome:
            if outcome.winner is not None:
                winner = 'White' if outcome.winner == chess.WHITE else 'Black'
                self.status.configure(text=f'Checkmate — {winner} wins')
            else:
                reason = outcome.termination.name.replace('_', ' ').lower()
                self.status.configure(text=f'Draw — {reason}')
        else:
            turn = 'White' if self.board.turn == chess.WHITE else 'Black'
            self.status.configure(text=f'{turn} to move' + (' — CHECK!' if self.board.is_check() else ''))
        try:
            hints = self._special_hints()
            self.hints_label.configure(text=hints)
        except Exception:
            try:
                self.hints_label.configure(text='')
            except Exception:
                pass
        self.update_controls_state()

        if self._activity != 'game':
            return
        self._save_session()
        # If the game just ended, finalize AI learning once
        try:
            if game_over_now and hasattr(self, 'ai') and self.ai:
                if not getattr(self, '_learn_finalized', False):
                    result = 'draw'
                    if self.board.is_checkmate():
                        # If it's checkmate, current turn is the side that cannot move (was mated)
                        result = 'black' if self.board.turn == chess.WHITE else 'white'
                    self._finished_log = list(self.ai.game_log)
                    self._finished_learning_backup = {
                        key + '|' + move: copy.deepcopy(self.ai.learning_db.get(key + '|' + move))
                        for key, move, _ in self.ai.game_log}
                    self._finished_stats_backup = copy.deepcopy(self.config.get('statistics', {})) if self.config else None
                    self.ai.finalize_game(result)
                    if self.config:
                        self.config.update_statistics(result)
                    self._learn_finalized = True
                    # Auto-save PGN if enabled
                    try:
                        if bool(self.autosave_pgn_var.get() if hasattr(self, 'autosave_pgn_var') else False) and not getattr(self, '_autosave_done', False):
                            self.autosave_pgn(result)
                            self._autosave_done = True
                    except Exception:
                        pass
                    # Auto-restart for AI vs AI if enabled
                    try:
                        if self.play_mode == 'ai_vs_ai' and bool(self.auto_restart_var.get() if hasattr(self, 'auto_restart_var') else False):
                            if not self._auto_restart_scheduled:
                                self._auto_restart_scheduled = True
                                # Give a brief pause to let user see result
                                self.master.after(1000, self._auto_restart_ai_game)
                    except Exception:
                        pass
            elif not game_over_now:
                # Reset flag during ongoing games
                self._learn_finalized = False
                self._auto_restart_scheduled = False
        except Exception:
            pass

    def new_game(self) -> None:
        if getattr(self, '_tools_busy', False):
            return
        """Start a fresh game, clearing the board and state."""
        try:
            self._return_to_game()
            # Increment session to abort any in-flight AI moves
            self._cancel_search()
            self.ai.game_log = []
            self._finished_learning_backup = None
            self._finished_log = None
            self._finished_stats_backup = None
            self._timed_out = False
            if self.clock:
                self.reset_clock()
            # Reset board/state
            self.board = chess.Board()
            self.selected = None
            self.move_history = []
            self.ai_last_explanation = ''
            # Reset learning finalize flag
            self._learn_finalized = False
            # Reset autosave flag
            self._autosave_done = False
            # Stop the game - require Start button press
            self.game_started = False
            self._update_start_pause_button()
            self.update_board(force=True)
        except Exception as e:
            messagebox.showerror('New Game', f'Failed to start new game: {e}')

    def restart_game(self) -> None:
        """Restart the current game (alias of New Game), preserving mode and settings."""
        self.new_game()

    def _auto_restart_ai_game(self) -> None:
        """Internal: auto-restart a new AI vs AI game after a conclusion."""
        try:
            # Ensure still in AI vs AI and auto-restart still requested
            if self.play_mode != 'ai_vs_ai' or not (self.auto_restart_var.get() if hasattr(self, 'auto_restart_var') else False):
                self._auto_restart_scheduled = False
                return
            self._auto_restart_scheduled = False
            self.new_game()
            # Auto-start the game for AI vs AI
            self.game_started = True
            self._update_start_pause_button()
            if not self.board.is_game_over():
                self._launch_ai_thread()
        except Exception:
            self._auto_restart_scheduled = False

    def on_clock_timeout(self, is_white: bool) -> None:
        """Handle chess clock timeout."""
        self._cancel_search()
        self._timed_out = True
        self.game_started = False
        self._update_start_pause_button()
        winner = "Black" if is_white else "White"
        self.status.configure(text=f"Time's up! {winner} wins on time")
        messagebox.showinfo("Time's Up!", f"{winner} wins on time!")
        if self.config:
            result = 'black' if is_white else 'white'
            self.config.update_statistics(result)
    
    def flip_board(self) -> None:
        """Flip the board orientation."""
        try:
            if hasattr(self.board_view, 'flip_board'):
                self.board_view.flip_board()  # type: ignore
                if self.config:
                    self.config.set('board_flipped', not self.config.get('board_flipped', False))
            self.update_board()
        except Exception as e:
            print(f"Board flip not supported: {e}")
    
    def change_theme(self, theme: str) -> None:
        """Change the color theme."""
        try:
            # Keep board visuals constant; if BoardView supports set_theme, it may still use it for labels, etc.
            if hasattr(self.board_view, 'set_theme'):
                self.board_view.set_theme(theme)  # type: ignore
            if self.config:
                self.config.set('theme', theme)
            # Apply background/foreground styles to UI, not the board squares
            self.apply_theme_to_ui(theme)
            self.update_board()
        except Exception as e:
            print(f"Theme change not supported: {e}")

    def _schedule_board_resize(self, event=None):
        if self._board_resize_job is not None:
            self.master.after_cancel(self._board_resize_job)
        self._board_resize_job = self.master.after(40, self._resize_board)

    def _resize_board(self):
        self._board_resize_job = None
        edge = max(160, min(self.board_area.winfo_width(), self.board_area.winfo_height()))
        # Include coordinate labels while preserving perfectly square cells.
        square_size = max(16, (edge - 24) // 8)
        self.board_view.parent.place_configure(width=square_size * 8 + 24,
                                              height=square_size * 8 + 24)
        self.board_view.resize(square_size)
        if self.selected is not None:
            self.board_view.show_legal_moves(self.board, self.selected)
            self.board_view.highlight(self.selected)

    def apply_theme_to_ui(self, theme):
        body_size = round(9 * self.text_scale)
        dark = theme == 'dark'
        bg, card, fg, muted = ('#17212f', '#223044', '#edf3fa', '#aebed0') if dark else (
            '#edf2f7', '#ffffff', '#172b44', '#52657c')
        accent = '#2563eb'
        self.master.configure(bg=bg)
        style = ttk.Style(self.master)
        style.theme_use('clam')
        style.configure('TNotebook', background=bg, borderwidth=0)
        style.configure('TNotebook.Tab', padding=(8, 8), font=(self.ui_font, min(11, body_size)),
                        background=bg, foreground=muted)
        style.map('TNotebook.Tab', background=[('selected', card)],
                  foreground=[('selected', accent)])

        def decorate(widget):
            # Board canvases and coordinate labels have their own rendering.
            if widget is self.board_area:
                widget.configure(bg=bg)
                return
            kind = widget.winfo_class()
            try:
                if kind in ('Frame', 'Labelframe'):
                    widget.configure(bg=card, bd=0)
                    if kind == 'Labelframe':
                        widget.configure(fg=muted, font=(self.ui_font, body_size + 1, 'bold'),
                                         padx=8, pady=6)
                elif kind == 'Label':
                    widget.configure(bg=card, fg=fg, font=(self.ui_font, body_size))
                elif kind == 'Button':
                    widget.configure(bg='#e7eef9' if not dark else '#334860', fg=fg,
                                     activebackground=accent, activeforeground='white',
                                     relief='flat', bd=0, padx=9, pady=6,
                                     font=(self.ui_font, body_size), cursor='hand2')
                elif kind in ('Checkbutton', 'Radiobutton'):
                    widget.configure(bg=card, fg=fg, activebackground=card,
                                     activeforeground=fg, selectcolor=card,
                                     font=(self.ui_font, body_size), highlightthickness=0)
                elif kind == 'TCombobox':
                    widget.configure(font=(self.ui_font, body_size))
                elif kind == 'Scale':
                    widget.configure(bg=card, fg=fg, highlightthickness=0,
                                     troughcolor=bg, bd=0)
                elif kind in ('Entry', 'Listbox'):
                    widget.configure(bg=bg, fg=fg, relief='flat', bd=0,
                                     highlightthickness=1, highlightbackground=bg,
                                     selectbackground=accent, selectforeground='white',
                                     font=(self.ui_font, 10))
            except tk.TclError:
                pass
            for child in widget.winfo_children():
                decorate(child)
        for child in self.master.winfo_children():
            decorate(child)
        self.title_label.configure(font=(self.ui_font, 19, 'bold'))
        self.status.configure(bg=bg, fg=fg, font=(self.ui_font, 12, 'bold'))
        self.hints_label.configure(bg=bg, fg=muted)
        self.start_pause_button.configure(bg=accent, fg='white')
        if hasattr(self, 'white_clock_label'):
            self.white_clock_label.configure(bg=bg, fg=fg)
            self.black_clock_label.configure(bg=bg, fg=fg)

    def change_mode(self):
        self._cancel_search()
        self.play_mode = self.mode_var.get()
        self.game_started = False
        if self.training_ai and self.training_ai.running:
            self.stop_training_ai()
        self._update_start_pause_button()
        self.update_board(force=True)
        if self.play_mode == 'training_ai':
            self.controls_notebook.select(self.control_pages[1])

    def toggle_game_started(self):
        if getattr(self, '_tools_busy', False):
            return
        self._return_to_game()
        if self.play_mode == 'training_ai':
            return self.stop_training_ai() if self.game_started else self.start_training_ai()
        if self.training_ai and self.training_ai.running:
            self.feedback_var.set('Stop and save training before playing.')
            return
        if self.board.is_game_over(claim_draw=True) or self._timed_out:
            self.new_game()
        self.game_started = not self.game_started
        if not self.game_started:
            self._cancel_search()
            if self.clock:
                self.clock.stop()
        else:
            if self.clock and self.clock_enabled:
                self.clock.start(self.master, self.board.turn == chess.WHITE)
            if self._is_ai_turn():
                self._launch_ai_thread()
        self._update_start_pause_button()

    def _update_start_pause_button(self) -> None:
        """Update the Start/Pause button appearance based on game state."""
        if hasattr(self, 'start_pause_button'):
            if self.game_started:
                self.start_pause_button.config(text='Pause', bg='#ff9800')
            else:
                self.start_pause_button.config(text='Play', bg='#4CAF50')

    def on_gui_move_time_change(self) -> None:
        try:
            if self.config and hasattr(self, 'gui_move_time_var'):
                self.config.set('gui_move_time_ms', int(self.gui_move_time_var.get()))
        except Exception:
            pass
    
    def toggle_sound(self) -> None:
        """Toggle sound effects on/off."""
        if self.sound:
            enabled = self.sound.toggle()
            if hasattr(self, 'sound_button'):
                self.sound_button.config(text=f"Sound: {'On' if enabled else 'Off'}")
            if self.config:
                self.config.set('sound_enabled', enabled)
    
    def toggle_clock(self) -> None:
        """Toggle chess clock on/off."""
        if not self.clock:
            return
        
        self.clock_enabled = not self.clock_enabled
        
        if self.clock_enabled:
            # Start the clock for current player
            self.clock.start(self.master, self.board.turn == chess.WHITE)
            self.clock_toggle_button.config(text='Disable Clock')
        else:
            self.clock.stop()
            self.clock_toggle_button.config(text='Enable Clock')
        
        if self.config:
            self.config.set('clock_enabled', self.clock_enabled)

    def on_toggle_compress(self) -> None:
        """Toggle gzip compression for learning data."""
        try:
            if hasattr(self, 'ai') and self.ai:
                val = bool(self.compress_learning_var.get())
                self.ai.compress_learning = val
                if self.config:
                    self.config.set('compress_learning', val)
        except Exception:
            pass

    def _training_cli_args(self):
        args = training_command() + ['--training',
                '--depth', str(int(self.depth_var.get())), '--batch-size', str(int(self.training_batch_size_var.get())),
                '--move-ms', str(int(self.training_move_time_var.get())),
                '--games', str(int(self.training_games_var.get())),
                '--snapshot-batches', str(int(self.training_snapshot_interval_var.get())),
                '--exploration', str(float(self.exploration_var.get())),
                '--learning-file', os.path.abspath(self.ai._learning_path)]
        if not self.varied_starts_var.get():
            args.append('--no-varied-starts')
        if not self.compress_learning_var.get():
            args.append('--no-compress')
        return args

    def _build_training_cli(self):
        import shlex
        import subprocess
        args = self._training_cli_args()
        return subprocess.list2cmdline(args) if os.name == 'nt' else shlex.join(args)

    def copy_training_command(self):
        self.master.clipboard_clear()
        self.master.clipboard_append(self._build_training_cli())
        messagebox.showinfo('Training', 'Training command copied to clipboard.')

    def run_training_now(self):
        import subprocess
        if self.training_ai and self.training_ai.running:
            messagebox.showinfo('Training', 'Stop and save the current trainer first.')
            return
        try:
            subprocess.Popen(self._training_cli_args(), cwd=os.fspath(data_dir()),
                             creationflags=getattr(subprocess, 'CREATE_NEW_CONSOLE', 0) if os.name == 'nt' else 0)
        except (OSError, ValueError) as exc:
            messagebox.showerror('Training', f'Cannot launch training: {exc}')

    def reset_training_defaults(self) -> None:
        """Restore training and compression defaults and persist them."""
        try:
            # Defaults
            default_batch = 100
            default_move_ms = 250
            default_snap = 0
            default_compress = True
            # Update UI vars
            self.training_batch_size_var.set(default_batch)
            self.training_move_time_var.set(default_move_ms)
            self.training_snapshot_interval_var.set(default_snap)
            self.compress_learning_var.set(default_compress)
            # Apply compression immediately
            self.on_toggle_compress()
            # Persist training settings
            if self.config:
                self.config.set('training_batch_size', default_batch)
                self.config.set('training_move_time_ms', default_move_ms)
                self.config.set('training_snapshot_batches', default_snap)
        except Exception:
            pass

    # ---- Learning controls ----
    def reset_learning(self) -> None:
        if self.training_ai and self.training_ai.running:
            messagebox.showinfo('Training', 'Stop and save training before resetting learning.')
            return
        try:
            if hasattr(self, 'ai') and self.ai:
                self.ai.learning_db = {}
                self.ai.game_log = []
                # Overwrite file
                try:
                    with open(self.ai._learning_path, 'w', encoding='utf-8') as f:
                        f.write('{}')
                except Exception:
                    pass
                messagebox.showinfo('Learning', 'Learning data has been reset.')
        except Exception as e:
            messagebox.showerror('Learning', f'Failed to reset: {e}')

    def export_learning(self) -> None:
        try:
            if not hasattr(self, 'ai') or not self.ai:
                return
            path = filedialog.asksaveasfilename(defaultextension='.json', initialfile='ai_learn_readable.json',
                                                filetypes=[('JSON files', '*.json')])
            if not path:
                return
            out = self.ai.export_readable_learning(path)
            if out:
                messagebox.showinfo('Learning', f'Exported readable learning to:\n{out}')
            else:
                messagebox.showerror('Learning', 'Failed to export learning.')
        except Exception as e:
            messagebox.showerror('Learning', f'Failed to export: {e}')

    def import_learning(self) -> None:
        if not self._tools_idle():
            return
        try:
            from data_validation import read_json, learning_records
            path = filedialog.askopenfilename(filetypes=[('Learning JSON', '*.json *.json.gz')])
            if not path:
                return
            records = learning_records(read_json(path))
            candidate = copy.deepcopy(self.ai.learning_db)
            for key, counts in records.items():
                old = candidate.setdefault(key, {'w': 0, 'l': 0, 'd': 0})
                for name in ('w', 'l', 'd'):
                    old[name] += counts[name]
            learning_records(candidate)  # Validate merged limits too.
            old, scoring = self.ai.learning_db, self.ai.use_outcome_scoring
            self.ai.learning_db, self.ai.use_outcome_scoring = candidate, False
            try:
                self.ai._save_learning_db()
            except Exception:
                self.ai.learning_db, self.ai.use_outcome_scoring = old, scoring
                raise
            messagebox.showinfo('Learning', f'Merged {len(records)} entries. Outcome scoring reset to off.')
        except Exception as exc:
            self._tool_error('Import failed', exc)

    def show_learning_for_position(self) -> None:
        try:
            if not hasattr(self, 'ai') or not self.ai:
                return
            fen_key = position_key(self.board)
            # Collect moves
            rows = []
            for mv in self.board.legal_moves:
                u = mv.uci()
                rec = self.ai.learning_db.get(fen_key + '|' + u)
                w = rec.get('w', 0) if rec else 0
                l = rec.get('l', 0) if rec else 0
                d = rec.get('d', 0) if rec else 0
                games = w + l + d
                winrate = 0.0 if games == 0 else (w + 0.5 * d) / games
                bonus = int((winrate - 0.5) * 200)
                rows.append((u, games, winrate, w, l, d, bonus))
            rows.sort(key=lambda r: (r[2], r[1]), reverse=True)
            # Show in a small dialog
            dlg = tk.Toplevel(self.master)
            dlg.title('Learning — Current Position')
            dlg.transient(self.master)
            dlg.grab_set()
            header = tk.Label(dlg, text='Move   Games   Winrate   W  L  D   Ordering bonus', font=('Arial', 9, 'bold'))
            header.pack(padx=8, pady=4)
            box = tk.Listbox(dlg, width=50, height=10, font=('Arial', 9))
            box.pack(padx=8, pady=4)
            if not rows:
                box.insert(tk.END, 'No learning yet for this position.')
            else:
                for (u, games, wr, w, l, d, bonus) in rows[:20]:
                    box.insert(tk.END, f'{u:6}  {games:5}   {wr:7.3f}   {w:2} {l:2} {d:2}   {bonus:+d}')
            tk.Button(dlg, text='Close', command=dlg.destroy, font=('Arial', 8)).pack(pady=6)
        except Exception as e:
            messagebox.showerror('Learning', f'Failed to show learning: {e}')
    
    def reset_clock(self) -> None:
        """Reset chess clock to initial time."""
        if not self.clock or not self.config:
            return
        
        clock_time = self.config.get('clock_time', 600)
        self.clock.reset(clock_time, clock_time)
        self.update_clock_display()
    
    def update_clock_display(self) -> None:
        """Update clock display labels."""
        if not self.clock:
            return
        
        try:
            if hasattr(self, 'white_clock_label'):
                self.white_clock_label.config(text=self.clock.get_time_string(True))
            if hasattr(self, 'black_clock_label'):
                self.black_clock_label.config(text=self.clock.get_time_string(False))
            
            # Schedule next update
            self.master.after(100, self.update_clock_display)
        except Exception:
            pass

    def on_depth_change(self, val):
        try:
            d = int(self.depth_var.get())
            self.ai.depth = max(1, d)
        except Exception:
            pass

    def load_piece_images(self):
        assets_dir = os.fspath(resource_dir() / 'assets')
        imgs = {}
        try:
            for sym in ['P','N','B','R','Q','K','p','n','b','r','q','k']:
                fname = None
                if sym.isupper():
                    short = 'w' + sym.lower()
                else:
                    short = 'b' + sym.lower()
                for candidate in (f'{short}.png', f'{sym}.png'):
                    path = os.path.join(assets_dir, candidate)
                    if os.path.exists(path):
                        fname = path
                        break
                if not fname:
                    continue
                try:
                    im = Image.open(fname).convert('RGBA')
                    im = im.resize((48, 48), Image.LANCZOS)
                    imgs[sym] = ImageTk.PhotoImage(im, master=self.master)
                except Exception:
                    imgs = {}
                    break
        except Exception:
            imgs = {}
        if imgs:
            self.piece_images = imgs
        else:
            # fallback: generate piece images programmatically
            try:
                gen_imgs = image_generator.create_all_piece_images(48)
                if gen_imgs and ImageTk:
                    imgs = {}
                    for sym, pil_img in gen_imgs.items():
                        imgs[sym] = ImageTk.PhotoImage(pil_img, master=self.master)
                    self.piece_images = imgs if imgs else None
                else:
                    self.piece_images = None
            except Exception:
                self.piece_images = None

    def load_overlay_icons(self):
        """Load or generate overlay icons for special moves."""
        try:
            gen_icons = image_generator.create_overlay_icons(48)
            if gen_icons and ImageTk:
                icons = {}
                for icon_type, pil_img in gen_icons.items():
                    icons[icon_type] = ImageTk.PhotoImage(pil_img, master=self.master)
                self.overlay_icons = icons if icons else None
            else:
                self.overlay_icons = None
        except Exception:
            self.overlay_icons = None

    def toggle_engine(self):
        if not self.engine_enabled:
            path = self.engine_path_var.get()
            if not path:
                messagebox.showerror('Engine', 'No engine path provided')
                return
            ok = self.engine_adapter.start(path)
            if ok:
                self.engine_enabled = True
                self.engine_toggle.configure(text='Use Engine: On')
            else:
                messagebox.showerror('Engine', 'Failed to start engine (see logs)')
                self.engine_enabled = False
        else:
            try:
                self.engine_adapter.stop()
            finally:
                self.engine_enabled = False
                self.engine_toggle.configure(text='Use Engine: Off')

    def on_close(self):
        if getattr(self, '_tools_busy', False):
            return
        self._save_session()
        self._cancel_review()
        self._closed = True
        self._cancel_search()
        if self.benchmark:
            self.benchmark.stop()
        if self.training_ai:
            self.training_ai.stop()
        try:
            if self.engine_adapter.is_running():
                try:
                    self.engine_adapter.stop()
                except Exception:
                    pass
        finally:
            try:
                self.master.destroy()
            except Exception:
                pass

    def ask_promotion(self, color: int) -> 'Optional[int]':
        dlg = tk.Toplevel(self.master)
        dlg.title('Choose promotion')
        dlg.transient(self.master)
        dlg.grab_set()
        sel = {'choice': None}
        def choose(ch):
            sel['choice'] = ch
            dlg.destroy()
        frame = tk.Frame(dlg)
        frame.pack(padx=8, pady=8)
        use_imgs = bool(self.piece_images)
        self._promo_imgs = []
        
        piece_names = {
            chess.QUEEN: 'Queen',
            chess.ROOK: 'Rook',
            chess.BISHOP: 'Bishop',
            chess.KNIGHT: 'Knight'
        }
        
        def make_button(pt, row, colpos):
            # Create container frame for button and label
            container = tk.Frame(frame)
            container.grid(row=row, column=colpos, padx=4, pady=2)
            
            if use_imgs:
                key = {chess.QUEEN: 'Q', chess.ROOK: 'R', chess.BISHOP: 'B', chess.KNIGHT: 'N'}[pt]
                if color == chess.BLACK:
                    key = key.lower()
                img = self.piece_images.get(key) if self.piece_images else None
                if img:
                    b = tk.Button(container, image=img, width=48, height=48, command=lambda: choose(pt))
                    self._promo_imgs.append(img)
                    b.pack()
                    # Add label below the image
                    tk.Label(container, text=piece_names[pt], font=('Arial', 9)).pack()
                else:
                    b = tk.Button(container, text=piece_names[pt], width=8, command=lambda: choose(pt))
                    b.pack()
            else:
                b = tk.Button(container, text=piece_names[pt], width=8, command=lambda: choose(pt))
                b.pack()
        
        make_button(chess.QUEEN, 0, 0)
        make_button(chess.ROOK, 0, 1)
        make_button(chess.BISHOP, 1, 0)
        make_button(chess.KNIGHT, 1, 1)
        self.master.update_idletasks()
        dlg.update_idletasks()
        x = self.master.winfo_rootx() + (self.master.winfo_width() - dlg.winfo_width()) // 2
        y = self.master.winfo_rooty() + (self.master.winfo_height() - dlg.winfo_height()) // 2
        try:
            dlg.geometry(f'+{x}+{y}')
        except Exception:
            pass
        dlg.wait_window()
        try:
            self._promo_imgs = []
        except Exception:
            pass
        return sel['choice']

    def _special_hints(self) -> str:
        parts = []
        try:
            ep = self.board.ep_square
            if ep is not None:
                parts.append(f'En-passant target: {chess.square_name(ep)}')
        except Exception:
            pass
        try:
            rights = ''
            if self.board.has_kingside_castling_rights(chess.WHITE):
                rights += 'K'
            if self.board.has_queenside_castling_rights(chess.WHITE):
                rights += 'Q'
            if self.board.has_kingside_castling_rights(chess.BLACK):
                rights += 'k'
            if self.board.has_queenside_castling_rights(chess.BLACK):
                rights += 'q'
            if rights:
                parts.append(f'Castling: {rights}')
        except Exception:
            pass
        # Append AI rationale if available
        try:
            if getattr(self, 'ai_last_explanation', ''):
                parts.append(self.ai_last_explanation)
        except Exception:
            pass
        return ' | '.join(parts)

    def _apply_special_overlays(self) -> None:
        try:
            self.board_view.apply_special_overlays(self.board)
        except Exception:
            pass

    def show_legal_moves(self, square: int):
        try:
            self.board_view.show_legal_moves(self.board, square)
        except Exception:
            pass

    def undo_move(self):
        self._return_to_game()
        if self.training_ai and self.training_ai.running:
            self.feedback_var.set('Stop and save training before undoing moves.')
            return
        self._cancel_search()
        if not self.board.move_stack:
            return
        if self._finished_learning_backup is not None:
            for key, previous in self._finished_learning_backup.items():
                if previous is None:
                    self.ai.learning_db.pop(key, None)
                else:
                    self.ai.learning_db[key] = previous
            self.ai.game_log = self._finished_log or []
            try:
                self.ai._save_learning_db()
                self.ai.export_readable_learning()
                if self.config and self._finished_stats_backup is not None:
                    self.config.config['statistics'] = self._finished_stats_backup
                    self.config.save_config()
            except OSError as exc:
                self.feedback_var.set(f'Could not save the undo: {exc}')
            self._finished_learning_backup = None
            self._finished_stats_backup = None
            self._finished_log = None
        self.board.pop()
        # Return to the human's turn, taking back the reply when it exists.
        if self.play_mode == 'player_vs_ai' and self.board.move_stack and self.board.turn != self._human_color():
            self.board.pop()
        valid = set()
        replay = self.board.root()
        for move in self.board.move_stack:
            valid.add((replay.board_fen(), move.uci(), replay.turn))
            valid.add((position_key(replay), move.uci(), replay.turn))
            replay.push(move)
        self.ai.game_log = [item for item in self.ai.game_log if item in valid]
        self.move_history = list(self.board.move_stack)
        self._learn_finalized = False
        self._timed_out = False
        self.selected = None
        self.game_started = False
        if self.clock:
            self.clock.stop()
        self._update_start_pause_button()
        self.board_view.clear_highlights()
        self.feedback_var.set('Move taken back. Press Play to continue. Clocks are paused.')
        self.update_board(force=True)

    def update_controls_state(self):
        try:
            disabled = 'disabled' if self.board.is_game_over() else 'normal'
            try:
                self.depth_scale.configure(state=disabled)
            except Exception:
                pass
            try:
                self.detect_button.configure(state=disabled)
            except Exception:
                pass
            try:
                self.download_button.configure(state=disabled)
            except Exception:
                pass
            try:
                self.verify_button.configure(state=disabled)
            except Exception:
                pass
            try:
                self.engine_toggle.configure(state=disabled)
            except Exception:
                pass
        except Exception:
            pass

    def save_pgn(self):
        game = chess.pgn.Game()
        game.setup(self.board.root())
        node = game
        b = self.board.root()
        for mv in self.board.move_stack:
            node = node.add_variation(mv)
            b.push(mv)
        file = filedialog.asksaveasfilename(defaultextension='.pgn', filetypes=[('PGN files', '*.pgn')])
        if file:
            with open(file, 'w', encoding='utf-8') as f:
                exporter = chess.pgn.FileExporter(f)
                game.accept(exporter)
            messagebox.showinfo('Saved', f'Saved PGN to {file}')

    def autosave_pgn(self, result: 'Optional[str]' = None) -> 'Optional[str]':
        """Automatically save the current game's PGN to an autosaves/ folder.

        Args:
            result: Optional winner string ('white'/'black'/'draw') to include in filename.

        Returns:
            The path to the saved PGN file, or None on failure.
        """
        try:
            autos_dir = os.fspath(data_dir() / 'autosaves')
            os.makedirs(autos_dir, exist_ok=True)
            # Build timestamped filename
            ts = time.strftime('%Y%m%d_%H%M%S')
            suffix = ''
            if result:
                suffix = f"_{result}"
            out_path = os.path.join(autos_dir, f'game_{ts}{suffix}.pgn')

            game = chess.pgn.Game()
            game.setup(self.board.root())
            node = game
            b = self.board.root()
            for mv in self.board.move_stack:
                node = node.add_variation(mv)
                b.push(mv)
            with open(out_path, 'w', encoding='utf-8') as f:
                exporter = chess.pgn.FileExporter(f)
                game.accept(exporter)
            return out_path
        except Exception:
            return None

    def on_toggle_autosave(self) -> None:
        """Persist the auto-save PGN setting to config when toggled."""
        try:
            if self.config:
                var = getattr(self, 'autosave_pgn_var', None)
                val = bool(var.get()) if var is not None else False
                self.config.set('auto_save_pgn', val)
        except Exception:
            pass

    def load_pgn(self):
        self._return_to_game()
        file = filedialog.askopenfilename(filetypes=[('PGN files', '*.pgn')])
        if not file:
            return
        try:
            with open(file, 'r', encoding='utf-8') as f:
                game = chess.pgn.read_game(f)
            if game is None:
                messagebox.showerror('Error', 'No game found in PGN')
                return
            board = game.board()
            for mv in game.mainline_moves():
                board.push(mv)
            self._cancel_search()
            self.game_started = False
            self.selected = None
            self.ai.game_log = []
            self._finished_learning_backup = None
            self._finished_log = None
            self._finished_stats_backup = None
            self._learn_finalized = board.is_game_over(claim_draw=True)
            self._timed_out = False
            self.board = board
            self.move_history = list(board.move_stack)
            self._update_start_pause_button()
            self.update_board(force=True)
        except Exception as e:
            messagebox.showerror('Error', f'Failed to load PGN: {e}')

    def detect_engine(self):
        path = self.engine_adapter.detect()
        if path:
            var = getattr(self, 'engine_path_var', None)
            if var is not None:
                var.set(path)
            messagebox.showinfo('Detected', f'Found stockfish at {path}')
        else:
            messagebox.showinfo('Not found', 'Stockfish not found (engines/ or PATH). Please install and/or provide path.')

    def download_engine(self):
        platform_var = getattr(self, 'platform_var', None)
        prefer = platform_var.get() if platform_var is not None else 'auto'
        gh_token = getattr(self, 'github_token', None)
        token = gh_token.get().strip() if gh_token is not None else ''
        proceed = messagebox.askyesno('Download Stockfish', 'Download Stockfish release from GitHub releases?\nProceed?')
        if not proceed:
            return
        found = self.engine_adapter.download_stockfish(prefer_platform=prefer, token=token)
        if not found:
            messagebox.showerror('Download failed', 'Failed to download or extract Stockfish — check network or token.')
            return
        var = getattr(self, 'engine_path_var', None)
        if var is not None:
            var.set(found)
        messagebox.showinfo('Downloaded', f'Stockfish downloaded to {found}. You can now click Use Engine.')

    def verify_engine(self):
        var = getattr(self, 'engine_path_var', None)
        path = var.get() if var is not None else ''
        if not path:
            messagebox.showerror('Verify failed', 'No engine path provided')
            return
        if not os.path.exists(path) and shutil.which(path) is None:
            messagebox.showerror('Verify failed', 'Engine executable not found')
            return
        vr = getattr(self, 'verify_retries', None)
        vt = getattr(self, 'verify_timeout', None)
        bm = getattr(self, 'backoff_max', None)
        bv = getattr(self, 'backoff_var', None)
        ad = getattr(self, 'auto_download_var', None)
        retries = max(1, int(vr.get())) if vr is not None else 2
        timeout = float(vt.get()) if vt is not None else 0.05
        backoff = float(bm.get()) if bm is not None else 5.0
        strategy = bv.get() if bv is not None else 'linear'
        auto_dl = bool(ad.get()) if ad is not None else False
        platform_var = getattr(self, 'platform_var', None)
        prefer = platform_var.get() if platform_var is not None else 'auto'
        gh_token = getattr(self, 'github_token', None)
        token = gh_token.get().strip() if gh_token is not None else ''
        ok, msg, found_path = self.engine_adapter.verify(path, retries=retries, timeout=timeout, auto_download=auto_dl, prefer_platform=prefer, backoff=strategy, max_wait=backoff, token=token)
        if ok:
            if found_path:
                var = getattr(self, 'engine_path_var', None)
                if var is not None:
                    var.set(found_path)
            messagebox.showinfo('Verify OK', msg)
            vlog = getattr(self, 'verify_log', None)
            if vlog is not None:
                vlog.insert(tk.END, f'OK: {msg}')
        else:
            vlog = getattr(self, 'verify_log', None)
            if vlog is not None:
                vlog.insert(tk.END, f'ERR: {msg}')
            messagebox.showerror('Verify failed', msg)

    # --- Batch PGN Converter UI callbacks ---
    def open_batch_converter_input_dir(self):
        try:
            path = filedialog.askdirectory(title='Select PGN input directory')
            if path:
                self.converter_input_dir_var.set(path)
        except Exception:
            pass

    def open_batch_converter_output_dir(self):
        try:
            path = filedialog.askdirectory(title='Select output directory')
            if path:
                self.converter_output_dir_var.set(path)
        except Exception:
            pass

    def start_batch_conversion(self):
        try:
            in_dir = self.converter_input_dir_var.get().strip()
            out_dir = self.converter_output_dir_var.get().strip()
            fmt = self.converter_format_var.get().strip()
            if not in_dir or not os.path.isdir(in_dir):
                messagebox.showerror('Batch Convert', 'Select a valid input directory containing .pgn files.')
                return
            if not out_dir:
                out_dir = os.path.join(in_dir, 'converted')
                self.converter_output_dir_var.set(out_dir)
            def worker():
                try:
                    self._post_ui(self.converter_status_var.set, 'Running...')
                    report = batch_convert(in_dir, out_dir, fmt=fmt, force=False, aggregate_csv=True)
                    summary = f"{report.get('ok',0)} ok, {report.get('skipped',0)} skipped, {report.get('error',0)} errors"
                    self._post_ui(self.converter_status_var.set, f'Done: {summary}')
                except Exception as e:
                    self._post_ui(self.converter_status_var.set, f'Error: {e}')
            threading.Thread(target=worker, daemon=True).start()
        except Exception:
            pass
