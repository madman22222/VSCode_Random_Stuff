"""Background self-play, resumable statistics, and reproducible evaluation."""
from __future__ import annotations
import json
import math
import hashlib
import copy
import os
from pathlib import Path
import random
import tempfile
import threading
import time
import chess
from learning_keys import position_key
from simple_ai import SimpleAI
from logger import info, error


OPENINGS = (
    'e2e4 e7e5 g1f3 b8c6 f1c4 g8f6',
    'd2d4 d7d5 c2c4 e7e6 b1c3 g8f6',
    'e2e4 c7c5 g1f3 d7d6 d2d4 c5d4',
    'd2d4 g8f6 c2c4 g7g6 b1c3 f8g7',
    'c2c4 e7e5 b1c3 g8f6 g2g3 d7d5',
    'e2e4 e7e6 d2d4 d7d5 b1c3 g8f6',
)


def starting_board(rng, varied=True):
    board = chess.Board()
    if varied:
        line = rng.choice(OPENINGS).split()
        for uci in line[:rng.randint(2, len(line))]:
            board.push_uci(uci)
    return board


def atomic_json(path, data, *, compact=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(json.dumps(data, indent=None if compact else 2,
                                    separators=(',', ':') if compact else None))
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


class TrainingAI:
    def __init__(self, ai_instance: SimpleAI, depth=3, batch_size=100,
                 export_interval=None, move_time_limit=0.25,
                 max_games=0, max_moves=300, exploration_rate=0.10,
                 varied_starts=True, seed=42, resume=False):
        self.ai = ai_instance
        self.depth = max(1, int(depth))
        self.batch_size = max(1, int(batch_size))
        self.export_interval = export_interval
        self.move_time_limit = max(0.001, float(move_time_limit))
        self.max_games = max(0, int(max_games))
        self.max_moves = max(1, int(max_moves))
        self.exploration_rate = float(exploration_rate)
        if not 0 <= self.exploration_rate <= 1:
            raise ValueError('Exploration must be between 0 and 1')
        self.varied_starts = bool(varied_starts)
        self.seed = seed
        self.resuming = resume
        self.games_played = 0
        self.results = {'white': 0, 'black': 0, 'draw': 0}
        self.move_limit_draws = 0
        self.current_move_count = 0
        self.running = False
        self.thread = None
        self.last_error = None
        self.state = 'idle'
        self._stop = threading.Event()
        self._elapsed = 0.0
        self._started = None
        self._lock = threading.RLock()
        self._session_games = 0
        self._recent_results = []
        self._saved_games = 0
        self._known_positions = {key.split('|', 1)[0] for key in self.ai.learning_db}
        self._position_count = len(self._known_positions)
        self.state_path = self.ai._learning_path + '.training.json'
        self.journal_path = self.ai._learning_path + '.checkpoint.json'
        self._recovered_memory = None
        self._published_fingerprint = None
        if resume:
            self._load_progress()
            self._saved_games = self.games_played
        self._elapsed_at_start = self._elapsed

    def _load_progress(self):
        from data_validation import read_json, training_checkpoint
        if Path(self.journal_path).exists():
            from training_journal import recoverable
            data, self._recovered_memory = recoverable(self.ai, self.journal_path)
        elif Path(self.state_path).exists():
            data = training_checkpoint(read_json(self.state_path))
        else:
            return
        if not isinstance(data, dict) or data.get('version', 1) != 1:
            raise ValueError('Unsupported training checkpoint version')
        results = data['results']
        if any(type(results.get(key)) is not int or results[key] < 0 for key in self.results):
            raise ValueError('Invalid training checkpoint counters')
        self.results = {key: results[key] for key in self.results}
        self.games_played = sum(self.results.values())
        self.move_limit_draws = int(data.get('move_limit_draws', 0))
        self._elapsed = max(0.0, float(data.get('elapsed_seconds', 0)))
        settings = data.get('settings', {})
        self.depth = max(1, int(settings.get('depth', self.depth)))
        self.move_time_limit = max(0.001, float(settings.get('move_ms', self.move_time_limit * 1000)) / 1000)
        self.exploration_rate = float(settings.get('exploration', self.exploration_rate))
        self.varied_starts = bool(settings.get('varied_starts', self.varied_starts))
        self.seed = int(settings.get('seed', self.seed))

    def snapshot(self):
        with self._lock:
            elapsed = self._elapsed + (time.monotonic() - self._started if self._started else 0)
            return {'version': 1, 'games': self.games_played, 'session_games': self._session_games,
                    'results': dict(self.results), 'move_limit_draws': self.move_limit_draws,
                    'current_moves': self.current_move_count, 'elapsed_seconds': elapsed,
                    'session_elapsed_seconds': max(0, elapsed - self._elapsed_at_start),
                    'saved_games': self._saved_games, 'recent_results': list(self._recent_results),
                    'positions': self._position_count,
                    'learned_moves': len(self.ai.learning_db), 'state': self.state,
                    'error': str(self.last_error) if self.last_error else None,
                    'settings': {'depth': self.depth, 'move_ms': self.move_time_limit * 1000,
                                 'exploration': self.exploration_rate,
                                 'varied_starts': self.varied_starts, 'seed': self.seed}}

    def progress_summary(self, snap=None):
        snap = snap or self.snapshot()
        count, elapsed = snap['session_games'], snap['session_elapsed_seconds']
        rate = 60 * count / elapsed if elapsed > 0 else 0
        text = f"{count} this run · {rate:.1f} games/min · {snap['saved_games']} checkpointed"
        if self.max_games and count >= 2 and rate > 0:
            remaining = max(0, self.max_games - count) / rate
            text += f" · ~{remaining:.1f} min left (estimate)"
        recent = snap['recent_results']
        if recent:
            text += f"\nLast {len(recent)}: W{recent.count('white')} B{recent.count('black')} D{recent.count('draw')}"
        return text

    def _checkpoint(self):
        if getattr(self.ai, 'load_error', None):
            raise ValueError(self.ai.load_error)
        from training_journal import disk_records, fingerprint
        # Publish the authoritative pair first. A kill between the following two
        # compatibility writes is recoverable without guessing which counters fit.
        progress = self.snapshot()
        progress['saved_games'] = self.games_played
        current_fingerprint = fingerprint(self.ai.learning_db)
        previous_fingerprint = (self._published_fingerprint if self.ai._writer_lease is not None
                                and self._published_fingerprint is not None else fingerprint(disk_records(self.ai)))
        atomic_json(self.journal_path, {'version': 1,
            'memory': {'meta': {'version': self.ai.learning_version}, 'data': self.ai.learning_db},
            'fingerprint': current_fingerprint,
            'previous_fingerprint': previous_fingerprint, 'progress': progress}, compact=True)
        self.ai._save_learning_db()
        self._published_fingerprint = current_fingerprint
        previous = self._saved_games
        self._saved_games = self.games_played
        try:
            atomic_json(self.state_path, self.snapshot())
        except Exception:
            self._saved_games = previous
            raise

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.ai.acquire_writer()
        self._published_fingerprint = None
        try:
            if getattr(self.ai, 'load_error', None):
                raise ValueError(self.ai.load_error)
            if self.resuming:
                # Revalidate after taking the writer lease: construction is read-only.
                self._load_progress()
                if self._recovered_memory is not None:
                    self.ai.learning_db = self._recovered_memory
                    self._known_positions = {key.split('|', 1)[0] for key in self.ai.learning_db}
                    self._position_count = len(self._known_positions)
                    self._saved_games = self.games_played
                    self.ai._save_learning_db()
                    atomic_json(self.state_path, self.snapshot())
            if not self.resuming:
                atomic_json(self.ai._learning_path + '.previous.json', {
                    'meta': {'version': self.ai.learning_version, 'outcome_scoring': self.ai.use_outcome_scoring},
                    'data': self.ai.learning_db})
        except Exception:
            self.ai.release_writer()
            raise
        self.ai.use_outcome_scoring = False
        self._stop.clear()
        self.last_error = None
        self._session_games = 0
        self._elapsed_at_start = self._elapsed
        self.ai.depth = self.depth
        self.ai.defer_persistence = True
        # The trainer owns checkpoints so learning and progress save together.
        self.ai.persist_every_n = self.batch_size + 1
        self.ai.export_readable_during_training = False
        self.ai._pending_games = 0
        self._started = time.monotonic()
        self.running = True
        self.state = 'running'
        self.thread = threading.Thread(target=self._training_loop, daemon=True)
        self.thread.start()

    def request_stop(self):
        self._stop.set()
        if self.running:
            self.state = 'saving'

    def stop(self):
        self.request_stop()
        if self.thread and self.thread is not threading.current_thread():
            self.thread.join()

    def _training_loop(self):
        rng = random.Random(self.seed + self.games_played)
        try:
            while not self._stop.is_set() and (not self.max_games or self._session_games < self.max_games):
                board = starting_board(rng, self.varied_starts)
                self.ai.game_log = []
                self.ai.transposition_table.clear()
                self.ai.history.clear()
                self.ai.killers.clear()
                self.current_move_count = 0
                while (not board.is_game_over(claim_draw=True)
                       and self.current_move_count < self.max_moves and not self._stop.is_set()):
                    if self.current_move_count < 20 and rng.random() < self.exploration_rate:
                        choices = self.ai._order_moves(board, list(board.legal_moves), 1)[:4]
                        move = rng.choice(choices)
                        self.ai._log_choice(position_key(board), move.uci(), board.turn)
                    else:
                        move = self.ai.choose_move_iterative(board, self.move_time_limit)
                    if move is None or move not in board.legal_moves:
                        raise RuntimeError('AI did not return a legal move')
                    board.push(move)
                    self.current_move_count += 1
                if self._stop.is_set():
                    self.ai.game_log = []
                    break
                outcome = board.outcome(claim_draw=True)
                winner = 'draw' if outcome is None or outcome.winner is None else (
                    'white' if outcome.winner == chess.WHITE else 'black')
                with self._lock:
                    played_positions = {key for key, _, _ in self.ai.game_log}
                    prune_time = self.ai._last_prune_time
                    self.ai.finalize_game(winner)
                    if self.ai._last_prune_time != prune_time:
                        self._known_positions = {key.split('|', 1)[0] for key in self.ai.learning_db}
                    else:
                        self._known_positions.update(played_positions)
                    self._position_count = len(self._known_positions)
                    self.results[winner] += 1
                    self._recent_results = (self._recent_results + [winner])[-20:]
                    self.games_played += 1
                    self._session_games += 1
                    if outcome is None:
                        self.move_limit_draws += 1
                info(f'Game {self.games_played}: {winner}; {self.current_move_count} half-moves; '
                     f'{len(self.ai.learning_db)} learned moves')
                if self._session_games % self.batch_size == 0:
                    self._checkpoint()
                    self.ai._pending_games = 0
                    if self.export_interval and (self._session_games // self.batch_size) % self.export_interval == 0:
                        self.ai.export_readable_learning()
            self.state = 'stopped' if self._stop.is_set() else 'completed'
        except Exception as exc:
            self.last_error = exc
            self.state = 'error'
            error(f'Training failed: {exc}')
        finally:
            self._elapsed += time.monotonic() - self._started
            self._started = None
            try:
                self._checkpoint()
                self.ai.export_readable_learning()
            except Exception as exc:
                self.last_error = exc
                self.state = 'error'
                error(f'Could not save training: {exc}')
            self.ai.release_writer()
            self.ai.defer_persistence = False
            self.ai.export_readable_during_training = False
            self.running = False
            info(f'Training stopped: {self.games_played} games; {self.results}')


def paired_interval(scores):
    """Conservative 95% Hoeffding range; the sampling unit is one color-swapped pair."""
    if not scores:
        return [0.0, 100.0]
    mean = sum(scores) / len(scores)
    radius = math.sqrt(math.log(40) / (2 * len(scores)))
    return [round(100 * max(0, mean - radius), 1), round(100 * min(1, mean + radius), 1)]


class BenchmarkRunner:
    """Frozen learned engine vs the identical engine without move memory.

    Paired games swap colors from the same opening with equal node/depth budgets.
    No learning updates or gameplay files are written during evaluation.
    """
    def __init__(self, ai, games=4, depth=2, node_limit=500, max_moves=120, seed=2026, opponent='untrained', experimental=False, positions=None, suite_meta=None):
        if games < 2 or games % 2:
            raise ValueError('Comparison games must be a positive even number')
        self.positions = positions
        self.candidate = ai.fork()
        self.candidate.use_learning = True
        if experimental:
            self.candidate.use_outcome_scoring = True
        if opponent not in ('untrained', 'previous'):
            raise ValueError('Unknown comparison opponent')
        self.baseline = ai.fork(learning=False)
        if opponent == 'previous':
            from data_validation import read_json, learning_records
            previous = read_json(ai._learning_path + '.previous.json')
            self.baseline.learning_db = learning_records(previous)
            self.baseline.use_learning = True
            self.baseline.use_outcome_scoring = bool(previous.get('meta', {}).get('outcome_scoring', False)) and previous.get('meta', {}).get('version') == 3
        self.opponent = opponent
        self.experimental = experimental
        self._pair_scores = []
        self.games = games
        self.depth = depth
        self.node_limit = max(1, int(node_limit))
        self.max_moves = max_moves
        self.seed = seed
        self.running = False
        self.thread = None
        self.last_error = None
        self.result = {'wins': 0, 'losses': 0, 'draws': 0, 'move_limit_draws': 0,
                       'completed': 0, 'requested': games, 'seed': seed,
                       'depth': depth, 'nodes_per_move': self.node_limit,
                       'max_plies': max_moves, 'memory_entries': len(self.candidate.learning_db),
                       'score_percent': None, 'state': 'idle', 'opponent': opponent,
                       'candidate_outcome_scoring': self.candidate.use_outcome_scoring,
                       'ci95_score_percent': [0.0, 100.0], 'completed_pairs': 0,
                       'scoring_recommended': False}
        self.result.update(evaluation_protocol=2, baseline_memory_fingerprint=memory_fingerprint(self.baseline),
                           baseline_outcome_scoring=self.baseline.use_outcome_scoring,
                           evaluation_suite=suite_meta or {'id': 'training-openings'},
                           memory_fingerprint=memory_fingerprint(ai), games_ledger=[], categories={})
        self._stop = threading.Event()
        self.result_path = ai._learning_path + '.benchmark.json'

    def start(self):
        if self.running:
            return
        self.running = True
        self.result['state'] = 'running'
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def request_stop(self):
        self._stop.set()

    def stop(self):
        self.request_stop()
        if self.thread:
            self.thread.join()

    def _run(self):
        rng = random.Random(self.seed)
        try:
            for pair in range(self.games // 2):
                selected = rng.choice(self.positions) if self.positions else None
                initial = chess.Board(selected['fen']) if selected else starting_board(rng)
                pair_points = 0.0
                for candidate_color in (chess.WHITE, chess.BLACK):
                    board = initial.copy()
                    for ai in (self.candidate, self.baseline):
                        ai.depth = self.depth
                        ai.transposition_table.clear()
                        ai.history.clear()
                        ai.killers.clear()
                    for ply in range(self.max_moves):
                        if self._stop.is_set() or board.is_game_over(claim_draw=True):
                            break
                        ai = self.candidate if board.turn == candidate_color else self.baseline
                        move = ai.choose_move_iterative(board, time_limit=5, record=False,
                                                        node_limit=self.node_limit)
                        if move is None:
                            raise RuntimeError('Comparison engine returned no move')
                        board.push(move)
                    if self._stop.is_set():
                        self.result['state'] = 'cancelled'
                        return
                    outcome = board.outcome(claim_draw=True)
                    if outcome is None or outcome.winner is None:
                        self.result['draws'] += 1
                        pair_points += 0.5
                        self.result['move_limit_draws'] += int(outcome is None)
                    elif outcome.winner == candidate_color:
                        self.result['wins'] += 1
                        pair_points += 1
                    else:
                        self.result['losses'] += 1
                    category = selected['category'] if selected else 'training'
                    result = 'draw' if outcome is None or outcome.winner is None else ('win' if outcome.winner == candidate_color else 'loss')
                    counts = self.result['categories'].setdefault(category, {'win': 0, 'draw': 0, 'loss': 0})
                    counts[result] += 1
                    self.result['games_ledger'].append({'pair': pair + 1,
                        'position': selected['id'] if selected else initial.fen(),
                        'candidate_color': 'white' if candidate_color else 'black',
                        'result': result, 'move_limit': outcome is None, 'plies': len(board.move_stack)})
                    self.result['completed'] += 1
                    n = self.result['completed']
                    self.result['score_percent'] = round(100 * (
                        self.result['wins'] + self.result['draws'] / 2) / n, 1)
                self._pair_scores.append(pair_points / 2)
                n_pairs = len(self._pair_scores)
                self.result['ci95_score_percent'] = paired_interval(self._pair_scores)
                self.result['completed_pairs'] = n_pairs
            self.result['state'] = 'completed'
            if self.experimental:
                from tactical_suite import run_suite
                candidate_tactics = run_suite(self.candidate)
                baseline_tactics = run_suite(self.baseline)
                self.result['tactics'] = {'candidate': candidate_tactics, 'baseline': baseline_tactics}
                self.result['scoring_recommended'] = (
                    self.result['completed_pairs'] >= 20
                    and self.result['ci95_score_percent'][0] > 50
                    and self.result['move_limit_draws'] <= self.games // 2
                    and candidate_tactics['passed'] == candidate_tactics['total'])
        except Exception as exc:
            self.last_error = exc
            self.result['state'] = 'error'
            self.result['error'] = str(exc)
        finally:
            try:
                atomic_json(self.result_path, self.result)
            except Exception as exc:
                self.last_error = exc
                self.result['state'] = 'error'
                self.result['error'] = str(exc)
            self.running = False


def memory_fingerprint(ai):
    return hashlib.sha256(json.dumps(ai.learning_db, sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


class ComparisonSeries:
    """Run against the untrained engine and the previous saved version."""
    def __init__(self, ai, games=20, depth=2, node_limit=500, max_moves=120,
                 seed=2026, experimental=False, against='both'):
        self.source = ai.fork()
        self.fingerprint = memory_fingerprint(ai)
        opponents = ['untrained', 'previous'] if against == 'both' else [against]
        self.missing_previous = 'previous' in opponents and not Path(ai._learning_path + '.previous.json').exists()
        if self.missing_previous:
            opponents.remove('previous')
        if not opponents:
            raise ValueError('Train once to create a previous-version snapshot first.')
        from evaluation_corpus import load_corpus
        positions, suite_meta = load_corpus(ai)
        self.runners = [BenchmarkRunner(self.source, games, depth, node_limit, max_moves,
                                       seed, opponent, experimental, positions, suite_meta) for opponent in opponents]
        self.current = self.runners[0]
        self.running = False
        self.last_error = None
        self.thread = None
        self.reports = []
        self._stop = threading.Event()
        self.experimental = experimental
        self.eligible = False
        self.result_path = ai._learning_path + '.benchmark.json'

    @property
    def result(self):
        result = copy.deepcopy(self.current.result)
        result.update(reports=copy.deepcopy(self.reports), missing_previous=self.missing_previous,
                      scoring_recommended=self.eligible, memory_fingerprint=self.fingerprint,
                      experiment=self.experimental)
        if self.running:
            result['state'] = 'running'
        return result

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def request_stop(self):
        self._stop.set()
        self.current.request_stop()

    def stop(self):
        self.request_stop()
        if self.thread:
            self.thread.join()

    def _run(self):
        try:
            for runner in self.runners:
                if self._stop.is_set():
                    break
                self.current = runner
                runner.start()
                runner.thread.join()
                self.reports.append(copy.deepcopy(runner.result))
                if runner.last_error:
                    raise runner.last_error
            self.eligible = (self.experimental and not self._stop.is_set() and len(self.reports) == 2
                             and all(r['scoring_recommended'] for r in self.reports))
        except Exception as exc:
            self.last_error = exc
            self.current.result['state'] = 'error'
            self.current.result['error'] = str(exc)
        finally:
            self.running = False
            if self._stop.is_set():
                self.eligible = False
                self.current.result['state'] = 'cancelled'
            try:
                atomic_json(self.result_path, self.result)
                history = Path(self.result_path).parent / 'comparison-history'
                atomic_json(history / f'comparison-{time.time_ns()}.json', self.result)
            except Exception as exc:
                self.last_error = exc
