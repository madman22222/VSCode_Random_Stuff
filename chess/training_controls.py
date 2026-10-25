"""Training dashboard and comparison callbacks separated from game controls."""
import copy
from training_ai import TrainingAI, ComparisonSeries


class TrainingControls:
    def start_training_ai(self, resume=False):
        if getattr(self, '_tools_busy', False):
            return
        if self.training_ai and self.training_ai.running:
            return
        if self.benchmark and self.benchmark.running:
            self.training_dashboard_var.set('Cancel the comparison before training.')
            return
        try:
            games, batch = int(self.training_games_var.get()), int(self.training_batch_size_var.get())
            milliseconds = int(self.training_move_time_var.get())
            if games < 0 or batch < 1 or milliseconds < 1:
                raise ValueError('Games must be zero or more; batch size and move time must be positive.')
            self._cancel_search()
            self.game_started = False
            self._update_start_pause_button()
            self.controls_notebook.select(self.control_pages[1])
            # Training has its own search state; it never shares a gameplay log.
            training_ai = self.ai.fork()
            self.training_ai = TrainingAI(training_ai, depth=int(self.depth_var.get()),
                batch_size=batch, move_time_limit=milliseconds / 1000,
                max_games=games, exploration_rate=float(self.exploration_var.get()),
                varied_starts=bool(self.varied_starts_var.get()), resume=resume,
                export_interval=int(self.training_snapshot_interval_var.get()) or None)
            self._training_synced = False
            self.training_ai.start()
            if self.config:
                self.config.config.update(training_games=games, training_batch_size=batch,
                    training_move_time_ms=milliseconds,
                    training_snapshot_batches=int(self.training_snapshot_interval_var.get()))
                self.config.save_config()
        except Exception as exc:
            self.training_dashboard_var.set(f'Cannot start training: {exc}')

    def stop_training_ai(self):
        if self.training_ai:
            self.training_ai.request_stop()
            self.training_dashboard_var.set('Stopping after the current search and saving completed games…')

    def _poll_training_status(self):
        if self.training_ai is None:
            return
        snap = self.training_ai.snapshot()
        seconds = int(snap['elapsed_seconds'])
        results = snap['results']
        self.training_dashboard_var.set(
            f"{snap['state'].capitalize()} · {snap['games']} completed games\n"
            f"White wins {results['white']} · Black wins {results['black']} · Draws {results['draw']}\n"
            f"{seconds // 60}m {seconds % 60}s · {snap['positions']} positions · {snap['learned_moves']} moves remembered\n"
            f"Current game: {snap['current_moves']} half-moves · Move-limit draws: {snap['move_limit_draws']}"
            + (f"\nError: {snap['error']}" if snap['error'] else ''))
        self.training_stats_label.configure(text=self.training_ai.progress_summary(snap))
        limit = self.training_ai.max_games
        self.training_progress.configure(value=(100 * min(snap['session_games'], limit) / limit if limit else 0))
        if not self.training_ai.running and not self._training_synced:
            self.ai.learning_db = copy.deepcopy(self.training_ai.ai.learning_db)
            self.ai.use_outcome_scoring = self.training_ai.ai.use_outcome_scoring
            self._training_synced = True
            self._update_start_pause_button()

    def start_benchmark(self):
        if getattr(self, '_tools_busy', False):
            return
        if self.benchmark and self.benchmark.running:
            return
        if self.training_ai and self.training_ai.running:
            self.benchmark_var.set('Stop and save training before starting a comparison.')
            return
        try:
            games, nodes = int(self.benchmark_games_var.get()), int(self.benchmark_nodes_var.get())
            if not 2 <= games <= 1000 or games % 2 or not 10 <= nodes <= 100000:
                raise ValueError('Use 2–1000 games (even) and 10–100000 nodes per move.')
            self.benchmark = ComparisonSeries(self.ai, games=games, node_limit=nodes,
                                              experimental=bool(self.experimental_scoring_var.get()))
            self.benchmark.start()
        except Exception as exc:
            self.benchmark_var.set(f'Cannot compare: {exc}')

    def stop_benchmark(self):
        if self.benchmark:
            self.benchmark.request_stop()

    def _show_benchmark(self, result):
        reports = list(result.get('reports') or [])
        if not reports or reports[-1].get('opponent') != result.get('opponent'):
            reports.append(result)
        text = [f"Comparison {result.get('state', 'idle')}."]
        for report in reports:
            interval = report.get('ci95_score_percent', [0, 100])
            text.append(f"{report.get('opponent', 'untrained').capitalize()}: {report['completed']}/{report['requested']} games; "
                        f"W{report['wins']} L{report['losses']} D{report['draws']}\n"
                        f"Score {report.get('score_percent') if report.get('score_percent') is not None else '—'}%; conservative 95% range {interval[0]}–{interval[1]}%\n"
                        f"Move-limit draws {report['move_limit_draws']}")
        if result.get('state') == 'running':
            text.append('Comparison running…')
        if result.get('missing_previous'):
            text.append('Previous snapshot unavailable. Train once to create one.')
        if result.get('experiment'):
            text.append('Scoring evidence: ' + ('supports enabling' if result.get('scoring_recommended') else 'not sufficient; scoring stays off'))
        if result.get('error'):
            text.append(result['error'])
        self.benchmark_var.set('\n'.join(text))

    def _load_benchmark_result(self):
        import json
        path = self.ai._learning_path + '.benchmark.json'
        try:
            with open(path, encoding='utf-8') as stream:
                self._show_benchmark(json.load(stream))
        except (OSError, ValueError, KeyError):
            pass

