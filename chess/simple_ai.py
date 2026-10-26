"""SimpleAI module extracted from game_controller.
Provides the SimpleAI class implementing chess search and learning.
"""
from __future__ import annotations

import chess  # type: ignore
import chess.pgn  # type: ignore
import time
from collections import OrderedDict
import os
from app_paths import data_dir
from search_rules import search_outcome
from learning_keys import position_key, from_fen
from typing import Optional

try:
    from logger import info, debug, warn, error  # type: ignore
except Exception:
    # Fallback no-op log functions
    def info(*a, **k): pass
    def debug(*a, **k): pass
    def warn(*a, **k): pass
    def error(*a, **k): pass


# Public python-chess bitboards; no private board hashes or relaxed rules.
_ADJACENT_FILES = tuple((chess.BB_FILES[f - 1] if f else 0) |
                        (chess.BB_FILES[f + 1] if f < 7 else 0) for f in range(8))
_AHEAD_RANKS = {
    chess.WHITE: tuple(sum(chess.BB_RANKS[r] for r in range(rank + 1, 8)) for rank in range(8)),
    chess.BLACK: tuple(sum(chess.BB_RANKS[r] for r in range(rank)) for rank in range(8)),
}


class SimpleAI:
    """
    Advanced Chess AI with Learning Capability
    ==========================================
    (Documentation retained from original source.)
    """
    PIECE_VALUES = {
        chess.PAWN: 100,
        chess.KNIGHT: 320,
        chess.BISHOP: 330,
        chess.ROOK: 500,
        chess.QUEEN: 900,
        chess.KING: 20000,
    }
    PAWN_TABLE = [0,0,0,0,0,0,0,0,50,50,50,50,50,50,50,50,10,10,20,30,30,20,10,10,5,5,10,27,27,10,5,5,0,0,0,25,25,0,0,0,5,-5,-10,0,0,-10,-5,5,5,10,10,-25,-25,10,10,5,0,0,0,0,0,0,0,0]
    KNIGHT_TABLE = [-50,-40,-30,-30,-30,-30,-40,-50,-40,-20,0,0,0,0,-20,-40,-30,0,10,15,15,10,0,-30,-30,5,15,20,20,15,5,-30,-30,0,15,20,20,15,0,-30,-30,5,10,15,15,10,5,-30,-40,-20,0,5,5,0,-20,-40,-50,-40,-30,-30,-30,-30,-40,-50]
    BISHOP_TABLE = [-20,-10,-10,-10,-10,-10,-10,-20,-10,0,0,0,0,0,0,-10,-10,0,5,10,10,5,0,-10,-10,5,5,10,10,5,5,-10,-10,0,10,10,10,10,0,-10,-10,10,10,10,10,10,10,-10,-10,5,0,0,0,0,5,-10,-20,-10,-10,-10,-10,-10,-10,-20]
    ROOK_TABLE = [
        0,0,0,0,0,0,0,0,
        5,10,10,10,10,10,10,5,
        -5,0,0,0,0,0,0,-5,
        -5,0,0,0,0,0,0,-5,
        -5,0,0,0,0,0,0,-5,
        -5,0,0,0,0,0,0,-5,
        -5,0,0,0,0,0,0,-5,
        0,0,0,5,5,0,0,0,
    ]
    QUEEN_TABLE = [-20,-10,-10,-5,-5,-10,-10,-20,-10,0,0,0,0,0,0,-10,-10,0,5,5,5,5,0,-10,-5,0,5,5,5,5,0,-5,0,0,5,5,5,5,0,-5,-10,5,5,5,5,5,0,-10,-10,0,5,0,0,0,0,-10,-20,-10,-10,-5,-5,-10,-10,-20]
    KING_MIDDLEGAME_TABLE = [-30,-40,-40,-50,-50,-40,-40,-30,-30,-40,-40,-50,-50,-40,-40,-30,-30,-40,-40,-50,-50,-40,-40,-30,-30,-40,-40,-50,-50,-40,-40,-30,-20,-30,-30,-40,-40,-30,-30,-20,-10,-20,-20,-20,-20,-20,-20,-10,20,20,0,0,0,0,20,20,20,30,10,0,0,10,30,20]
    KING_ENDGAME_TABLE = [-50,-40,-30,-20,-20,-30,-40,-50,-30,-20,-10,0,0,-10,-20,-30,-30,-10,20,30,30,20,-10,-30,-30,-10,30,40,40,30,-10,-30,-30,-10,30,40,40,30,-10,-30,-30,-10,20,30,30,20,-10,-30,-30,-30,0,0,0,0,-30,-30,-50,-30,-30,-30,-30,-30,-30,-50]
    OPENING_BOOK = {
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1": ["e2e4","d2d4","c2c4","g1f3"],
        "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1": ["e7e5","c7c5","e7e6","c7c6"],
        "rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 1 2": ["b8c6","g8f6"],
        "rnbqkbnr/pppppppp/8/8/3P4/8/PPP1PPPP/RNBQKBNR b KQkq - 0 1": ["g8f6","d7d5","e7e6"],
        "rnbqkb1r/pppppppp/5n2/8/3P4/8/PPP1PPPP/RNBQKBNR w KQkq - 1 2": ["c2c4","g1f3"],
    }
    def __init__(self, depth=3, learning_path=None, load_learning=True):
        self.depth = depth
        self.nodes_searched = 0
        self.last_move_metrics = {}
        self._evaluation_cache = OrderedDict()
        self.evaluation_cache_limit = 4096
        self.transposition_table = OrderedDict()
        self.transposition_limit = 40000
        self.killers = {}
        self.history = {}
        self.learning_db = {}
        self.use_outcome_scoring = False
        self.game_log = []
        self._writer_lease = None
        self._learning_path = os.fspath(learning_path) if learning_path is not None else os.fspath(data_dir() / 'ai_learn.json')
        self._learning_path_gz = self._learning_path + '.gz'
        if load_learning:
            self._load_learning_db()
        self.use_learning = True
        self.defer_persistence = False
        self.persist_every_n = 100
        self._pending_games = 0
        self.export_readable_during_training = False
        self.compress_learning = True
        # Pruning controls
        self.learning_max_entries = 50000  # soft cap
        self.learning_min_keep = 40000     # target after prune
        self.learning_version = 3          # format version for meta embedding
        self._last_prune_time = 0.0
    def fork(self, learning=True):
        """Independent search state with a frozen copy of move memory."""
        import copy
        ai = SimpleAI(self.depth, self._learning_path, load_learning=False)
        ai.learning_db = copy.deepcopy(self.learning_db) if learning else {}
        ai.load_error = getattr(self, "load_error", None) if learning else None
        ai.use_learning = self.use_learning if learning else False
        ai.compress_learning = self.compress_learning
        ai.evaluation_cache_limit = self.evaluation_cache_limit
        ai.transposition_limit = self.transposition_limit
        ai.learning_max_entries = self.learning_max_entries
        ai.learning_min_keep = self.learning_min_keep
        ai.use_outcome_scoring = self.use_outcome_scoring if learning else False
        return ai

    def _load_learning_db(self) -> None:
        from data_validation import read_json, learning_records
        self.load_error = None
        path = self._learning_path_gz if os.path.exists(self._learning_path_gz) else self._learning_path
        if not os.path.exists(path):
            return
        try:
            data = read_json(path)
            self.learning_db = learning_records(data)
            if isinstance(data.get('meta'), dict):
                self.use_outcome_scoring = bool(data['meta'].get('outcome_scoring', False)) and data['meta'].get('version') == 3
        except (OSError, ValueError, TypeError, EOFError) as exc:
            self.learning_db = {}
            self.load_error = f'Cannot read learning data: {exc}. Original file preserved; use backups to recover.'
            warn(self.load_error)

    def acquire_writer(self):
        from learning_storage import writer_lease
        if self._writer_lease is None:
            lease = writer_lease(self._learning_path)
            lease.__enter__()
            self._writer_lease = lease

    def release_writer(self):
        if self._writer_lease is not None:
            self._writer_lease.__exit__(None, None, None)
            self._writer_lease = None

    def _save_learning_db(self):
        from learning_storage import writer_lease
        if self._writer_lease is not None:
            return self._write_learning_db()
        with writer_lease(self._learning_path):
            return self._write_learning_db()

    def _write_learning_db(self) -> None:
        if getattr(self, 'load_error', None):
            raise ValueError(self.load_error)
        import json
        import gzip
        import tempfile
        wrapper = {
            'meta': {'version': self.learning_version,
                     'saved': time.strftime('%Y-%m-%d %H:%M:%S'),
                     'count': len(self.learning_db), 'outcome_scoring': self.use_outcome_scoring},
            'data': self.learning_db,
        }
        compressed = bool(self.compress_learning)
        target = self._learning_path_gz if compressed else self._learning_path
        directory = os.path.dirname(os.path.abspath(target))
        os.makedirs(directory, exist_ok=True)
        fd, temporary = tempfile.mkstemp(dir=directory, suffix='.tmp')
        os.close(fd)
        try:
            opener = gzip.open if compressed else open
            options = {'compresslevel': 1} if compressed else {}
            with opener(temporary, 'wt', encoding='utf-8', **options) as stream:
                stream.write(json.dumps(wrapper, separators=(',', ':')))
            os.replace(temporary, target)
            # Keep only the active format, so a stale gzip cannot override JSON.
            other = self._learning_path if compressed else self._learning_path_gz
            if os.path.exists(other):
                os.remove(other)
        finally:
            if os.path.exists(temporary):
                os.remove(temporary)

    def _maybe_prune_learning(self) -> None:
        try:
            now = time.time()
            if len(self.learning_db) <= self.learning_max_entries:
                return
            # Avoid pruning too frequently (< 30s apart)
            if now - self._last_prune_time < 30:
                return
            excess = len(self.learning_db) - self.learning_min_keep
            if excess <= 0:
                return
            # Build sortable list: (score, key)
            # Score heuristic: lower winrate & older timestamp pruned first
            victims = []
            for key, rec in self.learning_db.items():
                w = int(rec.get('w', 0)); l = int(rec.get('l', 0)); d = int(rec.get('d', 0))
                tot = w + l + d
                winrate = (w + 0.5*d)/tot if tot else 0.0
                last = rec.get('ts', 0)
                # Composite: prioritize low games & low winrate & old
                score = (tot) * 0.6 + winrate * 100.0 * 0.3 - (now - last) * 0.1
                victims.append((score, key))
            victims.sort()  # lowest first
            to_remove = [k for _, k in victims[:excess]]
            for k in to_remove:
                self.learning_db.pop(k, None)
            self._last_prune_time = now
            info(f"Pruned learning DB: removed {len(to_remove)}; new size {len(self.learning_db)}")
        except Exception:
            pass
    def _log_choice(self, fen_key: str, move_uci: str, color_to_move: bool) -> None:
        try:
            self.game_log.append((fen_key, move_uci, color_to_move))
        except Exception:
            pass
    def finalize_game(self, result: str) -> None:
        if not self.game_log:
            return
        for fen_key, move_uci, color_to_move in self.game_log:
            key = fen_key + '|' + move_uci
            rec = self.learning_db.get(key) or {"w":0,"l":0,"d":0,"ts":0}
            if result == 'draw':
                rec['d'] = rec.get('d',0) + 1
            else:
                winner_is_white = (result == 'white')
                if winner_is_white == color_to_move:
                    rec['w'] = rec.get('w',0) + 1
                else:
                    rec['l'] = rec.get('l',0) + 1
            rec['ts'] = int(time.time())  # update last touched timestamp
            self.learning_db[key] = rec
        self.game_log = []
        # Prune if oversized before persistence
        self._maybe_prune_learning()
        if getattr(self, 'defer_persistence', False):
            self._pending_games = int(getattr(self,'_pending_games',0)) + 1
            threshold = int(getattr(self,'persist_every_n',100))
            if self._pending_games >= max(1, threshold):
                self._save_learning_db()
                if bool(getattr(self,'export_readable_during_training',False)):
                    try:
                        self.export_readable_learning()
                    except Exception:
                        pass
                self._pending_games = 0
        else:
            self._save_learning_db()
            try:
                self.export_readable_learning()
            except Exception:
                pass
    def export_readable_learning(self, path: Optional[str]=None) -> Optional[str]:
        try:
            import json, time
            positions = {}
            for key, rec in self.learning_db.items():
                if '|' not in key:
                    continue
                fen_key, move_uci = key.split('|',1)
                entry = positions.setdefault(fen_key,{"moves":{}})
                entry['moves'][move_uci] = {"wins":int(rec.get('w',0)),"losses":int(rec.get('l',0)),"draws":int(rec.get('d',0))}
            total_positions = 0
            total_entries = 0
            for fen_key, entry in positions.items():
                moves = entry.get('moves',{})
                for mv,r in moves.items():
                    games = r['wins']+r['losses']+r['draws']
                    r['games'] = games
                    r['winrate'] = 0.0 if games==0 else round((r['wins']+0.5*r['draws'])/games,3)
                    r['ordering_bonus'] = int((r['winrate']-0.5)*200)
                    total_entries += 1
                total_positions += 1
            blob = {"meta":{"version":1,"updated":time.strftime('%Y-%m-%d %H:%M:%S'),"total_positions":total_positions,"total_entries":total_entries,"notes":"Ordering bias only."},"positions":positions}
            out_path = path or os.path.join(os.path.dirname(self._learning_path),'ai_learn_readable.json')
            with open(out_path,'w',encoding='utf-8') as f:
                json.dump(blob,f,separators=(',',':'),ensure_ascii=False)
            return out_path
        except Exception:
            return None
    def _learn_bonus(self, fen_key: str, move_uci: str) -> int:
        try:
            rec = self.learning_db.get(fen_key+'|'+move_uci)
            if not rec:
                return 0
            w = int(rec.get('w',0)); l=int(rec.get('l',0)); d=int(rec.get('d',0))
            tot = w + l + d
            if tot == 0: return 0
            rating = (w + 0.5*d)/tot
            return int((rating-0.5)*200)
        except Exception:
            return 0
    def outcome_adjustment(self, fen_key, uci):
        """Small root-only prior; five virtual draws smooth low-sample outcomes."""
        if not self.use_learning or not self.use_outcome_scoring:
            return 0
        record = self.learning_db.get(fen_key + '|' + uci, {})
        wins, losses, draws = (max(0, int(record.get(k, 0))) for k in ('w', 'l', 'd'))
        total = wins + losses + draws
        if total < 5:
            return 0
        # At most a quarter-pawn, far smaller than losing material or checkmate.
        return round(25 * (wins - losses) / (total + 10))

    def game_phase(self, board: chess.Board) -> int:
        total_material = chess.popcount(board.queens | board.rooks | board.bishops | board.knights)
        if total_material <= 6: return 2
        elif len(board.move_stack) < 10: return 0
        else: return 1
    def get_piece_square_value(self, piece: chess.Piece, square: int, phase: int) -> int:
        sq = chess.square_mirror(square) if piece.color == chess.WHITE else square
        if piece.piece_type == chess.PAWN: return self.PAWN_TABLE[sq]
        elif piece.piece_type == chess.KNIGHT: return self.KNIGHT_TABLE[sq]
        elif piece.piece_type == chess.BISHOP: return self.BISHOP_TABLE[sq]
        elif piece.piece_type == chess.ROOK: return self.ROOK_TABLE[sq]
        elif piece.piece_type == chess.QUEEN: return self.QUEEN_TABLE[sq]
        elif piece.piece_type == chess.KING: return self.KING_ENDGAME_TABLE[sq] if phase==2 else self.KING_MIDDLEGAME_TABLE[sq]
        return 0
    def evaluate(self, board: chess.Board) -> int:
        if board.is_checkmate(): return -9999999
        if board.is_stalemate() or board.is_insufficient_material(): return 0
        phase = self.game_phase(board)
        score = 0
        tables = (None, self.PAWN_TABLE, self.KNIGHT_TABLE, self.BISHOP_TABLE,
                  self.ROOK_TABLE, self.QUEEN_TABLE,
                  self.KING_ENDGAME_TABLE if phase == 2 else self.KING_MIDDLEGAME_TABLE)
        for piece_type in chess.PIECE_TYPES:
            table, value = tables[piece_type], self.PIECE_VALUES[piece_type]
            for square in chess.scan_forward(board.pieces_mask(piece_type, chess.WHITE)):
                score += value + table[square ^ 56]
            for square in chess.scan_forward(board.pieces_mask(piece_type, chess.BLACK)):
                score -= value + table[square]
        score += self.evaluate_mobility(board)
        score += self.evaluate_king_safety(board, chess.WHITE, phase)
        score -= self.evaluate_king_safety(board, chess.BLACK, phase)
        score += self.evaluate_pawn_structure(board, chess.WHITE)
        score -= self.evaluate_pawn_structure(board, chess.BLACK)
        if chess.popcount(board.bishops & board.occupied_co[chess.WHITE]) >= 2: score += 30
        if chess.popcount(board.bishops & board.occupied_co[chess.BLACK]) >= 2: score -= 30
        return score if board.turn==chess.WHITE else -score
    def evaluate_mobility(self, board: chess.Board) -> int:
        current_turn = board.turn
        try:
            board.turn = chess.WHITE
            white = board.legal_moves.count()
            board.turn = chess.BLACK
            black = board.legal_moves.count()
            return (white - black) * 3
        finally:
            board.turn = current_turn

    def _evaluate_cached(self, board):
        # Static evaluation does not use repetition/fifty-move claims. Search
        # checks those separately at every node. Include phase, promotion and
        # castling/EP state so every legal-mobility input remains represented.
        key = (board.pawns, board.knights, board.bishops, board.rooks, board.queens,
               board.kings, board.occupied_co[chess.WHITE], board.occupied_co[chess.BLACK],
               board.turn, board.castling_rights, board.ep_square, board.promoted,
               board.chess960, len(board.move_stack) < 10)
        cached = self._evaluation_cache.get(key)
        if cached is not None:
            return cached
        score = self.evaluate(board)
        if self.evaluation_cache_limit > 0:
            if len(self._evaluation_cache) >= self.evaluation_cache_limit:
                self._evaluation_cache.popitem(last=False)
            self._evaluation_cache[key] = score
        return score

    def evaluate_king_safety(self, board: chess.Board, color: bool, phase: int) -> int:
        if phase == 2: return 0
        score = 0; king_square = board.king(color)
        if king_square is None: return 0
        king_file = chess.square_file(king_square)
        if phase == 1 and 2 <= king_file <= 5: score -= 40
        if color == chess.WHITE:
            if king_square in [chess.G1, chess.C1]:
                score += 50
                if king_square == chess.G1:
                    for sq in [chess.F2, chess.G2, chess.H2]:
                        p = board.piece_at(sq);
                        if p and p.piece_type == chess.PAWN: score += 10
        else:
            if king_square in [chess.G8, chess.C8]:
                score += 50
                if king_square == chess.G8:
                    for sq in [chess.F7, chess.G7, chess.H7]:
                        p = board.piece_at(sq);
                        if p and p.piece_type == chess.PAWN: score += 10
        return score
    def evaluate_pawn_structure(self, board: chess.Board, color: bool) -> int:
        pawns = board.pawns & board.occupied_co[color]
        enemies = board.pawns & board.occupied_co[not color]
        counts = tuple(chess.popcount(pawns & file) for file in chess.BB_FILES)
        score = 0
        for square in chess.scan_forward(pawns):
            file, rank = square & 7, square >> 3
            adjacent = _ADJACENT_FILES[file]
            if not (enemies & (adjacent | chess.BB_FILES[file]) & _AHEAD_RANKS[color][rank]):
                score += 20 + (rank if color else 7 - rank) * 10
            if counts[file] > 1:
                score -= 15
            if not (pawns & adjacent):
                score -= 20
            if pawns & adjacent & _AHEAD_RANKS[not color][rank]:
                score -= 10
        return score
    def is_passed_pawn(self, board: chess.Board, square: int, color: bool) -> bool:
        pawn_file = chess.square_file(square); pawn_rank = chess.square_rank(square); enemy_color = not color; enemy_pawns = board.pieces(chess.PAWN, enemy_color)
        for enemy_pawn in enemy_pawns:
            ep_file = chess.square_file(enemy_pawn); ep_rank = chess.square_rank(enemy_pawn)
            if abs(ep_file - pawn_file) <= 1:
                if color==chess.WHITE and ep_rank > pawn_rank: return False
                if color==chess.BLACK and ep_rank < pawn_rank: return False
        return True
    def is_isolated_pawn(self, board: chess.Board, square: int, color: bool) -> bool:
        pawn_file = chess.square_file(square); friendly_pawns = board.pieces(chess.PAWN, color)
        for friendly_pawn in friendly_pawns:
            if friendly_pawn != square:
                fp_file = chess.square_file(friendly_pawn)
                if abs(fp_file - pawn_file) == 1: return False
        return True
    def is_backward_pawn(self, board: chess.Board, square: int, color: bool) -> bool:
        pawn_file = chess.square_file(square); pawn_rank = chess.square_rank(square); friendly_pawns = board.pieces(chess.PAWN, color)
        for friendly_pawn in friendly_pawns:
            if friendly_pawn != square:
                fp_file = chess.square_file(friendly_pawn); fp_rank = chess.square_rank(friendly_pawn)
                if abs(fp_file - pawn_file) == 1:
                    if color==chess.WHITE and fp_rank < pawn_rank: return True
                    if color==chess.BLACK and fp_rank > pawn_rank: return True
        return False
    def _check_deadline(self):
        limit = getattr(self, '_node_limit', None)
        if limit is not None and self.nodes_searched >= limit:
            raise TimeoutError('Search node budget reached')
        deadline = getattr(self, '_deadline', None)
        if deadline is not None and time.monotonic() >= deadline:
            raise TimeoutError('Search time budget reached')

    def quiescence(self, board, alpha, beta, ply=0, _terminal_checked=False):
        self._check_deadline()
        self.nodes_searched += 1
        if not _terminal_checked:
            outcome = search_outcome(board)
            if outcome is not None:
                return -9999999 if outcome.winner is not None else 0
        if ply >= 16:
            return self._evaluate_cached(board)
        in_check = board.is_check()
        if not in_check:
            stand_pat = self._evaluate_cached(board)
            if stand_pat >= beta:
                return beta
            alpha = max(alpha, stand_pat)
        moves = [m for m in board.legal_moves
                 if in_check or board.is_capture(m) or m.promotion]
        moves.sort(key=lambda m: self._move_score(board, m), reverse=True)
        for move in moves:
            board.push(move)
            try:
                score = -self.quiescence(board, -beta, -alpha, ply + 1)
            finally:
                board.pop()
            if score >= beta:
                return beta
            alpha = max(alpha, score)
        return alpha

    def negamax(self, board, depth, alpha, beta):
        self._check_deadline()
        self.nodes_searched += 1
        outcome = search_outcome(board)
        if outcome is not None:
            return -9999999 if outcome.winner is not None else 0
        if depth <= 0:
            return self.quiescence(board, alpha, beta, _terminal_checked=True)
        best_score = -10000000
        best_move = None
        original_alpha = alpha
        key = board.fen()
        for move in self._order_moves(board, list(board.legal_moves), depth, _fen=key):
            board.push(move)
            try:
                score = -self.negamax(board, depth - 1, -beta, -alpha)
            finally:
                board.pop()
            if score > best_score:
                best_score, best_move = score, move
            alpha = max(alpha, score)
            if alpha >= beta:
                self._store_killer(depth, move)
                self._bump_history(move, depth)
                break
        flag = 'UPPER' if best_score <= original_alpha else (
            'LOWER' if best_score >= beta else 'EXACT')
        if key not in self.transposition_table and len(self.transposition_table) >= self.transposition_limit:
            self.transposition_table.popitem(last=False)
        self.transposition_table[key] = (best_score, depth, flag, best_move.uci() if best_move else None)
        return best_score

    def choose_move(self, board: chess.Board):
        return self.choose_move_iterative(board, time_limit=5.0)

    def _order_moves(self, board, moves, depth, _fen=None):
        # Build position keys once rather than once for every candidate move.
        fen = board.fen() if _fen is None else _fen
        fen_key = from_fen(fen)
        entry = self.transposition_table.get(fen)
        killers = self.killers.get(depth, [])
        def score_move(move):
            uci = move.uci()
            score = self._move_score(board, move) + self.history.get(uci, 0)
            if uci in killers:
                score += 10000
            if entry and entry[3] == uci:
                score += 20000
            if self.use_learning:
                score += self._learn_bonus(fen_key, uci)
            return score
        return sorted(moves, key=score_move, reverse=True)

    def _store_killer(self, depth: int, move: chess.Move) -> None:
        try:
            u = move.uci(); arr = self.killers.get(depth, [])
            if u in arr: return
            if len(arr) < 2: arr.append(u)
            else: arr[1] = arr[0]; arr[0] = u
            self.killers[depth] = arr
        except Exception: pass
    def _bump_history(self, move: chess.Move, depth: int) -> None:
        try:
            u = move.uci(); self.history[u] = self.history.get(u,0) + depth*depth
        except Exception: pass
    def choose_move_iterative(self, board: chess.Board, time_limit: float = 5.0, record=True, node_limit=None):
        moves = list(board.legal_moves)
        if not moves or board.is_game_over():
            return None
        start = time.monotonic()
        self.nodes_searched = 0
        self._evaluation_cache.clear()
        self._node_limit = node_limit
        while len(self.transposition_table) > self.transposition_limit:
            self.transposition_table.popitem(last=False)
        best_move = moves[0]
        completed_depth = 0
        completed_score = None
        root_fen = board.fen()
        fen_key = from_fen(root_fen)
        priors = ({move.uci(): self.outcome_adjustment(fen_key, move.uci()) for move in moves}
                  if self.use_learning and self.use_outcome_scoring else {})
        active_prior = any(priors.values())
        self._deadline = start + max(0.001, time_limit)
        try:
            for depth in range(1, max(1, self.depth) + 1):
                alpha, beta = -10000000, 10000000
                current_best, best_score = None, -10000000
                for move in self._order_moves(board, moves, depth, _fen=root_fen):
                    self._check_deadline()
                    board.push(move)
                    try:
                        # Root priors differ per move; full root windows avoid unsound
                        # alpha cutoffs when comparing their adjusted scores.
                        score = -self.negamax(board, depth - 1, -beta,
                                             10000000 if active_prior else -alpha)
                    finally:
                        board.pop()
                    if active_prior and abs(score) < 9000000:
                        score += priors.get(move.uci(), 0)
                    if score > best_score:
                        current_best, best_score = move, score
                    alpha = max(alpha, score)
                if current_best is not None:
                    best_move = current_best
                    completed_depth = depth
                    completed_score = best_score
        except TimeoutError:
            pass
        finally:
            self._deadline = None
            self._node_limit = None
        if record:
            self._log_choice(fen_key, best_move.uci(), board.turn)
        self.last_move_metrics = {
            'move': best_move.uci(), 'depth': completed_depth,
            'nodes': self.nodes_searched, 'branching': len(moves),
            'time': time.monotonic() - start, 'source': 'iterative', 'score_cp': completed_score,
        }
        return best_move

    def _move_score(self, board: chess.Board, move: chess.Move) -> int:
        score = 0
        if move.promotion is not None:
            score += 1200 if move.promotion == chess.QUEEN else 900
        try:
            if board.is_capture(move):
                if board.is_en_passant(move): victim_value = self.PIECE_VALUES[chess.PAWN]
                else:
                    victim_piece = board.piece_type_at(move.to_square); victim_value = self.PIECE_VALUES.get(victim_piece,0) if victim_piece is not None else 0
                score += 200 + victim_value
        except Exception: pass
        try:
            if board.piece_type_at(move.from_square) == chess.KING:
                if abs(chess.square_file(move.from_square) - chess.square_file(move.to_square)) == 2: score += 80
        except Exception: pass
        try:
            board.push(move)
            if board.is_check(): score += 40
            board.pop()
        except Exception:
            try: board.pop()
            except Exception: pass
        return score
