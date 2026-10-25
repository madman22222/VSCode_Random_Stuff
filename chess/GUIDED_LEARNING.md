# Guided learning and evaluation

Practice offers six short lessons: checkmate, forks/pins, queen mates, rook mates,
king-and-pawn play, and calculating replies. Continue recommended lesson selects
the first incomplete lesson and first unsolved exercise. Completion and selection
persist in preferences. All puzzles also exposes the original seven exercises,
the six new ones, and any imported packs.

For multi-move exercises, play your move and the authored opponent reply appears
automatically. Restart cycles authored defenses. Hints progress from concepts to
the next solution move. A different legal mate is accepted in a mating exercise;
other authored alternative lines are accepted too. A legal move outside those
lines receives factual guidance and leaves the exercise unchanged. The authored
line is a teaching example, not proof that every other legal move is wrong.
The pawn lesson illustrates play against shown replies, not an all-defense result.
Practice keeps the real game, clocks and learning records isolated.

## Local puzzle pack version 2

Version 1 packs with a `solutions` list remain supported. Version 2 uses `lines`,
each a list of UCI half-moves. The solver moves first and last; alternate opponent
replies must have complete authored continuations. Each line has 1–15 half-moves,
with at most 32 lines per exercise. Every move is validated; terminal positions
cannot be continued, duplicate/prefix lines are rejected, mating goals must end
in mate, and promotion goals must end with a promotion.

```json
{
  "version": 2,
  "id": "my-course",
  "author": "Your name and attribution",
  "puzzles": [{
    "id": "fork",
    "title": "Check before collecting",
    "fen": "8/2r1k3/8/8/8/2N5/8/6K1 w - - 0 1",
    "theme": "Fork",
    "difficulty": "Introductory",
    "goal": "line",
    "hints": ["Look for a knight check.", "Attack the king and rook together."],
    "explanation": "Check forces the king to answer before the knight takes the rook.",
    "lines": [["c3d5", "e7f7", "d5c7"]]
  }]
}
```

Goals are `line`, `mate`, or `promotion`. Use Tools → Import puzzle pack; import
returns the selector to All puzzles. The bundled `assets/puzzles/guided-course.json`
contains complete examples. Only use positions you may redistribute; supplied
PDFs are reference material and are not copied into packs or trained as text.

## Review and measurement

Review shows a suggested move and up to four legal continuation half-moves,
following only exact cached entries from the budgeted search. A short line may
end when the cache lacks a suitable entry. Notes report checks, absolute pins,
multiple attacks and legal captures of unprotected pieces. These are things to
inspect, not a proof of a winning tactic. Shallow estimated losses and lines can
be wrong. Exported annotated PGN retains those qualifications.

Compare uses an independent, versioned 16-position starting catalogue covering
four categories. It excludes every self-play opening seed prefix and the practice
positions. Training can later reach these roots: reports expose remembered roots
rather than asserting permanent training isolation. Each sampled root is played
with both colors; both sides use the same depth/node budgets and five-second
ceiling. Reports record version/checksum, memory fingerprint, budgets, category
totals and a per-game ledger. Use enough complete pairs and inspect cutoff draws
and uncertainty. This is internal comparison, not Elo or evidence of improvement
from a small smoke run. Existing scoring promotion gates remain conservative.

## Reliability and testing limits

An atomic checkpoint journal contains matching move records and progress before
compatibility files are published. Resume validates it, rechecks after acquiring
the writer lease, and can finish an interrupted publication. If current memory
matches neither side of the saved transition, Resume refuses to overwrite it;
Start retains that newer memory and begins fresh counters. Unreadable originals
remain preserved. Backup/restore validates the journal alongside other data.
This handles process interruptions; it does not guarantee survival of power loss.

`python benchmarks/soak.py --cycles 100 --output soak-results.json` repeats actual
training, reload, resume, cancellation and lease checks in a temporary profile.
Increase cycles for longer runs. Desktop regressions exercise resize, synthetic
Tk scaling and lesson isolation; Windows CI runs the same source suite and tests
both extracted ZIP editions. Physical Windows DPI/driver, screen-reader and
native signing verification remain separate open Kanban cards.

## Coaching, adaptive review and comparison trends

After a game, open Review, choose Analyze game, then Coaching moments. The summary
selects up to three distinct analyzed positions, preferring different ideas and
larger estimated losses. Inspect position returns to the position before that
move; Practice this idea opens a related authored exercise. Games shorter than
three half-moves have fewer moments. Partial analysis is labeled; suggested moves
remain budget-limited estimates. Custom FEN move numbers and Black starts are
preserved. No game or learning record is replaced by coached practice.

Practice now contains **nine lessons and 21 built-in exercises**. The eight new
exercises cover central knight development, central play, blocking/escaping check,
capturing a checker, queen/rook/pawn endings as Black, and avoiding stalemate.
Explicit alternatives are validated as legal. Opening examples illustrate
principles, not every good opening move. A related exercise teaches the motif;
it is not an automatically proven puzzle extracted from your game.

Choose Adaptive practice: next review to revisit due exercises before new ones.
Mistakes make an exercise due immediately. A hinted or previously missed solution
returns after one day without increasing its mastery streak. Unassisted successes
increase review intervals through 1, 3, 7, 14 and 30 days. Three mastered exercises
unlock the next practice level, up to level three. These are local scheduling
heuristics, not chess ratings. When nothing is due, the UI labels optional review.
Existing solved progress is retained; no network service is used. Preferences
store counters and UTC due times in `practice_stats`; backup/restore includes them.

Support & study → Comparison history → Compare trends across saved versions shows
score, uncertainty interval, completed pairs, cutoff draws, remembered roots and
memory fingerprint. Only complete protocol-2 reports are included. Different
corpus checksums, depth/node/ply budgets, seeds, baseline memory and scoring modes
are grouped separately. Older raw reports remain viewable/exportable. Repeated
seeds or unchanged memory are not independent trials and intervals are not pooled.
A first-to-latest score change is descriptive; it does not establish improvement.
At most the latest 500 history files are inspected; unreadable files are skipped.
Long explanations use native scrollable text widgets rather than a canvas with
embedded child windows.
