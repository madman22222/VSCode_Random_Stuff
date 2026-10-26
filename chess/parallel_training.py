"""Opt-in spawn workers with frozen memory waves and deterministic parent merging."""
from concurrent.futures import ProcessPoolExecutor
import copy
import multiprocessing as mp
import random
import time
from pathlib import Path
import chess
from simple_ai import SimpleAI
from learning_keys import position_key
from training_ai import TrainingAI, starting_board
from data_validation import read_json, training_checkpoint
from training_journal import validate_journal

_worker_ai = None
_worker_stop = None


def _initialize(records, settings, stop):
    global _worker_ai, _worker_stop
    _worker_ai = SimpleAI(depth=settings['depth'], load_learning=False)
    _worker_ai.learning_db = records
    _worker_ai.use_outcome_scoring = False
    _worker_ai.transposition_limit = settings['cache']
    _worker_stop = stop


def play_frozen_game(job):
    """Workers never persist or finalize memory; return completed game logs only."""
    ordinal, settings = job
    ai = _worker_ai
    rng = random.Random(settings['seed'] + ordinal)
    board = starting_board(rng, settings['varied'])
    ai.game_log = []
    ai.transposition_table.clear(); ai.history.clear(); ai.killers.clear()
    plies = 0
    while plies < settings['max_moves'] and not board.is_game_over(claim_draw=True):
        if _worker_stop.is_set(): return None
        started = time.monotonic()
        if plies < 20 and rng.random() < settings['exploration']:
            move = rng.choice(ai._order_moves(board, list(board.legal_moves), 1)[:4])
            ai._log_choice(position_key(board), move.uci(), board.turn)
        else:
            move = ai.choose_move_iterative(board, settings['move_time'])
        if move not in board.legal_moves:
            raise RuntimeError('Parallel worker returned an illegal move')
        board.push(move); plies += 1
        if settings['cpu_percent'] < 100:
            _worker_stop.wait(min(1, (time.monotonic() - started) * (100 / settings['cpu_percent'] - 1)))
    if _worker_stop.is_set(): return None
    outcome = board.outcome(claim_draw=True)
    winner = 'draw' if outcome is None or outcome.winner is None else ('white' if outcome.winner else 'black')
    return board, winner, list(ai.game_log), plies


class ParallelTrainingAI(TrainingAI):
    def __init__(self, ai_instance, workers=2, **kwargs):
        if not 2 <= int(workers) <= 8:
            raise ValueError('Choose 2–8 parallel workers')
        self.workers = int(workers)
        self._process_stop = None
        super().__init__(ai_instance, **kwargs)

    def request_stop(self):
        super().request_stop()
        if self._process_stop is not None:
            self._process_stop.set()

    def _games(self):
        ctx = mp.get_context('spawn')
        while not self._stop.is_set() and (not self.max_games or self._session_games < self.max_games):
            remaining = self.max_games - self._session_games if self.max_games else self.workers * 2
            size = min(self.workers * 2, remaining)
            settings = {'depth': self.depth, 'cache': self.ai.transposition_limit,
                        'seed': self.seed, 'varied': self.varied_starts,
                        'max_moves': self.max_moves, 'exploration': self.exploration_rate,
                        'move_time': self.move_time_limit, 'cpu_percent': self.cpu_percent}
            # A frozen wave differs from online single-worker learning. This is
            # explicit opt-in; individual search budgets and recorded outcomes remain exact.
            records = copy.deepcopy(self.ai.learning_db)
            self._process_stop = ctx.Event()
            try:
                with ProcessPoolExecutor(max_workers=self.workers, mp_context=ctx,
                        initializer=_initialize, initargs=(records, settings, self._process_stop)) as pool:
                    futures = [pool.submit(play_frozen_game, (self.games_played + i, settings)) for i in range(size)]
                    for future in futures:
                        if self._stop.is_set():
                            self._process_stop.set()
                            for pending in futures: pending.cancel()
                            break
                        result = future.result()
                        if result is not None and not self._stop.is_set():
                            yield result
                        if self._stop.is_set():
                            self._process_stop.set()
                            for pending in futures: pending.cancel()
            finally:
                self._process_stop = None


def training_factory(ai_instance, workers=1, resume=False, **kwargs):
    if resume:
        journal = Path(ai_instance._learning_path + '.checkpoint.json')
        state = Path(ai_instance._learning_path + '.training.json')
        if journal.exists():
            data = read_json(journal); validate_journal(data)
            settings = data['progress'].get('settings', {})
        elif state.exists():
            settings = training_checkpoint(read_json(state)).get('settings', {})
        else:
            settings = {}
        workers = settings.get('workers', workers)
    workers = int(workers)
    if not 1 <= workers <= 8:
        raise ValueError('Choose 1–8 training workers')
    cls = ParallelTrainingAI if workers > 1 else TrainingAI
    return cls(ai_instance, resume=resume, **({'workers': workers} if workers > 1 else {}), **kwargs)
