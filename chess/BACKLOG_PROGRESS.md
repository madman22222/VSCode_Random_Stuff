# Backlog implementation record

The implementation addresses 17 of the 20 planned improvement issues. Completion
on the Kanban remains subject to source/desktop and actual Windows bundle checks.

| Issue | Implementation / evidence |
| --- | --- |
| #9 | ProfileStore archives, hashes, bounded validation, writer leases, preview, rollback and GUI restore |
| #10 | Rotating logs, callback/save failures, About metadata, paths/counts and reviewed report export |
| #12 | Versioned corpus, search/redraw/traced-memory harness and retained raw A/B results |
| #13 | Bounded compressed JSON, preferences/checkpoint/learning versions, atomic import staging and corrupt-file preservation |
| #14 | Additional underpromotion, illegal en-passant, repetition, session, maintenance and import rollback regressions |
| #15 | Dashboard subpages, checkpointed/completed totals, recent outcomes, throughput and bounded-run estimates |
| #16 | Named persisted memory profiles and per-profile comparison history with view/export/delete |
| #17 | Version-3 contextual keys, unchanged legacy retention, disabled legacy scoring approval and migration smoke report |
| #18 | Profiled evaluation tuning with retained reference methods, equal evaluation/move/node checks and raw timings |
| #19 | Bounded FIFO table, configurable search/learning limits, fork propagation and observable counts |
| #20 | Validated attributed local puzzle packs, persistence, four supplied themed cases and underpromotion practice |
| #21 | Quick/Deeper review budgets, mate-score uncertainty and independent annotated PGN export |
| #23 | Extracted training/comparison callbacks and support/profile/study UI into cohesive modules |
| #24 | Reviewed build constraints, dependency-update proposals, recorded package versions, notices and source inclusion |
| #25 | Explicit asynchronous release check, revision comparison and backup-first upgrade instructions; no automatic replacement |
| #27 | Validated FEN study/copy isolated from game, logs and recovery; game restored on return |
| #28 | Bug/feature forms, contribution/validation/release checklists and diagnostics guidance |

## Work that remains open

- **#11:** Linux desktop checks passed, and training controls are split into smaller
  pages. Real Windows 100–200% scaling, drivers and multi-monitor behavior still
  need the [manual verification checklist](MANUAL_VERIFICATION.md).
- **#22:** Keyboard interaction is tested and focused square/piece feedback is
  visible. Real NVDA/Narrator announcements, full workflow tab order and display
  contrast still require hands-on assistive-technology testing.
- **#26:** [Signing and native packaging plan](../packaging/PORTABILITY_PLAN.md)
  records the next steps. A paid signing account/certificate and native macOS/Linux
  package builds have not been supplied or validated. No support is claimed.

No outcome comparison here proves improved chess strength. The migration experiment
is tiny and cutoff-heavy. Evaluation timings describe one machine and workload.
