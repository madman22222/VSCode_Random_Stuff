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
