"""Fresh, validated transformations of original exercises for variation and mastery."""
from functools import lru_cache
import hashlib
import chess
from curriculum import LESSONS, course_puzzles
from tactical_suite import PUZZLES
from practice_model import SequencePuzzle, validate_lines


@lru_cache(maxsize=1)
def fresh_catalogue():
    sources = {p.id: p for p in list(PUZZLES) + list(course_puzzles())}
    existing = {chess.Board(p.fen).board_fen() + ' ' + str(chess.Board(p.fen).turn) for p in sources.values()}
    catalogue, lessons = {}, {}
    for lesson_id, title, description, ids in LESSONS:
        lessons[lesson_id] = []
        for id in ids:
            source = sources[id]
            board = chess.Board(source.fen)
            if hasattr(source, 'lines'):
                lines = source.lines
            else:
                lines = tuple((move.uci(),) for move in board.legal_moves if source.accepts(board, move))
            if not lines:
                continue
            if lesson_id == 'openings':
                for prefix in ('d2d4 d7d5', 'c2c4 e7e5', 'g2g3 d7d5'):
                    fresh = chess.Board()
                    for uci in prefix.split(): fresh.push_uci(uci)
                    solutions = [[uci] for uci in ('g1f3', 'b1c3', 'd2d4') if chess.Move.from_uci(uci) in fresh.legal_moves]
                    _add(catalogue, lessons[lesson_id], existing, fresh, solutions, 'line', title)
                continue
            for horizontal, mirrored in ((True, False), (False, True), (True, True)):
                fresh = board.mirror() if mirrored else board.copy()
                if horizontal: fresh = fresh.transform(chess.flip_horizontal)
                if fresh.castling_rights:
                    continue
                def transform(uci):
                    move = chess.Move.from_uci(uci)
                    def square(s):
                        return (s ^ (56 if mirrored else 0)) ^ (7 if horizontal else 0)
                    return chess.Move(square(move.from_square), square(move.to_square), promotion=move.promotion).uci()
                transformed = [[transform(uci) for uci in line] for line in lines]
                goal = source.goal if source.goal in ('mate', 'promotion') else 'line'
                _add(catalogue, lessons[lesson_id], existing, fresh, transformed, goal, title)
    return catalogue, lessons


def _add(catalogue, lesson, existing, board, lines, goal, title):
    signature = board.board_fen() + ' ' + str(board.turn)
    if signature in existing or not board.is_valid() or board.is_game_over(claim_draw=True):
        return
    valid = validate_lines(board, [list(line) for line in lines[:32]], goal)
    id = 'fresh:' + hashlib.sha256((board.fen() + str(valid)).encode()).hexdigest()[:16]
    catalogue.setdefault(id, SequencePuzzle(id, 'Fresh practice / ' + title, board.fen(),
        ('Apply the lesson in this changed position.', 'Calculate checks, captures and the reply before choosing.'),
        valid, 'Apply the same idea in a changed position; the authored continuation illustrates the lesson.', goal))
    if id not in lesson: lesson.append(id)


def choose_fresh(lesson_id, seen=()):
    catalogue, lessons = fresh_catalogue()
    return next((catalogue[id] for id in lessons[lesson_id] if id not in seen), None)
