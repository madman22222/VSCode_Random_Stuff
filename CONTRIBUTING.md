# Contributing to Chess Studio

Start with the [Kanban](KANBAN.md) and an issue with focused acceptance criteria.
Avoid working on the same item as another contributor. Update its board status
in your implementation PR; link the issue and explain the user-visible change.

## Setup and validation

Use Python 3.10+ with Tkinter, a virtual environment, and `chess/requirements.txt`.
Run commands from the repository root:

```bash
python run_tests.py
python chess/tactical_suite.py --depth 2 --nodes 12000
python chess/main.py --diagnostics-report diagnostics.json
```

Desktop tests and diagnostics need a display (`xvfb-run -a` works on Linux).
Skipped desktop tests are not desktop validation. Packaging changes also require
the actual Windows extracted-ZIP smoke check; see [packaging](packaging/README.md).
For performance work, capture a [benchmark baseline](benchmarks/README.md) first.

Preserve the live game during study/practice/review, use bounded independent
search state in workers, and send Tk updates through the main-thread queue.
Mutable files belong in the data profile; bundled assets are read-only resources.
Never silently replace unreadable user data. Do not submit real personal profiles,
logs, or training memory as test fixtures. Prefer hand-built minimal positions.

## PR checklist

- [ ] Concrete issue goal and acceptance criteria addressed.
- [ ] Relevant source/desktop/package checks passed, with limitations stated.
- [ ] Saves, migration, cancellation and writer contention considered where affected.
- [ ] User/developer instructions and Kanban updated.
- [ ] Performance/strength claims supported by reproducible evidence.

## Release checklist

- [ ] Merge only after required source/desktop/package CI succeeds.
- [ ] Record exact revision and reviewed dependency constraints; include notices/source.
- [ ] Test the extracted ZIP from another folder with Python removed from child PATH.
- [ ] Check data upgrade/rollback instructions and bundled README.
- [ ] Verify release assets, build metadata and SHA-256 match.
- [ ] Record manual Windows DPI/accessibility checks separately from automated tests.

Report bugs with the issue form and About/diagnostics build information. Reports
exclude logs and games by default; review all exported content before sharing.
