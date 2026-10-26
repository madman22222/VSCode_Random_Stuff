# Training performance and correctness

Run from a Git checkout with the reviewed dependencies:

```bash
python benchmarks/training_performance.py --output training-performance.json
python benchmarks/soak.py --cycles 250 --output training-soak.json
```

The A/B script loads the immutable baseline at `e2e5f0a9147c392dcd41298a0334dfd7cd70ee92`
using Git; fetch full history first. Reference code is used only in this developer
benchmark, never as a second application edition. Both released editions use
`chess/simple_ai.py` and `chess/training_ai.py`.

## Optimized paths

- Pawn structure uses equivalent bitboard masks instead of repeated pawn scans.
- Material/positional evaluation avoids temporary Piece objects and dictionaries;
  evaluation weights, mobility rules and phase thresholds are unchanged.
- Bounded per-search static-evaluation and pawn caches reuse exact results.
  Static keys include color, castling, en passant, promoted pieces, Chess960 mode
  and opening phase. Draw/repetition checks still run independently at each node.
- Search reuses a terminal check already completed at that node, while public
  evaluation still handles terminal positions and custom evaluation overrides.
- Quiescence generates captures/promotions directly, retaining original move
  order, all check evasions, en passant and underpromotions.
- Move ordering reuses the same full FEN rather than encoding it twice per node.
- The trainer updates its position index from completed-game logs; pruning and
  resume rebuild the index. Learned counts and exploration are retained.
- Checkpoints reuse the last published fingerprint only while owning the writer
  lease. Resume/new ownership revalidate canonical data; manual saves read it anew.
- JSON is serialized in one write; the recovery journal uses compact JSON.
  Gzip level 1 reduces save CPU at the cost of a larger compressed memory file.
  Existing plain/gzip profiles remain readable, with identical recovered records.

Static caches are capped at 4,096 evaluations and 1,024 pawn structures per engine
and reset for each search. Faster serialization allocates a temporary JSON string;
the benchmark separately measures peak traced checkpoint allocations. Atomic
replacement, writer leases and interrupted-save recovery remain in place.

## Evidence and its limits

The performance workflow runs on Linux and Windows, retaining raw reports:

- cProfile output for real self-play and 20 search positions identifies CPU costs.
- Evaluation and pawn scores must match on 1,000 seeded legal positions.
- Five timing trials per workload alternate baseline/candidate order, with depth 4,
  3,000 nodes and a generous 60-second ceiling. Moves, scores, completed depth and
  visited nodes must match exactly.
- Five checkpoint trials use 50,000 synthetic, schema-valid historical records,
  check round-trip equality, and report compressed/journal size and traced peak
  allocation outside the timed trials.
- Three six-game self-play trials per implementation use equal 80-node move budgets,
  seeded exploration and 10,000 starting records. Outcomes and every learned count
  must match. Position totals and persistence are checked.
- Extended 250-cycle tests exercise training, resume, cancellation, writer-lease
  release, cache bounds and saved memory. The regular source/desktop suite includes
  atomic-write failures and abrupt process-exit recovery, and both ZIPs are tested.

Timing gains depend on hardware, positions, memory size, batch size and search
budget. Short synthetic workloads are not an Elo or strength test. In time-limited
training a faster evaluator may spend the same allotted time searching more nodes;
games/second need not increase by the fixed-work speedup. Default search depth,
move budgets, exploration and chess rules are retained.

For throughput, keep a sensible batch size (for example 100) rather than saving
every game. Larger batches reduce I/O but leave more completed games between
checkpoints if the process crashes. Stop and save still checkpoints completed work.
Back up the whole profile before experiments, and keep the recovery journal.
