"""A small, original curriculum using existing and multi-move practice positions."""
from functools import lru_cache
from app_paths import resource_dir
from puzzle_packs import load_pack

LESSONS = (
    ('mates', '1. Finish with checkmate', 'Check every king escape and avoid stalemate.', ('mate-white', 'mate-black')),
    ('tactics', '2. Forks and pins', 'Use forcing threats; a pin restricts legal responses.', ('guided:fork', 'guided:pin')),
    ('queen', '3. Queen and king ending', 'Bring your king closer before delivering a supported mate.', ('guided:queen-mate',)),
    ('rook', '4. Rook and king ending', 'Use opposition and a rank cut-off to remove escape squares.', ('guided:rook-mate',)),
    ('pawns', '5. King and pawn ending', 'Study king support and reserve pawn tempi against the shown replies.', ('guided:pawn-ending',)),
    ('combinations', '6. Calculate the reply', 'Look beyond the first threat; practice both authored defenses.', ('guided:discovery',)),
)


@lru_cache(maxsize=1)
def course_puzzles():
    return tuple(load_pack(resource_dir() / 'assets/puzzles/guided-course.json'))


def lesson_status(lesson, solved):
    completed = len(set(lesson[3]) & set(solved))
    return completed, len(lesson[3])
