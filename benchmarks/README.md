# Performance measurement

Run from the repository root, with the same Python, machine, settings, and idle
workload for before/after comparisons:

```bash
python benchmarks/run.py --output before.json --repeats 5 --nodes 2000
python benchmarks/run.py --output desktop.json --repeats 5 --nodes 2000 --redraw
```

The redraw option needs a display. Workloads are hand-built in `positions.json`.
Reports include revision/dirty state, platform/processor, Python, node/depth budget,
per-position samples/median/peak traced memory and search metrics. Tracemalloc adds
substantial overhead; compare like with like. The five-second ceiling means a
slow machine may not finish the same depth. These are performance measurements,
not Elo or strength estimates. Use tactics and paired comparisons for behavior.

Keep raw reports when tuning. Profile the workload before choosing an optimization;
change one thing, repeat measurements, and reject regressions or inconclusive wins.
Do not compare a traced benchmark with an untraced ad-hoc timer.

```bash
python benchmarks/compare_evaluation.py --output evaluation-ab.json
python benchmarks/check_memory_migration.py --output memory-migration.json
```

The first retains the original two evaluation methods, checks equality on 100
seeded legal positions, then compares five runs per workload with equal node
budgets and a generous ceiling. It asserts matching moves and visited nodes.
The committed `evaluation-ab.json` is one local run, not a general speed claim.
The migration smoke report records retained legacy counts, storage and a tiny
paired comparison; mostly cutoff draws make it unsuitable as strength evidence.

`python benchmarks/search_draw_ab.py --output search-draw-ab.json` compares guarded
prospective-draw checks with full reference checks, with matching moves/node counts
and 400 seeded semantic comparisons. The committed report is one machine's timing
data, not a playing-strength result.

## Training reliability soak

```bash
python benchmarks/soak.py --cycles 100 --output soak-results.json
python benchmarks/soak.py --cycles 10000 --output soak-long.json
```

Every cycle trains a real bounded game, reloads persisted memory, resumes counters,
cancels an active trainer, and checks writer-lease release and search/memory caps.
Reports retain platform/Python, elapsed time, games and traced memory samples.
Growing move records are expected to consume memory; samples alone do not prove
absence of leaks. The checked-in `soak-smoke.json` records a local 100-cycle run;
CI repeats 12 cycles per Linux Python version. Longer runs are opt-in and use
temporary profiles. The test suite also forces abrupt process exit between
checkpoint writes and tests recovery plus externally changed memory rejection.

GUI/CLI comparisons now use `chess/assets/evaluation/independent-v1.json`: 16
original positions across opening, middlegame, tactical and endgame categories,
separate from all self-play opening seed prefixes and practice exercises.
Seeded random selection with replacement keeps color-paired trials comparable.
Reports expose the corpus SHA-256, root-memory overlap, budgets, category totals
and per-game results. Roots may be encountered during self-play; this is an
independent starting suite, not a permanently uncontaminated training holdout.
A small or mostly cutoff-draw run cannot support playing-strength claims.
