"""Independent support/profile/study UI, kept out of the game controller."""
import json
from pathlib import Path
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
from app_paths import data_dir
from profile_store import ProfileStore, profile_path
from support_tools import support_report, latest_release


class StudioTools:
    def _profile_root(self):
        return Path(self.config.config_file).resolve().parent if self.config else data_dir()

    def _build_tools_menu(self, parent):
        self._tools_busy = False
        menu = tk.Menubutton(parent, text='Support & study ▾', relief='raised', takefocus=True)
        menu.pack(side='right', padx=10)
        actions = tk.Menu(menu, tearoff=False)
        menu.configure(menu=actions)
        for label, method in (
                ('Resign game…', self.resign_game), ('Agree local draw…', self.agree_draw),
                ('Back up data…', self._backup_profile), ('Restore data…', self._restore_profile),
                ('Select/create training profile…', self._select_profile),
                ('Comparison history…', self._comparison_history),
                ('Memory limits…', self._memory_limits),
                ('Import puzzle pack…', self._import_puzzle_pack),
                ('Study a FEN position…', self._study_fen), ('Copy current FEN', self._copy_fen),
                ('Export reviewed PGN…', self._export_review),
                ('About / export diagnostics…', self._support_dialog),
                ('Check for updates (online)…', self._check_updates)):
            actions.add_command(label=label, command=method)
        self.master.report_callback_exception = self._report_callback_exception

    def _report_callback_exception(self, kind, value, traceback):
        from logger import error
        error(f'UI callback failed: {kind.__name__}: {value}')
        messagebox.showerror('Action failed', f'{value}\nUse Support & study → About / export diagnostics for build details.')

    def _tool_error(self, title, error):
        from logger import error as log_error
        log_error(f'{title}: {error}')
        messagebox.showerror(title, str(error), parent=self.master)

    def _tools_idle(self):
        if getattr(self, '_tools_busy', False):
            return False
        if any(task and (task.running or task.thread and task.thread.is_alive())
               for task in (self.training_ai, self.benchmark, self.review_runner)):
            messagebox.showinfo('Task running', 'Stop training, comparison and review before changing or backing up profile data.')
            return False
        self._cancel_search()
        self.game_started = False
        if self.clock:
            self.clock.stop()
        self._update_start_pause_button()
        return True

    def _run_tool(self, title, work, finished):
        if self._tools_busy:
            return
        self._tools_busy = True
        dialog = tk.Toplevel(self.master)
        dialog.title(title)
        dialog.transient(self.master)
        dialog.grab_set()
        dialog.protocol('WM_DELETE_WINDOW', lambda: None)
        tk.Label(dialog, text=title + '… Please wait.', padx=25, pady=25).pack()
        def complete(result, error):
            self._tools_busy = False
            dialog.destroy()
            if error:
                self._tool_error(title, error)
            else:
                finished(result)
        def worker():
            try:
                result, error = work(), None
            except Exception as exc:
                result, error = None, exc
            self._post_ui(complete, result, error)
        threading.Thread(target=worker, daemon=True).start()

    def _backup_profile(self):
        if not self._tools_idle():
            return
        target = filedialog.asksaveasfilename(defaultextension='.zip', initialfile='ChessStudio-backup.zip')
        if not target:
            return
        self._save_session()
        store = ProfileStore(self._profile_root())
        self._run_tool('Backing up data', lambda: store.backup(target),
                       lambda path: messagebox.showinfo('Backup complete', f'Saved {path}'))

    def _restore_profile(self):
        if not self._tools_idle():
            return
        target = filedialog.askopenfilename(filetypes=[('Chess Studio backup', '*.zip')])
        if not target:
            return
        store = ProfileStore(self._profile_root())
        def preview(files):
            summary = '\n'.join(sorted(files)[:15])
            if not messagebox.askyesno('Restore preview', f'Replace runtime data with {len(files)} files?\n\n'
                    f'{summary}\n\nA rollback backup will be kept. The app closes after restore; reopen it to load restored data.'):
                return
            self._run_tool('Restoring data', lambda: store.restore(target), self._restore_finished)
        self._run_tool('Checking backup', lambda: store.inspect(target), preview)

    def _restore_finished(self, rollback):
        messagebox.showinfo('Restore complete', f'Previous data retained at:\n{rollback}\n\nReopen Chess Studio to use restored data.')
        # Do not let on_close write the old in-memory session over restored files.
        self._features_ready = False
        self.on_close()

    def _select_profile(self):
        if not self._tools_idle():
            return
        root = self._profile_root()
        names = sorted(p.name for p in (root / 'profiles').glob('*') if p.is_dir())
        name = simpledialog.askstring('Training profile', 'Name (letters/digits/_/-), or blank for default.\n'
                                      'Existing: ' + ', '.join(names), parent=self.master)
        if name is None:
            return
        try:
            from simple_ai import SimpleAI
            target = profile_path(root, name) if name else root / 'ai_learn.json'
            candidate = SimpleAI(depth=self.ai.depth, learning_path=target)
            candidate.use_learning = bool(self.learn_use_var.get())
            candidate.transposition_limit = self.ai.transposition_limit
            candidate.learning_max_entries = self.ai.learning_max_entries
            candidate.learning_min_keep = self.ai.learning_min_keep
            if candidate.load_error:
                raise ValueError(candidate.load_error)
            if not messagebox.askyesno('Switch training profile', 'Start a new paused game using this profile?\n'
                                       'Save the current PGN first if you need it.'):
                return
            # Save preference first, so a failure does not half-switch live state.
            self.config.set('learning_profile', name)
            self._return_to_game()
            self.ai = candidate
            self.ai.compress_learning = bool(self.compress_learning_var.get())
            self.training_ai = None
            self.benchmark = None
            self.new_game()
            self.benchmark_var.set('No comparison loaded for this profile.')
            self.training_dashboard_var.set('Ready in this profile. Start or Resume to load its training progress.')
            self.training_stats_label.configure(text='No active run')
            self.training_progress.configure(value=0)
            self._load_benchmark_result()
            self.feedback_var.set(f'Training profile: {name or "default"}. {target}')
        except Exception as exc:
            self._tool_error('Profile not changed', exc)

    def _memory_limits(self):
        if not self._tools_idle():
            return
        cache = simpledialog.askinteger('Search cache limit', 'Maximum transposition entries (1,000–200,000)',
                                        initialvalue=self.ai.transposition_limit, minvalue=1000, maxvalue=200000)
        if cache is None:
            return
        memory = simpledialog.askinteger('Move memory soft limit', 'Soft cap (1,000–100,000). Pruning discards older/weaker records.\nBack up data before reducing this.',
                                         initialvalue=self.ai.learning_max_entries, minvalue=1000, maxvalue=100000)
        if memory is None:
            return
        try:
            self.config.config.update(transposition_limit=cache, learning_max_entries=memory)
            self.config.save_config()
            self.ai.transposition_limit = cache
            self.ai.learning_max_entries = memory
            self.ai.learning_min_keep = int(memory * .8)
            self.ai.transposition_table.clear()
            self.feedback_var.set('Limits saved. Learning pruning occurs after completed games, with a cooldown.')
        except Exception as exc:
            self._tool_error('Limits not saved', exc)

    def _comparison_history(self):
        folder = Path(self.ai._learning_path).parent / 'comparison-history'
        window = tk.Toplevel(self.master)
        window.title('Comparison history for current profile')
        choices = sorted(folder.glob('*.json'), reverse=True)
        listing = tk.Listbox(window, width=70, height=12, exportselection=False)
        listing.pack(fill='both', expand=True)
        for path in choices:
            listing.insert('end', path.name)
        def export():
            if not listing.curselection():
                return
            from data_validation import read_json
            path = choices[listing.curselection()[0]]
            try:
                text = json.dumps(read_json(path), indent=2)
                self._text_dialog('Comparison report (review before sharing)', text, '.json')
            except Exception as exc:
                self._tool_error('Cannot read report', exc)
        def delete():
            if not listing.curselection():
                return
            index = listing.curselection()[0]
            path = choices[index]
            if messagebox.askyesno('Delete report', f'Delete only {path.name}?\nMove memory and latest comparison are unchanged.'):
                try:
                    path.unlink()
                    choices.pop(index)
                    listing.delete(index)
                except OSError as exc:
                    self._tool_error('Delete failed', exc)
        def trends():
            from comparison_trends import history_text
            paths = list(choices)
            self._run_tool('Reading comparison trends', lambda: history_text(paths),
                           lambda text: self._text_dialog('Comparable evaluation trends', text))
        tk.Button(window, text='Compare trends across saved versions', command=trends).pack(fill='x')
        tk.Button(window, text='View / export selected report', command=export).pack(fill='x')
        tk.Button(window, text='Delete selected history report…', command=delete).pack(fill='x')
        tk.Label(window, text='History is isolated per training profile. No reports yet.' if not choices else
                 'Reports include budgets, outcomes and memory fingerprints.').pack()

    def _text_dialog(self, title, content, extension='.txt'):
        window = tk.Toplevel(self.master)
        window.title(title)
        window.geometry('720x480')
        text = tk.Text(window, wrap='word')
        text.insert('1.0', content)
        text.configure(state='disabled')
        text.pack(fill='both', expand=True)
        def save():
            path = filedialog.asksaveasfilename(parent=window, defaultextension=extension)
            if path:
                try:
                    Path(path).write_text(content, encoding='utf-8')
                except OSError as exc:
                    self._tool_error('Export failed', exc)
        tk.Button(window, text='Export this report…', command=save).pack(fill='x')
        return window

    def _support_dialog(self):
        try:
            text = support_report() + f'\n\nActive learning file: {self.ai._learning_path}\n'
            text += f'Search cache: {len(self.ai.transposition_table)}/{self.ai.transposition_limit} entries\n'
            text += f'Learning memory: {len(self.ai.learning_db)} entries; soft cap {self.ai.learning_max_entries}\n'
            text += 'Local rotating logs: ' + str(data_dir() / 'logs') + '\n'
            text += 'This report excludes logs, move memory and games. Review paths before sharing.'
            self._text_dialog('About / diagnostics', text)
        except Exception as exc:
            self._tool_error('Diagnostics unavailable', exc)

    def _check_updates(self):
        if not messagebox.askyesno('Online release check', 'Contact GitHub for the latest release?\n'
                                   'This is optional; no files will be installed or replaced.'):
            return
        def show(release):
            from support_tools import build_info
            current = build_info()['build']['revision']
            notice = ('You have this published revision.' if current == release.get('revision') else
                      'Latest published revision differs from this copy. A source checkout may be newer than the release.')
            self._text_dialog('Latest release', notice + '\nCurrent revision: ' + current + '\n' + json.dumps(release, indent=2) + '\n\n'
                'Compare the revision with About / diagnostics.\nDownload the ZIP from the release URL. '
                'Back up your data before upgrading. Offline use is unaffected.')
        self._run_tool('Checking GitHub release', latest_release, show)

    def _copy_fen(self):
        self.master.clipboard_clear()
        self.master.clipboard_append(self.board.fen())
        self.feedback_var.set('Current FEN copied.')

    def _study_fen(self):
        if not self._tools_idle():
            return
        fen = simpledialog.askstring('Study position', 'Paste a valid FEN. The live game stays preserved.',
                                     initialvalue=self.board.fen(), parent=self.master)
        if not fen:
            return
        try:
            from data_validation import validated_fen
            position = validated_fen(fen)
            self.workspace.select(self.review_workspace)
            self._workspace_changed()
            self.review_board = position
            self.review_index = 0
            self.board = position.copy()
            self.review_runner = None
            self.update_board(force=True)
            self._show_review_text()
            self.feedback_var.set('FEN study is isolated in Review; return to Game to restore your game.')
        except ValueError as exc:
            self._tool_error('Invalid FEN', exc)

    def _export_review(self):
        runner = self.review_runner
        if not runner or runner.running or not runner.rows:
            messagebox.showinfo('Review', 'Finish a game review before exporting annotations.')
            return
        from game_review import annotated_pgn
        self._text_dialog('Annotated PGN (shallow estimates)', annotated_pgn(runner), '.pgn')

    def _import_puzzle_pack(self):
        if not self._tools_idle():
            return
        target = filedialog.askopenfilename(filetypes=[('Puzzle pack', '*.json')])
        if not target:
            return
        try:
            from puzzle_packs import load_pack
            puzzles = load_pack(target)
            self._return_to_game()
            if {p.id for p in puzzles} & {p.id for p in self.puzzles}:
                raise ValueError('This puzzle pack is already loaded (or has duplicate IDs)')
            from data_validation import read_json
            from training_ai import atomic_json
            pack = read_json(target)
            atomic_json(self._profile_root() / 'puzzle-packs' / (pack['id'] + '.json'), pack)
            self.puzzles = list(self.puzzles) + puzzles
            self.lesson_choice.set('All puzzles')
            self._lesson_changed()
            self.feedback_var.set(f'Loaded {len(puzzles)} puzzles. The pack and solved progress persist in your data folder.')
        except Exception as exc:
            self._tool_error('Puzzle pack rejected', exc)
