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
        self.practice_choice = tk.StringVar(master=self.master, value=PUZZLES[0].title)
        picker = ttk.Combobox(self.practice_workspace, textvariable=self.practice_choice,
                             values=[p.title for p in PUZZLES], state='readonly')
        picker.pack(fill='x', pady=5)
        picker.bind('<<ComboboxSelected>>', self._pick_practice)
        row = tk.Frame(self.practice_workspace)
        row.pack(fill='x')
        for label, command in (('Restart puzzle', self._load_practice), ('Hint', self._practice_hint),
                               ('Next', self._next_practice)):
            tk.Button(row, text=label, command=command).pack(side='left', fill='x', expand=True)
        self.practice_text = tk.StringVar(master=self.master, value='Choose a puzzle. Your game remains paused and saved.')
        tk.Label(self.practice_workspace, textvariable=self.practice_text, wraplength=365,
                 justify='left').pack(fill='x', pady=8)

        navigation = tk.Frame(self.review_workspace)
        navigation.pack(fill='x')
        for text, command in (('|<', lambda: self._review_step(-10000)), ('<', lambda: self._review_step(-1)),
                              ('>', lambda: self._review_step(1)), ('>|', lambda: self._review_step(10000))):
            tk.Button(navigation, text=text, command=command).pack(side='left', fill='x', expand=True)
        row = tk.Frame(self.review_workspace)
        row.pack(fill='x', pady=4)
        tk.Button(row, text='Analyze game', command=self._analyze_review).pack(side='left')
        tk.Button(row, text='Cancel', command=self._cancel_review).pack(side='right')
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
        if not self._features_ready or self.session_store is None:
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

    def _pick_practice(self, event=None):
        self.practice_index = next(i for i, p in enumerate(PUZZLES) if p.title == self.practice_choice.get())
        self._load_practice()

    def _load_practice(self):
        if self._activity != 'practice':
            return
        puzzle = PUZZLES[self.practice_index]
        self.practice_choice.set(puzzle.title)
        self.board = chess.Board(puzzle.fen)
        self.practice_done = False
        self.practice_hint_level = 0
        self.selected = None
        self._cancel_search()
        if self.board_view.flipped != (self.board.turn == chess.BLACK):
            self.board_view.flip_board()
        self.update_board(force=True)
        solved = self.config.get('practice_solved', []) if self.config else []
        side = 'White' if self.board.turn else 'Black'
        self.practice_text.set(f'{puzzle.title}: {side} to move.\n{len(solved)}/{len(PUZZLES)} puzzles solved.')
        self.feedback_var.set('Practice mode: your game and clocks are paused.')

    def _practice_click(self, square):
        if self.practice_done:
            return
        piece = self.board.piece_at(square)
        if self.selected is None or (piece and piece.color == self.board.turn):
            if piece and piece.color == self.board.turn:
                self.selected = square
                self.board_view.show_legal_moves(self.board, square)
                self.board_view.highlight(square)
            return
        mover = self.board.piece_at(self.selected)
        promotion = chess.QUEEN if mover and mover.piece_type == chess.PAWN and chess.square_rank(square) in (0, 7) else None
        move = chess.Move(self.selected, square, promotion=promotion)
        puzzle = PUZZLES[self.practice_index]
        if move not in self.board.legal_moves:
            from chess_coach import illegal_move_message
            self.practice_text.set(illegal_move_message(self.board, move))
        elif puzzle.accepts(self.board, move):
            self.board.push(move)
            self.practice_done = True
            solved = list(self.config.get('practice_solved', [])) if self.config else []
            if puzzle.id not in solved:
                solved.append(puzzle.id)
                if self.config:
                    self.config.set('practice_solved', solved)
            self.practice_text.set(f'Correct! {len(solved)}/{len(PUZZLES)} solved. Choose Next for another puzzle.')
            self.selected = None
            self.update_board(force=True)
        else:
            self.practice_text.set('That is legal, but it does not meet the puzzle goal. Try again or use Hint.')

    def _practice_hint(self):
        puzzle = PUZZLES[self.practice_index]
        self.practice_text.set(puzzle.hints[min(self.practice_hint_level, len(puzzle.hints) - 1)])
        self.practice_hint_level += 1

    def _next_practice(self):
        self.practice_index = (self.practice_index + 1) % len(PUZZLES)
        self._load_practice()

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
        self.review_runner = ReviewRunner(self.review_board, self.ai)
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
                text += f"\nPlayed: {row['san']} · Search suggested: {row['suggested']}\nEstimated loss: {estimate}\n{row['note']}"
        else:
            text += '\nChoose Analyze game to see possible mistakes and suggested alternatives.'
        self.review_text.set(text)

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
                self.board_view.focus(chess.square(file, rank))
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
