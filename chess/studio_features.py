"""Practice, review, session recovery and accessibility for Chess Studio."""
from pathlib import Path
import time
import tkinter as tk
from tkinter import ttk
import chess
from game_review import ReviewRunner
from session_store import SessionStore
from tactical_suite import PUZZLES
from training_ai import memory_fingerprint


class StudioFeatures:
    def _init_studio_state(self):
        from curriculum import course_puzzles
        self.puzzles = list(PUZZLES) + list(course_puzzles())
        if self.config:
            from puzzle_packs import load_pack
            from logger import warn
            for pack in sorted(Path(self.config.config_file).parent.glob('puzzle-packs/*.json')):
                try:
                    extra = load_pack(pack)
                    if {p.id for p in extra} & {p.id for p in self.puzzles}:
                        raise ValueError('Duplicate puzzle IDs')
                    self.puzzles.extend(extra)
                except (OSError, ValueError, KeyError, TypeError) as exc:
                    warn(f'Puzzle pack not loaded: {pack.name}: {exc}')
        self._activity = 'game'
        self._saved_game = None
        self._features_ready = False
        self._last_session_save = 0
        self.review_runner = None
        self.review_board = None
        self.review_index = 0
        self.practice_index = 0
        self.practice_done = False
        self.practice_hint_level = 0
        self.text_scale = 1.0
        self.session_store = None
        if self.config:
            self.session_store = SessionStore(Path(self.config.config_file).with_name('last_session.json'))
        self._review_render_key = None

    def _build_studio_features(self, accessibility_page):
        self.workspace.bind('<<NotebookTabChanged>>', self._workspace_changed)
        self._build_lessons()
        self.practice_choice = tk.StringVar(master=self.master, value=PUZZLES[0].title)
        picker = ttk.Combobox(self.practice_workspace, textvariable=self.practice_choice,
                             values=[p.title for p in self.puzzles], state='readonly')
        picker.pack(fill='x', pady=5)
        self.practice_picker = picker
        picker.bind('<<ComboboxSelected>>', self._pick_practice)
        row = tk.Frame(self.practice_workspace)
        row.pack(fill='x')
        for label, command in (('Restart puzzle', self._load_practice), ('Hint', self._practice_hint),
                               ('Next', self._next_practice)):
            tk.Button(row, text=label, command=command).pack(side='left', fill='x', expand=True)
        self.practice_text = tk.StringVar(master=self.master, value='Choose a puzzle. Your game remains paused and saved.')
        tk.Label(self.practice_workspace, textvariable=self.practice_text, wraplength=365,
                 justify='left').pack(fill='x', pady=8)

        self._lesson_changed(save=False)

        navigation = tk.Frame(self.review_workspace)
        navigation.pack(fill='x')
        for text, command in (('|<', lambda: self._review_step(-10000)), ('<', lambda: self._review_step(-1)),
                              ('>', lambda: self._review_step(1)), ('>|', lambda: self._review_step(10000))):
            tk.Button(navigation, text=text, command=command).pack(side='left', fill='x', expand=True)
        row = tk.Frame(self.review_workspace)
        row.pack(fill='x', pady=4)
        tk.Button(row, text='Analyze game', command=self._analyze_review).pack(side='left')
        tk.Button(row, text='Details', command=self._review_details).pack(side='left', padx=4)
        tk.Button(row, text='Cancel', command=self._cancel_review).pack(side='right')
        self.review_budget = tk.StringVar(master=self.master, value='Quick')
        ttk.Combobox(self.review_workspace, textvariable=self.review_budget, values=('Quick', 'Deeper'),
                     state='readonly').pack(fill='x')
        self.review_text = tk.StringVar(master=self.master, value='Step through the current or finished game. Left/Right also navigate.')
        tk.Label(self.review_workspace, textvariable=self.review_text, wraplength=365,
                 justify='left').pack(fill='x', pady=6)
        tk.Label(self.review_workspace, text='Estimates use a short search and can be wrong.',
                 wraplength=365, justify='left').pack(fill='x')

        self.text_size_var = tk.StringVar(master=self.master, value=self.config.get('text_size', 'Normal') if self.config else 'Normal')
        self.contrast_var = tk.BooleanVar(master=self.master, value=self.config.get('high_contrast', False) if self.config else False)
        self.piece_style_var = tk.StringVar(master=self.master, value=self.config.get('piece_style', 'Images') if self.config else 'Images')
        for label, variable, values in (('Text size', self.text_size_var, ('Normal', 'Large')),
                                         ('Pieces', self.piece_style_var, ('Images', 'Symbols', 'Letters'))):
            tk.Label(accessibility_page, text=label).pack(anchor='w', pady=(10, 2))
            chooser = ttk.Combobox(accessibility_page, textvariable=variable, values=values, state='readonly')
            chooser.pack(fill='x')
            chooser.bind('<<ComboboxSelected>>', self._apply_accessibility)
        tk.Checkbutton(accessibility_page, text='High-contrast board and highlights', variable=self.contrast_var,
                       command=self._apply_accessibility).pack(anchor='w', pady=10)
        tk.Label(accessibility_page, text='Keyboard: click a board square, then use arrow keys to move focus. '
                 'Enter/Space selects a piece or destination; Escape clears selection. '
                 'Tab navigates controls. In Review, Left/Right step through the game.',
                 wraplength=355, justify='left').pack(fill='x', pady=8)
        self.master.bind('<KeyPress>', self._board_keyboard, add='+')
        self._apply_accessibility(save=False)

    def _save_session(self):
        if not self._features_ready or self.session_store is None or getattr(self, '_tools_busy', False):
            return
        if getattr(self, '_declared_result', None) is not None:
            try:
                self.session_store.clear()
            except OSError as exc:
                self.feedback_var.set(f'Could not clear finished-game recovery: {exc}')
            return
        board = self.board if self._activity == 'game' else self._saved_game['board']
        state = None if self._activity == 'game' else self._saved_game
        clock = {'white': self.clock.white_time, 'black': self.clock.black_time,
                 'increment': self.clock.increment, 'enabled': self.clock_enabled} if self.clock else {}
        try:
            self.session_store.save(board, state['mode'] if state else self.play_mode,
                state['side'] if state else self.player_color_var.get(), clock,
                state['log'] if state else self.ai.game_log,
                state['flipped'] if state else self.board_view.flipped)
            self._last_session_save = time.monotonic()
        except (OSError, ValueError, TypeError) as exc:
            self.feedback_var.set(f'Could not save this game: {exc}')

    def _restore_session(self):
        try:
            data = self.session_store.load() if self.session_store else None
            if data:
                self.board = data['board']
                self.play_mode = data['mode']
                self.mode_var.set(self.play_mode)
                self.mode_display_var.set({'player_vs_ai': 'Play AI', 'player_vs_player': 'Two players',
                                           'ai_vs_ai': 'Watch AI'}[self.play_mode])
                self.player_color_var.set(data['side'])
                self.ai.game_log = data['log']
                if self.clock:
                    self.clock.reset(data['clock']['white'], data['clock']['black'])
                    self.clock.increment = data['clock']['increment']
                    self.clock_enabled = bool(data['clock'].get('enabled', False))
                if self.board_view.flipped != bool(data.get('flipped')):
                    self.board_view.flip_board()
                self.move_history = list(self.board.move_stack)
                self.game_started = False
                self.update_board(force=True)
                self.feedback_var.set('Unfinished game restored. Clocks are paused; press Play to continue.')
        except (OSError, ValueError, KeyError, TypeError) as exc:
            if self.session_store and self.session_store.path.exists():
                backup = self.session_store.path.with_name(f'last_session.invalid-{time.time_ns()}.json')
                try:
                    self.session_store.path.replace(backup)
                except OSError:
                    pass
            self.feedback_var.set(f'Saved game could not be restored: {exc}. The invalid file was retained if possible.')
        finally:
            self._features_ready = True

    def _feature_tick(self):
        if self.review_runner and self._activity == 'review':
            key = (len(self.review_runner.rows), self.review_runner.running, self.review_index)
            if key != self._review_render_key:
                self._review_render_key = key
                self._show_review_text()
        if self._features_ready and time.monotonic() - self._last_session_save >= 5:
            self._save_session()

    def _suspend_game(self):
        if self._activity == 'game':
            self._cancel_search()
            self.game_started = False
            if self.clock:
                self.clock.stop()
            self._saved_game = {'board': self.board.copy(), 'log': list(self.ai.game_log),
                'flipped': self.board_view.flipped, 'mode': self.play_mode,
                'side': self.player_color_var.get()}
            self._update_start_pause_button()
            self._save_session()
        self.selected = None

    def _return_to_game(self):
        if self._activity == 'game':
            return
        self._cancel_review()
        state = self._saved_game
        self._activity = 'game'
        self.board = state['board'].copy()
        self.ai.game_log = list(state['log'])
        self.play_mode = state['mode']
        self.selected = None
        if self.board_view.flipped != state['flipped']:
            self.board_view.flip_board()
        self.workspace.select(self.game_workspace)
        self.update_board(force=True)
        self.feedback_var.set('Game restored. Press Play to continue.')

    def _workspace_changed(self, event=None):
        if not self._features_ready:
            return
        selected = self.workspace.select()
        if selected == str(self.practice_workspace) and self._activity != 'practice':
            self._suspend_game()
            self._activity = 'practice'
            self._load_practice()
        elif selected == str(self.review_workspace) and self._activity != 'review':
            self._suspend_game()
            self._activity = 'review'
            self._cancel_review()
            self.review_runner = None
            self.review_board = self._saved_game['board'].copy()
            self.review_index = len(self.review_board.move_stack)
            self._review_step(0)
        elif selected == str(self.game_workspace):
            self._return_to_game()

    def _review_step(self, delta):
        if self._activity != 'review' or self.review_board is None:
            return
        moves = list(self.review_board.move_stack)
        self.review_index = max(0, min(len(moves), self.review_index + delta))
        self.board = self.review_board.root()
        for move in moves[:self.review_index]:
            self.board.push(move)
        self.update_board(force=True)
        self._show_review_text()

    def _analyze_review(self):
        if self._activity != 'review':
            return
        self._cancel_review()
        depth, nodes = (3, 12000) if self.review_budget.get() == 'Deeper' else (2, 1500)
        self.review_runner = ReviewRunner(self.review_board, self.ai, depth=depth, nodes=nodes)
        actual = self._saved_game['board'] if self._saved_game else self.board
        if (self.review_board.root().fen() == actual.root().fen()
                and list(self.review_board.move_stack) == list(actual.move_stack)):
            self.review_runner.headers = dict(getattr(self, '_pgn_headers', {}))
            outcome = getattr(self, '_declared_result', None) or self.review_board.outcome(claim_draw=True)
            self.review_runner.headers['Result'] = outcome.result() if outcome else '*'
        self.review_runner.start()
        self._show_review_text()

    def _cancel_review(self):
        if self.review_runner:
            self.review_runner.request_stop()

    def _show_review_text(self):
        total = len(self.review_board.move_stack) if self.review_board else 0
        text = f'Position {self.review_index}/{total}. Left/Right steps through moves.'
        runner = self.review_runner
        if runner:
            text += f'\nAnalyzed {len(runner.rows)}/{total}' + ('…' if runner.running else '.')
            if runner.last_error:
                text += f'\nReview error: {runner.last_error}'
            index = self.review_index - 1
            if 0 <= index < len(runner.rows):
                row = runner.rows[index]
                loss = row['estimated_loss_cp']
                estimate = 'unavailable' if loss is None else ('mate risk' if loss > 9000000 else f'{loss / 100:.2f} pawns')
                text += f"\nPlayed: {row['san']} · Search suggested: {row['suggested']}\nEstimated loss: {estimate}\n{row['note']}\n{row.get('reason', '')}\nLine: {' '.join(row.get('continuation', []))}\n{' '.join(row.get('facts', [])[:2])}"
        else:
            text += '\nChoose Analyze game to see possible mistakes and suggested alternatives.'
        self.review_text.set(text)

    def _review_details(self):
        runner = self.review_runner
        index = self.review_index - 1
        if not runner or not 0 <= index < len(runner.rows):
            self.feedback_var.set('Select an analyzed move before opening review details.')
            return
        row = runner.rows[index]
        text = (f"Played: {row['san']}\nSuggested: {row['suggested']}\n"
                f"Continuation: {' '.join(row.get('continuation', []))}\n\n"
                f"Suggested move: {' '.join(row.get('facts', [])) or 'No additional tactical feature identified.'}\n"
                f"Played move: {' '.join(row.get('played_facts', [])) or 'No additional tactical feature identified.'}\n\n"
                f"{row['note']} {row.get('uncertainty', '')}\n"
                f"Search depth {row['depth']}; node budget {runner.nodes}.")
        self._text_dialog('Review details', text)

    def _apply_accessibility(self, event=None, save=True):
        self.text_scale = 1.25 if self.text_size_var.get() == 'Large' else 1.0
        self.board_view.set_accessibility(bool(self.contrast_var.get()), self.piece_style_var.get())
        if hasattr(self, 'theme_var'):
            self.apply_theme_to_ui(self.theme_var.get())
        if save and self.config:
            self.config.config.update(text_size=self.text_size_var.get(), high_contrast=bool(self.contrast_var.get()),
                                      piece_style=self.piece_style_var.get())
            self.config.save_config()

    def _board_keyboard(self, event):
        widget = self.master.focus_get()
        if widget and widget.winfo_class() in ('Entry', 'TEntry', 'TCombobox', 'Text', 'Listbox', 'Scale', 'Spinbox'):
            return
        key = event.keysym
        if self._activity == 'review' and key in ('Left', 'Right', 'Home', 'End'):
            self._review_step({'Left': -1, 'Right': 1, 'Home': -10000, 'End': 10000}[key])
            return 'break'
        if widget is not None and widget is not self.master and widget.winfo_class() != 'Canvas':
            return
        square = self.board_view.focus_square
        if key in ('Left', 'Right', 'Up', 'Down'):
            dx, dy = {'Left': (-1, 0), 'Right': (1, 0), 'Up': (0, 1), 'Down': (0, -1)}[key]
            if self.board_view.flipped:
                dx, dy = -dx, -dy
            file, rank = chess.square_file(square) + dx, chess.square_rank(square) + dy
            if 0 <= file < 8 and 0 <= rank < 8:
                target = chess.square(file, rank)
                self.board_view.focus(target)
                piece = self.board.piece_at(target)
                description = ('White ' if piece.color else 'Black ') + chess.piece_name(piece.piece_type) if piece else 'empty'
                self.feedback_var.set(f'Board focus: {chess.square_name(target)}, {description}. Enter or Space selects.')
            return 'break'
        if key in ('Return', 'space'):
            self.on_click(square)
            return 'break'
        if key == 'Escape':
            self.selected = None
            self.board_view.clear_highlights()
            return 'break'

    def _approve_outcome_scoring(self):
        if (not self.benchmark or self.benchmark.running
                or self.benchmark.result.get('state') != 'completed'
                or not self.benchmark.result.get('scoring_recommended')):
            self.benchmark_var.set('Not enabled: both comparisons need convincing evidence and passing tactical tests.')
            return
        if memory_fingerprint(self.ai) != self.benchmark.result.get('memory_fingerprint'):
            self.benchmark_var.set('Memory changed since this comparison. Run the experiment again.')
            return
        self.ai.use_outcome_scoring = True
        try:
            self.ai._save_learning_db()
        except (OSError, RuntimeError) as exc:
            self.ai.use_outcome_scoring = False
            self.benchmark_var.set(f'Could not save the scoring setting: {exc}')
            return
        self.benchmark_var.set('Tested scoring enabled for this saved version.')
