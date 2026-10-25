# AI implementation and learning notes

The built-in `SimpleAI` is a Python chess search engine with outcome-based move
memory. It does not use neural networks, a GPU, or an online service. See
[training and comparison instructions](README.md).

## Search and evaluation

Current search uses iterative deepening, negamax with alpha-beta pruning, and
quiescence for captures/promotions and legal check evasions. Quiescence has a
ply limit. Time/node budget checks bound work; the last completed iteration is
preferred, with a legal fallback if no iteration completes.

Move ordering combines capture/promotion/check heuristics, stored transposition
moves, killer moves, history, and optional learned preferences. The transposition
table helps ordering; it is not evidence of a measured cache hit rate or speedup.
It is cleared at search start when it has exceeded 40,000 entries. Move-memory
pruning has a separate soft cap of 50,000 entries and target of 40,000.

Evaluation uses material, piece-square placement, mobility, king safety, pawn
structure, and a bishop-pair bonus, with phase-sensitive king placement. Scores
are estimates in centipawns (100 is one pawn), not calibrated win probabilities.
The presence of an `OPENING_BOOK` constant does not imply the current iterative
search selects book moves. Training variety comes from curated starts and early
exploration among heuristic-ranked moves.

Earlier documentation described PVS, late-move reductions, aspiration windows,
fixed random book selection, exact depth-to-strength timings, and 10–20× speedups.
Those descriptions do not describe the current search path and are not supported
performance guarantees.

## Move memory

Completed games add wins/losses/draws for logged position/move pairs. Ordinary
learning preference uses the outcome score `(wins + draws/2) / observations` to
produce a bounded move-ordering bonus. It usually affects ordering rather than
static evaluation, but bounded searches can produce different choices.

This is a lightweight memory of observed outcomes. Repeated self-play can
reinforce weak habits, and identical piece placements do not describe every
aspect of chess history. More recorded games do not guarantee better chess.
Use checkpoints, backups, and controlled evaluation.

Training supports fixed additional game counts, batching, compressed memory,
resume, seeded opening selection, and configurable early exploration. Exploration
chooses among four heuristic-ranked moves in the first 20 played half-moves.
Move-limit games count as draws; stopping discards an unfinished game. Resume
restores saved settings/counters, not an interrupted board. Hardware-dependent
time budgets prevent bit-for-bit reproducibility.

## Experimental outcome scoring

The optional root prior uses smoothed outcomes, requires at least five
observations, and caps adjustments at 25 centipawns. It cannot override mate
scores. It is off by default and new training resets it to off.

An experiment must complete at least 20 color-swapped pairs per opponent, have a
conservative lower score bound above 50% against both untrained and previous
opponents, avoid a majority of move-limit draws, and pass the tactical suite
before the UI recommends enabling it. The memory fingerprint must still match.
Passing this gate supplies evidence under those conditions, not a universal
strength or Elo guarantee.

## Comparison methodology

Comparisons freeze move memory and disable learning updates. Both engines use
equal depth/node budgets, the same seeded opening pairs with colors swapped,
and a five-second search ceiling per move. Results include score, outcomes,
move-limit draws, settings, memory fingerprint, and tactical evidence when used.

Conservative 95% ranges use color-swapped pairs as sampling units and Hoeffding's
bounded-mean inequality. They describe the sampled opening distribution; small
samples and many cutoff draws are weak evidence. `--games` is the count per
opponent, must be even, and defaults to 20 for comparison. At least 40 games per
opponent are needed even to meet the experiment's minimum pair count.

## Optimization and validation

Search budgets, cached move-order keys, and skipped inactive scoring work reduce
unnecessary computation. UI rendering separately caches unchanged pieces,
scaled images, and focus. No fixed speedup or FPS is promised across machines.
Run `python run_tests.py` and the tactical runner before changing search behavior;
measure representative positions and compare outcome reports before claiming
improved playing strength. Review analysis is deliberately shallow and can err.
