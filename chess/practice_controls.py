"""Guided lesson and multi-move practice UI; never owns the live game's state."""
import chess
import tkinter as tk
from tkinter import ttk
from curriculum import LESSONS, lesson_status
from practice_model import PuzzleSession, SequencePuzzle


class PracticeControls:
    def _build_lessons(self):
        labels = ['All puzzles'] + [lesson[1] for lesson in LESSONS]
        selected = self.config.get('selected_lesson', '') if self.config else ''
        title = next((lesson[1] for lesson in LESSONS if lesson[0] == selected), 'All puzzles')
        self.lesson_choice = tk.StringVar(master=self.master, value=title)
        chooser = ttk.Combobox(self.practice_workspace, textvariable=self.lesson_choice,
                               values=labels, state='readonly')
        chooser.pack(fill='x', pady=(5, 2))
        chooser.bind('<<ComboboxSelected>>', self._lesson_changed)
        tk.Button(self.practice_workspace, text='Continue recommended lesson',
                  command=self._continue_lesson).pack(fill='x')
        self.lesson_text = tk.StringVar(master=self.master)
        tk.Label(self.practice_workspace, textvariable=self.lesson_text, wraplength=365,
                 justify='left').pack(fill='x', pady=4)
        self._practice_restarts = {}
        self.practice_session = None

    def _active_lesson(self):
        return next((lesson for lesson in LESSONS if lesson[1] == self.lesson_choice.get()), None)

    def _lesson_changed(self, event=None, save=True):
        lesson = self._active_lesson()
        available = [p for p in self.puzzles if lesson is None or p.id in lesson[3]]
        self.practice_picker.configure(values=[p.title for p in available])
        solved = self.config.get('practice_solved', []) if self.config else []
        chosen = next((p for p in available if p.id not in solved), available[0])
        self.practice_index = self.puzzles.index(chosen)
        self.practice_choice.set(chosen.title)
        if save and self.config:
            try:
                self.config.set('selected_lesson', lesson[0] if lesson else '')
            except (OSError, ValueError) as exc:
                self.feedback_var.set(f'Lesson selection not saved: {exc}')
        self._lesson_progress()
        self._load_practice()

    def _lesson_progress(self):
        lesson = self._active_lesson()
        solved = self.config.get('practice_solved', []) if self.config else []
        if lesson:
            completed, total = lesson_status(lesson, solved)
            self.lesson_text.set(f'{lesson[2]}\nProgress: {completed}/{total} exercises complete.')
        else:
            finished = sum(lesson_status(item, solved)[0] == lesson_status(item, solved)[1] for item in LESSONS)
            self.lesson_text.set(f'{finished}/{len(LESSONS)} lessons complete. Choose a lesson or any puzzle.')

    def _continue_lesson(self):
        solved = self.config.get('practice_solved', []) if self.config else []
        lesson = next((item for item in LESSONS if not set(item[3]).issubset(solved)), LESSONS[-1])
        self.lesson_choice.set(lesson[1])
        self._lesson_changed()

    def _pick_practice(self, event=None):
        self.practice_index = next(i for i, p in enumerate(self.puzzles) if p.title == self.practice_choice.get())
        self._load_practice()

    def _load_practice(self):
        if self._activity != 'practice':
            return
        puzzle = self.puzzles[self.practice_index]
        self.practice_choice.set(puzzle.title)
        variant = self._practice_restarts.get(puzzle.id, 0)
        self._practice_restarts[puzzle.id] = variant + 1
        self.practice_session = PuzzleSession(puzzle, variant) if isinstance(puzzle, SequencePuzzle) else None
        self.board = self.practice_session.board if self.practice_session else chess.Board(puzzle.fen)
        self.practice_done = False
        self.practice_hint_level = 0
        self.selected = None
        self._cancel_search()
        if self.board_view.flipped != (self.board.turn == chess.BLACK):
            self.board_view.flip_board()
        self.update_board(force=True)
        self._lesson_progress()
        side = 'White' if self.board.turn else 'Black'
        extra = '\nOpponent replies automatically. Restart cycles authored defenses.' if self.practice_session else ''
        self.practice_text.set(f'{puzzle.title}: {side} to move.{extra}')
        self.feedback_var.set('Practice mode: your game and clocks are paused.')

    def _mark_practice_solved(self, puzzle):
        self.practice_done = True
        solved = list(self.config.get('practice_solved', [])) if self.config else []
        if puzzle.id not in solved:
            solved.append(puzzle.id)
            if self.config:
                try:
                    self.config.set('practice_solved', solved)
                except (OSError, ValueError) as exc:
                    self.feedback_var.set(f'Solved, but progress was not saved: {exc}')
        self._lesson_progress()

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
        puzzle = self.puzzles[self.practice_index]
        if promotion is not None and (isinstance(puzzle, SequencePuzzle) or getattr(puzzle, 'goal', '') == 'solution'):
            promotion = self.ask_promotion(self.board.turn)
            if promotion is None:
                return
        move = chess.Move(self.selected, square, promotion=promotion)
        if move not in self.board.legal_moves:
            from chess_coach import illegal_move_message
            self.practice_text.set(illegal_move_message(self.board, move))
            return
        if self.practice_session:
            result = self.practice_session.attempt(move)
            if not result['accepted']:
                self.practice_text.set(result['message'])
                return
            self.board = self.practice_session.board
            if result['completed']:
                self._mark_practice_solved(puzzle)
            reply = f"\nOpponent played {result['reply']}." if result['reply'] else ''
            self.practice_text.set(result['message'] + reply)
        elif puzzle.accepts(self.board, move):
            self.board.push(move)
            self._mark_practice_solved(puzzle)
            self.practice_text.set('Correct! Choose Next for another puzzle.')
        else:
            self.practice_text.set('That is legal, but it does not meet the puzzle goal. Try again or use Hint.')
            return
        self.selected = None
        self.update_board(force=True)

    def _practice_hint(self):
        puzzle = self.puzzles[self.practice_index]
        hint = puzzle.hints[min(self.practice_hint_level, len(puzzle.hints) - 1)]
        if self.practice_session and not self.practice_done and self.practice_hint_level >= len(puzzle.hints) - 1:
            prefix = self.practice_session.prefix
            line = next(line for line in puzzle.lines if line[:len(prefix)] == prefix)
            hint += '\nNext solution move: ' + self.board.san(chess.Move.from_uci(line[len(prefix)]))
        self.practice_text.set(hint)
        self.practice_hint_level += 1

    def _next_practice(self):
        lesson = self._active_lesson()
        indexes = [i for i, p in enumerate(self.puzzles) if lesson is None or p.id in lesson[3]]
        current = indexes.index(self.practice_index) if self.practice_index in indexes else -1
        self.practice_index = indexes[(current + 1) % len(indexes)]
        self._load_practice()
