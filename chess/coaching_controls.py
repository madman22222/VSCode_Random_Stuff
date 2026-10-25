"""Review-to-practice navigation with frozen review data and isolated game state."""
import tkinter as tk
from coaching import coaching_moments


class CoachingControls:
    def _coaching_summary(self):
        runner = self.review_runner
        if not runner or not runner.rows:
            self.feedback_var.set('Choose Analyze game first, then open Coaching moments.')
            return
        moments = coaching_moments(list(runner.rows))
        window = tk.Toplevel(self.master)
        window.title('Three coaching moments')
        window.geometry('740x460')
        tk.Label(window, text='Select a moment, inspect its position, or practice the related idea.\n'
                 'Search suggestions are estimates; partial analysis may omit later moments.',
                 justify='left', wraplength=690).pack(fill='x', padx=12, pady=8)
        listing = tk.Listbox(window, height=4, exportselection=False)
        listing.pack(fill='x', padx=12)
        for moment in moments:
            listing.insert('end', moment['text'].split(':', 1)[0] + ': ' + moment['topic'])
        detail = tk.Text(window, height=9, wrap='word')
        detail.pack(fill='both', expand=True, padx=12, pady=8)
        def selected():
            return moments[listing.curselection()[0]] if listing.curselection() else moments[0]
        def show(event=None):
            detail.configure(state='normal'); detail.delete('1.0', 'end')
            detail.insert('1.0', selected()['text']); detail.configure(state='disabled')
        def position():
            if self._activity != 'review' or self.review_runner is not runner:
                self.feedback_var.set('Reopen coaching from the current review to inspect a position.')
                return
            self.review_index = selected()['index']
            self._review_step(0)
        def practice(event=None):
            self._open_practice_id(selected()['puzzle_id'])
            window.destroy()
        listing.bind('<<ListboxSelect>>', show)
        listing.bind('<Return>', practice)
        listing.selection_set(0); show()
        row = tk.Frame(window); row.pack(fill='x', padx=12, pady=8)
        tk.Button(row, text='Inspect position before move', command=position).pack(side='left')
        tk.Button(row, text='Practice this idea', command=practice).pack(side='left', padx=8)
        tk.Button(row, text='Close', command=window.destroy).pack(side='right')
        listing.focus_set()

    def _open_practice_id(self, puzzle_id):
        chosen = next((i for i, p in enumerate(self.puzzles) if p.id == puzzle_id), None)
        if chosen is None:
            self.feedback_var.set('Related exercise is unavailable; choose another practice lesson.')
            return
        self.workspace.select(self.practice_workspace)
        self._workspace_changed()
        self.lesson_choice.set('All puzzles')
        self._lesson_changed()
        self.practice_index = chosen
        self._load_practice()
