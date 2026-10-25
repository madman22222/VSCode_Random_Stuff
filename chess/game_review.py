"""Budgeted background review of a frozen game; evaluations are suggestions."""
import threading


class ReviewRunner:
    def __init__(self, board, ai, depth=2, nodes=1500):
        self.board = board.copy()
        self.ai = ai.fork(learning=False)
        self.ai.depth = depth
        self.nodes = nodes
        self.rows = []
        self.headers = {}
        self.running = False
        self.last_error = None
        self.thread = None
        self._stop = threading.Event()

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def request_stop(self):
        self._stop.set()

    def _evaluate(self, board):
        if board.is_game_over(claim_draw=True):
            outcome = board.outcome(claim_draw=True)
            return None, (0 if outcome.winner is None else (9999999 if outcome.winner else -9999999)), 0
        self.ai.transposition_table.clear()
        self.ai.history.clear()
        self.ai.killers.clear()
        move = self.ai.choose_move_iterative(board, 3, record=False, node_limit=self.nodes)
        metrics = self.ai.last_move_metrics
        score = metrics.get('score_cp')
        return move, (score if board.turn else -score) if score is not None else None, metrics.get('depth', 0)

    def _run(self):
        try:
            board = self.board.root()
            before_move, before_score, before_depth = self._evaluate(board)
            for move in self.board.move_stack:
                if self._stop.is_set():
                    break
                turn = board.turn
                san = board.san(move)
                suggested = board.san(before_move) if before_move else '—'
                from chess_coach import describe_move
                reason = describe_move(board, before_move) if before_move else 'No legal suggestion available.'
                board.push(move)
                after_move, after_score, after_depth = self._evaluate(board)
                loss = None
                if (before_score is not None and after_score is not None
                        and abs(before_score) < 9000000 and abs(after_score) < 9000000):
                    loss = max(0, (before_score - after_score) * (1 if turn else -1))
                    if move == before_move:
                        loss = 0
                note = 'Shallow search suggestion; not a definitive verdict.'
                if any(score is not None and abs(score) >= 9000000 for score in (before_score, after_score)):
                    note = 'Mate-related score: no precise pawn-loss estimate is available.'
                if loss is not None and loss >= 150 and before_depth and (after_depth or board.is_game_over()):
                    note = 'Possible mistake: this search preferred a different move.'
                self.rows.append({'move': move.uci(), 'san': san, 'suggested': suggested,
                    'reason': reason, 'score_before_white': before_score, 'score_after_white': after_score,
                    'estimated_loss_cp': loss, 'note': note, 'depth': before_depth})
                before_move, before_score, before_depth = after_move, after_score, after_depth
        except Exception as exc:
            self.last_error = str(exc)
        finally:
            self.running = False


def annotated_pgn(runner):
    """Export a separate PGN; preserve start position and never change source board."""
    import chess.pgn
    game = chess.pgn.Game.from_board(runner.board)
    game.headers.update(runner.headers)
    game.setup(runner.board.root())
    node = game
    for row in runner.rows:
        if not node.variations:
            break
        node = node.variations[0]
        node.comment = (f"Shallow estimate: suggested {row['suggested']}. {row['note']} "
                        f"{row.get('reason', '')} Search depth {row['depth']}; node budget {runner.nodes}.")
    return str(game) + '\n'
