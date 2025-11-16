"""SimpleAI module extracted from game_controller.
Provides the SimpleAI class implementing chess search and learning.
"""
from __future__ import annotations

import chess  # type: ignore
import chess.pgn  # type: ignore
import random
import time
import os
from typing import Optional
import time

try:
    from logger import info, debug, warn, error  # type: ignore
except Exception:
    # Fallback no-op log functions
    def info(*a, **k): pass
    def debug(*a, **k): pass
    def warn(*a, **k): pass
    def error(*a, **k): pass

# Original class definition copied verbatim (except removed surrounding comments)
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
    ROOK_TABLE = [0,0,0,0,0,0,0,0,5,10,10,10,10,10,10,5,-5,0,0,0,0,0,0,-5,-5,0,0,0,0,0,0,-5,-5,0,0,0,0,0,0,-5,-5,0,0,0,0,0,0,-5,0,0,0,5,5,0,0,0]
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
    def __init__(self, depth=3):
        self.depth = depth
        self.nodes_searched = 0
        self.last_move_metrics = {}
        self.transposition_table = {}
        self.killers = {}
        self.history = {}
        self.learning_db = {}
        self.game_log = []
        self._learning_path = os.path.join(os.path.dirname(__file__), 'ai_learn.json')
        self._learning_path_gz = self._learning_path + '.gz'
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
        self.learning_version = 2          # format version for meta embedding
        self._last_prune_time = 0.0
    def _load_learning_db(self) -> None:
        try:
            import json, gzip
            data = None
            if os.path.exists(self._learning_path_gz):
                with gzip.open(self._learning_path_gz, 'rt', encoding='utf-8') as f:
                    data = json.load(f)
            elif os.path.exists(self._learning_path):
                with open(self._learning_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            if isinstance(data, dict):
                # Support legacy (flat dict) or new {'meta':..., 'data':{}}
                if 'meta' in data and 'data' in data and isinstance(data['data'], dict):
                    self.learning_db = data['data']
                else:
                    self.learning_db = data
            debug(f"Loaded learning DB entries: {len(self.learning_db)}")
        except Exception:
            self.learning_db = {}
    def _save_learning_db(self) -> None:
        try:
            import json, gzip, os
            # Embed meta wrapper
            wrapper = {
                'meta': {
                    'version': self.learning_version,
                    'saved': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'count': len(self.learning_db)
                },
                'data': self.learning_db
            }
            if getattr(self, 'compress_learning', False):
                with gzip.open(self._learning_path_gz, 'wt', encoding='utf-8') as f:
                    json.dump(wrapper, f, separators=(',', ':'), ensure_ascii=False)
                try:
                    if os.path.exists(self._learning_path):
                        os.remove(self._learning_path)
                except Exception:
                    pass
            else:
                with open(self._learning_path, 'w', encoding='utf-8') as f:
                    json.dump(wrapper, f, separators=(',', ':'), ensure_ascii=False)
            debug(f"Saved learning DB ({len(self.learning_db)} entries)")
        except Exception:
            pass
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
                score = (tot) * 0.6 + winrate * 100.0 * 0.3 + (now - last) * 0.1
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
        try:
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
    def game_phase(self, board: chess.Board) -> int:
        total_material = sum(len(board.pieces(pt, chess.WHITE))+len(board.pieces(pt, chess.BLACK)) for pt in [chess.QUEEN,chess.ROOK,chess.BISHOP,chess.KNIGHT])
        if len(board.move_stack) < 10: return 0
        elif total_material <= 6: return 2
        else: return 1
    def get_piece_square_value(self, piece: chess.Piece, square: int, phase: int) -> int:
        sq = square if piece.color == chess.WHITE else chess.square_mirror(square)
        if piece.piece_type == chess.PAWN: return self.PAWN_TABLE[sq]
        elif piece.piece_type == chess.KNIGHT: return self.KNIGHT_TABLE[sq]
        elif piece.piece_type == chess.BISHOP: return self.BISHOP_TABLE[sq]
        elif piece.piece_type == chess.ROOK: return self.ROOK_TABLE[sq]
        elif piece.piece_type == chess.QUEEN: return self.QUEEN_TABLE[sq]
        elif piece.piece_type == chess.KING: return self.KING_ENDGAME_TABLE[sq] if phase==2 else self.KING_MIDDLEGAME_TABLE[sq]
        return 0
    def evaluate(self, board: chess.Board) -> int:
        if board.is_checkmate(): return -20000 if board.turn==chess.WHITE else 20000
        if board.is_stalemate() or board.is_insufficient_material(): return 0
        phase = self.game_phase(board); score = 0
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece:
                value = self.PIECE_VALUES[piece.piece_type]
                pos_value = self.get_piece_square_value(piece, square, phase)
                if piece.color == chess.WHITE: score += value + pos_value
                else: score -= value + pos_value
        score += self.evaluate_mobility(board)
        score += self.evaluate_king_safety(board, chess.WHITE, phase)
        score -= self.evaluate_king_safety(board, chess.BLACK, phase)
        score += self.evaluate_pawn_structure(board, chess.WHITE)
        score -= self.evaluate_pawn_structure(board, chess.BLACK)
        if len(board.pieces(chess.BISHOP, chess.WHITE)) >= 2: score += 30
        if len(board.pieces(chess.BISHOP, chess.BLACK)) >= 2: score -= 30
        return score if board.turn==chess.WHITE else -score
    def evaluate_mobility(self, board: chess.Board) -> int:
        current_turn = board.turn; board.turn = chess.WHITE; w = board.legal_moves.count(); board.turn = chess.BLACK; b = board.legal_moves.count(); board.turn = current_turn; return (w-b)*3
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
        score = 0; pawns = board.pieces(chess.PAWN, color)
        for pawn_square in pawns:
            pawn_file = chess.square_file(pawn_square); pawn_rank = chess.square_rank(pawn_square)
            if self.is_passed_pawn(board, pawn_square, color):
                score += 20 + (pawn_rank*10) if color==chess.WHITE else 20 + ((7-pawn_rank)*10)
            same_file = [sq for sq in pawns if chess.square_file(sq) == pawn_file]
            if len(same_file) > 1: score -= 15
            if self.is_isolated_pawn(board, pawn_square, color): score -= 20
            if self.is_backward_pawn(board, pawn_square, color): score -= 10
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
    def quiescence(self, board: chess.Board, alpha: int, beta: int) -> int:
        try:
            self.nodes_searched += 1
        except Exception:
            pass
        stand_pat = self.evaluate(board)
        if stand_pat >= beta: return beta
        if alpha < stand_pat: alpha = stand_pat
        capture_moves = [m for m in board.legal_moves if board.is_capture(m)]
        capture_moves.sort(key=lambda m: self._move_score(board, m), reverse=True)
        for move in capture_moves:
            board.push(move); score = -self.quiescence(board, -beta, -alpha); board.pop()
            if score >= beta: return beta
            if score > alpha: alpha = score
        return alpha
    def negamax(self, board: chess.Board, depth: int, alpha: int, beta: int) -> int:
        try:
            self.nodes_searched += 1
        except Exception:
            pass
        fen = board.fen()
        if fen in self.transposition_table:
            t_score, t_depth, t_flag, _ = self.transposition_table[fen]
            if t_depth >= depth:
                if t_flag == 'EXACT': return t_score
                if t_flag == 'LOWER' and t_score >= beta: return t_score
                if t_flag == 'UPPER' and t_score <= alpha: return t_score
        if board.is_game_over():
            score = -9999999 if board.is_checkmate() else 0
            self.transposition_table[fen] = (score, depth, 'EXACT', None); return score
        if depth == 0:
            score = self.quiescence(board, alpha, beta); self.transposition_table[fen] = (score, depth, 'EXACT', None); return score
        max_score = -9999999; best_move = None; moves = list(board.legal_moves); moves = self._order_moves(board, moves, depth); orig_alpha = alpha
        for idx, move in enumerate(moves):
            pv = (idx == 0)
            try:
                is_capture = board.is_capture(move); gives_check = board.gives_check(move)
            except Exception:
                is_capture = False; gives_check = False
            board.push(move)
            if pv:
                score = -self.negamax(board, depth-1, -beta, -alpha)
            else:
                reduction = 0
                if depth >= 3 and not is_capture and not gives_check and move.promotion is None and idx >= 4:
                    reduction = 1
                d2 = max(1, depth-1-reduction)
                score = -self.negamax(board, d2, -(alpha+1), -alpha)
                if score > alpha:
                    score = -self.negamax(board, depth-1, -beta, -alpha)
            board.pop()
            if score > max_score: max_score = score; best_move = move
            alpha = max(alpha, score)
            if alpha >= beta:
                self._store_killer(depth, move); self._bump_history(move, depth); break
        flag = 'EXACT'
        if max_score <= orig_alpha: flag = 'UPPER'
        elif max_score >= beta: flag = 'LOWER'
        self.transposition_table[fen] = (max_score, depth, flag, best_move.uci() if best_move else None)
        return max_score
    def choose_move(self, board: chess.Board) -> Optional[chess.Move]:
        position_fen = board.fen().split(' ')[0]
        if position_fen in self.OPENING_BOOK:
            book_moves = self.OPENING_BOOK[position_fen]
            legal_book_moves = [mv for mv in book_moves if mv in [m.uci() for m in board.legal_moves]]
            if legal_book_moves:
                chosen = chess.Move.from_uci(random.choice(legal_book_moves))
                self.last_move_metrics = {
                    'move': chosen.uci(),
                    'depth': 0,
                    'nodes': 0,
                    'branching': len(list(board.legal_moves)),
                    'time': 0.0,
                    'source': 'book'
                }
                return chosen
        start_time = time.time(); self.nodes_searched = 0
        best_move = None; prev_score = 0; root_branching = len(list(board.legal_moves))
        for d in range(1, max(1, self.depth)+1):
            window = 30 + d*10
            alpha = max(-9999999, prev_score - window); beta = min(9999999, prev_score + window)
            move_d, score_d = self._search_root(board, d, alpha, beta)
            if move_d is not None and score_d <= alpha:
                move_d, score_d = self._search_root(board, d, -9999999, beta)
            elif move_d is not None and score_d >= beta:
                move_d, score_d = self._search_root(board, d, alpha, 9999999)
            if move_d is not None:
                best_move, prev_score = move_d, score_d
        if best_move is not None:
            try:
                fen_key = board.fen().split(' ')[0]; self._log_choice(fen_key, best_move.uci(), board.turn)
            except Exception: pass
            elapsed = time.time() - start_time
            self.last_move_metrics = {
                'move': best_move.uci(),
                'depth': self.depth,
                'nodes': self.nodes_searched,
                'branching': root_branching,
                'time': elapsed,
                'source': 'aspiration'
            }
            try:
                info(f"AI metrics: move={best_move.uci()} depth={self.depth} nodes={self.nodes_searched} branching={root_branching} time={elapsed:.3f}s")
            except Exception:
                pass
        return best_move
    def _search_root(self, board: chess.Board, depth: int, alpha: int, beta: int):
        best_move = None; max_score = -9999999; fen = board.fen(); moves = list(board.legal_moves); moves = self._order_moves(board, moves, depth); orig_alpha = alpha
        for idx, move in enumerate(moves):
            board.push(move)
            if idx == 0:
                score = -self.negamax(board, depth-1, -beta, -alpha)
            else:
                score = -self.negamax(board, depth-1, -(alpha+1), -alpha)
                if score > alpha:
                    score = -self.negamax(board, depth-1, -beta, -alpha)
            board.pop()
            if score > max_score: max_score = score; best_move = move
            alpha = max(alpha, score)
            if alpha >= beta:
                self._store_killer(depth, move); self._bump_history(move, depth); break
        flag = 'EXACT'
        if max_score <= orig_alpha: flag = 'UPPER'
        elif max_score >= beta: flag = 'LOWER'
        self.transposition_table[fen] = (max_score, depth, flag, best_move.uci() if best_move else None)
        return best_move, max_score
    def _order_moves(self, board: chess.Board, moves: list[chess.Move], depth: int) -> list[chess.Move]:
        def score_move(m: chess.Move) -> int:
            s = self._move_score(board, m) + self.history.get(m.uci(),0)
            killers = self.killers.get(depth, [])
            if m.uci() in killers: s += 10000
            try:
                fen = board.fen(); entry = self.transposition_table.get(fen)
                if entry and entry[3] == m.uci(): s += 20000
            except Exception: pass
            if self.use_learning:
                try:
                    fen_key = board.fen().split(' ')[0]; s += self._learn_bonus(fen_key, m.uci())
                except Exception: pass
            return s
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
    def choose_move_iterative(self, board: chess.Board, time_limit: float = 5.0) -> Optional[chess.Move]:
        position_fen = board.fen().split(' ')[0]
        if position_fen in self.OPENING_BOOK:
            book_moves = self.OPENING_BOOK[position_fen]
            legal_book_moves = [mv for mv in book_moves if mv in [m.uci() for m in board.legal_moves]]
            if legal_book_moves:
                chosen = chess.Move.from_uci(random.choice(legal_book_moves))
                self.last_move_metrics = {
                    'move': chosen.uci(),
                    'depth': 0,
                    'nodes': 0,
                    'branching': len(list(board.legal_moves)),
                    'time': 0.0,
                    'source': 'book'
                }
                return chosen
        start_time = time.time(); self.nodes_searched = 0; best_move = None; max_target = min(getattr(self,'depth',3), 10)
        root_branching = len(list(board.legal_moves))
        for depth in range(1, max_target+1):
            if time.time() - start_time >= time_limit: break
            self.depth = depth; current_best = None; best_score = -9999999; alpha = -9999999; beta = 9999999
            moves = list(board.legal_moves); moves.sort(key=lambda m: self._move_score(board, m), reverse=True)
            for move in moves:
                if time.time() - start_time >= time_limit: break
                board.push(move); score = -self.negamax(board, depth-1, -beta, -alpha); board.pop()
                if score > best_score: best_score = score; current_best = move
                alpha = max(alpha, score)
            if current_best is not None: best_move = current_best
        elapsed = time.time() - start_time
        if best_move is not None:
            self.last_move_metrics = {
                'move': best_move.uci(),
                'depth': self.depth,
                'nodes': self.nodes_searched,
                'branching': root_branching,
                'time': elapsed,
                'source': 'iterative'
            }
            try:
                info(f"AI metrics: move={best_move.uci()} depth={self.depth} nodes={self.nodes_searched} branching={root_branching} time={elapsed:.3f}s")
            except Exception:
                pass
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
            piece = board.piece_at(move.from_square)
            if piece is not None and piece.piece_type == chess.KING:
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
