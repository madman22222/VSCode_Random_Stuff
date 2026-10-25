"""A/B against retained pre-optimization evaluation methods; runs on one machine."""
import json,sys,time,statistics,random,types,platform
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'chess'))
import chess
from simple_ai import SimpleAI
class ReferenceAI(SimpleAI):
    def evaluate(self, board: chess.Board) -> int:
        if board.is_checkmate():
            return -9999999
        if board.is_stalemate() or board.is_insufficient_material():
            return 0
        phase = self.game_phase(board)
        score = 0
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece:
                value = self.PIECE_VALUES[piece.piece_type]
                pos_value = self.get_piece_square_value(piece, square, phase)
                if piece.color == chess.WHITE:
                    score += value + pos_value
                else:
                    score -= value + pos_value
        score += self.evaluate_mobility(board)
        score += self.evaluate_king_safety(board, chess.WHITE, phase)
        score -= self.evaluate_king_safety(board, chess.BLACK, phase)
        score += self.evaluate_pawn_structure(board, chess.WHITE)
        score -= self.evaluate_pawn_structure(board, chess.BLACK)
        if len(board.pieces(chess.BISHOP, chess.WHITE)) >= 2:
            score += 30
        if len(board.pieces(chess.BISHOP, chess.BLACK)) >= 2:
            score -= 30
        return score if board.turn == chess.WHITE else -score
    def evaluate_pawn_structure(self, board: chess.Board, color: bool) -> int:
        score = 0
        pawns = board.pieces(chess.PAWN, color)
        for pawn_square in pawns:
            pawn_file = chess.square_file(pawn_square)
            pawn_rank = chess.square_rank(pawn_square)
            if self.is_passed_pawn(board, pawn_square, color):
                score += 20 + pawn_rank * 10 if color == chess.WHITE else 20 + (7 - pawn_rank) * 10
            same_file = [sq for sq in pawns if chess.square_file(sq) == pawn_file]
            if len(same_file) > 1:
                score -= 15
            if self.is_isolated_pawn(board, pawn_square, color):
                score -= 20
            if self.is_backward_pawn(board, pawn_square, color):
                score -= 10
        return score

import argparse
parser=argparse.ArgumentParser()
parser.add_argument('--output', required=True)
output=parser.parse_args().output
corpus=json.loads(Path('benchmarks/positions.json').read_text())['positions']
rng=random.Random(2026);board=chess.Board()
for _ in range(100):
 if board.is_game_over():board=chess.Board()
 a=SimpleAI(load_learning=False); b=ReferenceAI(load_learning=False)
 assert a.evaluate(board)==b.evaluate(board)
 board.push(rng.choice(list(board.legal_moves)))
report={'description':'Single-machine evaluation-only A/B, identical engine except two evaluation methods. No tracing/profiling in timer.', 'platform':platform.platform(),'python':platform.python_version(),'seed':2026,'node_limit':1000,'depth':3,'evaluation_equivalence_positions':100,'results':[]}
for row in corpus:
 results={}
 for mode in ('before','after'):
  samples=[];metrics=[]
  for _ in range(5):
   ai=SimpleAI(depth=3,load_learning=False)
   if mode=='before':
    ai.evaluate=types.MethodType(ReferenceAI.evaluate,ai)
    ai.evaluate_pawn_structure=types.MethodType(ReferenceAI.evaluate_pawn_structure,ai)
   start=time.perf_counter();ai.choose_move_iterative(chess.Board(row['fen']),30,record=False,node_limit=1000);samples.append(time.perf_counter()-start);metrics.append(ai.last_move_metrics)
  results[mode]={'median_seconds':statistics.median(samples),'samples_seconds':samples,'metrics':metrics[-1]}
 assert results['before']['metrics']['move']==results['after']['metrics']['move']
 assert results['before']['metrics']['nodes']==results['after']['metrics']['nodes']
 report['results'].append(dict(row,**results))
Path(output).write_text(json.dumps(report,indent=2)+'\n')
print([(r['id'],round(r['before']['median_seconds'],4),round(r['after']['median_seconds'],4)) for r in report['results']])
