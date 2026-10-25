# Chess Studio Kanban

[Project README](README.md) · [Open issues](https://github.com/madman22222/VSCode_Random_Stuff/issues) · [Merged work](https://github.com/madman22222/VSCode_Random_Stuff/pulls?q=is%3Apr+is%3Amerged)

Repository board populated on October 25, 2026. This is a version-controlled
Markdown Kanban with real issue cards, rather than a GitHub Projects drag-and-drop
view. Each proposed issue contains its goal, acceptance checklist, and priority.
Completed cards link to merged implementation evidence instead of creating
retroactive duplicate issues.

## Current status

Updated October 25, 2026: **17 improvement issues implemented and validated** in
[PR #42](https://github.com/madman22222/VSCode_Random_Stuff/pull/42). The board now
contains **43 delivered feature/planning cards** (26 earlier cards plus 17 improvements).
No implementation or review task is currently in progress.

Validation: **103 tests** passed on a Linux virtual desktop and in Windows source
checks; Linux Python 3.10/3.11 CI also passed. All **11 diagnostic groups** passed.
The actual extracted Windows ZIP passed frozen diagnostics and CLI checks with
Python removed from the child PATH. Evidence:
[source/desktop CI](https://github.com/madman22222/VSCode_Random_Stuff/actions/runs/40222207466),
[portable build/smoke CI](https://github.com/madman22222/VSCode_Random_Stuff/actions/runs/40222207716).
See [implementation details and limits](chess/BACKLOG_PROGRESS.md).

**Three cards remain open:** #11 needs real Windows DPI/driver checks; #22 needs
hands-on screen-reader/accessibility verification; #26 needs native package work
and owner-provided signing resources. Plans and partial automated checks do not
count as completing those cards. No chess-strength improvement is claimed.

## Board

| Backlog / verification (3) | Ready (0) | In progress (0) | Review / test (0) | Done (43) |
| --- | --- | --- | --- | --- |
| **P1** [#11 Validate Windows display scaling and small-window layouts](https://github.com/madman22222/VSCode_Random_Stuff/issues/11) — external verification pending | — | — | — | [Repair GUI startup and restore the dedicated AI/training modules](https://github.com/madman22222/VSCode_Random_Stuff/pull/3) |
| **P2** [#22 Audit keyboard navigation and assistive-technology support](https://github.com/madman22222/VSCode_Random_Stuff/issues/22) — external verification pending | — | — | — | [Fix search depth, move budgets, timeout board restoration, and evaluation errors](https://github.com/madman22222/VSCode_Random_Stuff/pull/3) |
| **P3** [#26 Explore signed Windows releases and macOS/Linux portable packages](https://github.com/madman22222/VSCode_Random_Stuff/issues/26) — external verification pending | — | — | — | [Record self-play outcomes; stop at requested game counts and save/reload reliably](https://github.com/madman22222/VSCode_Random_Stuff/pull/3) |
| — | — | — | — | [Fix the test runner and establish source CI](https://github.com/madman22222/VSCode_Random_Stuff/pull/3) |
| — | — | — | — | [Make the board square and responsive with scaled images and correct hit detection](https://github.com/madman22222/VSCode_Random_Stuff/pull/4) |
| — | — | — | — | [Replace the scrolling control canvas to remove its ghosting/redraw path](https://github.com/madman22222/VSCode_Random_Stuff/pull/4) |
| — | — | — | — | [Apply consistent tabs, themes, spacing, and debounced resizing](https://github.com/madman22222/VSCode_Random_Stuff/pull/4) |
| — | — | — | — | [Add guided modes, difficulty, human Black, and Watch AI start/pause](https://github.com/madman22222/VSCode_Random_Stuff/pull/5) |
| — | — | — | — | [Add background hints, thinking status, legal/illegal feedback, and draw outcomes](https://github.com/madman22222/VSCode_Random_Stuff/pull/5) |
| — | — | — | — | [Add paired Undo, completed-game memory/statistics rollback, and custom-start PGN support](https://github.com/madman22222/VSCode_Random_Stuff/pull/5) |
| — | — | — | — | [Add the training dashboard with Start, Stop and save, Resume, and visible progress/errors](https://github.com/madman22222/VSCode_Random_Stuff/pull/5) |
| — | — | — | — | [Add varied openings, seeded exploration, persistent counters, and training settings](https://github.com/madman22222/VSCode_Random_Stuff/pull/5) |
| — | — | — | — | [Isolate background searches, discard stale results, and queue UI updates on the main thread](https://github.com/madman22222/VSCode_Random_Stuff/pull/5) |
| — | — | — | — | [Add atomic configuration writes, OS writer leases, bounded search-cache cleanup, and cached ordering keys](https://github.com/madman22222/VSCode_Random_Stuff/pull/5) |
| — | — | — | — | [Add paired baseline comparisons and the Windows source launcher](https://github.com/madman22222/VSCode_Random_Stuff/pull/5) |
| — | — | — | — | [Add seven tactical practice puzzles, progressive hints, and saved solved progress](https://github.com/madman22222/VSCode_Random_Stuff/pull/6) |
| — | — | — | — | [Add budgeted background game review and isolated position navigation](https://github.com/madman22222/VSCode_Random_Stuff/pull/6) |
| — | — | — | — | [Add validated atomic unfinished-game recovery with paused restoration](https://github.com/madman22222/VSCode_Random_Stuff/pull/6) |
| — | — | — | — | [Add larger text, contrast, piece styles, keyboard focus, and accessible board input](https://github.com/madman22222/VSCode_Random_Stuff/pull/6) |
| — | — | — | — | [Add previous-version snapshots, two-opponent comparisons, uncertainty ranges, and gated scoring experiments](https://github.com/madman22222/VSCode_Random_Stuff/pull/6) |
| — | — | — | — | [Reuse unchanged pieces/focus rendering and fix monotonic clock/timer precision](https://github.com/madman22222/VSCode_Random_Stuff/pull/6) |
| — | — | — | — | [Build and publish the Windows ZIP with bundled runtime, GUI and CLI executables](https://github.com/madman22222/VSCode_Random_Stuff/pull/7) |
| — | — | — | — | [Separate resources from writable data; add fallback paths, notices, source archives, and checksums](https://github.com/madman22222/VSCode_Random_Stuff/pull/7) |
| — | — | — | — | [Test the extracted Windows bundle without Python on PATH and publish only after success](https://github.com/madman22222/VSCode_Random_Stuff/pull/7) |
| — | — | — | — | [Refresh all user/developer/asset documentation and add the portable build/release guide](https://github.com/madman22222/VSCode_Random_Stuff/pull/8) |
| — | — | — | — | [Create the populated Kanban, prioritized issues, acceptance checklists, and README link](https://github.com/madman22222/VSCode_Random_Stuff/pull/29) |
| — | — | — | — | **P1** [#9 Add one-click backup and restore for the complete data profile](https://github.com/madman22222/VSCode_Random_Stuff/issues/9) — [PR #42](https://github.com/madman22222/VSCode_Random_Stuff/pull/42) |
| — | — | — | — | **P1** [#10 Add a diagnostics and log export panel](https://github.com/madman22222/VSCode_Random_Stuff/issues/10) — [PR #42](https://github.com/madman22222/VSCode_Random_Stuff/pull/42) |
| — | — | — | — | **P1** [#12 Establish reproducible search and rendering performance benchmarks](https://github.com/madman22222/VSCode_Random_Stuff/issues/12) — [PR #42](https://github.com/madman22222/VSCode_Random_Stuff/pull/42) |
| — | — | — | — | **P1** [#13 Validate and version learning and configuration imports](https://github.com/madman22222/VSCode_Random_Stuff/issues/13) — [PR #42](https://github.com/madman22222/VSCode_Random_Stuff/pull/42) |
| — | — | — | — | **P1** [#14 Expand chess-rule and cancellation regression coverage](https://github.com/madman22222/VSCode_Random_Stuff/issues/14) — [PR #42](https://github.com/madman22222/VSCode_Random_Stuff/pull/42) |
| — | — | — | — | **P2** [#15 Make training progress easier to understand](https://github.com/madman22222/VSCode_Random_Stuff/issues/15) — [PR #42](https://github.com/madman22222/VSCode_Random_Stuff/pull/42) |
| — | — | — | — | **P2** [#16 Save named training profiles and comparison history](https://github.com/madman22222/VSCode_Random_Stuff/issues/16) — [PR #42](https://github.com/madman22222/VSCode_Random_Stuff/pull/42) |
| — | — | — | — | **P2** [#17 Evaluate stronger move-memory keys with a compatibility migration](https://github.com/madman22222/VSCode_Random_Stuff/issues/17) — [PR #42](https://github.com/madman22222/VSCode_Random_Stuff/pull/42) |
| — | — | — | — | **P2** [#18 Tune search only after baseline measurements and tactical checks](https://github.com/madman22222/VSCode_Random_Stuff/issues/18) — [PR #42](https://github.com/madman22222/VSCode_Random_Stuff/pull/42) |
| — | — | — | — | **P2** [#19 Improve bounded transposition and learning-memory management](https://github.com/madman22222/VSCode_Random_Stuff/issues/19) — [PR #42](https://github.com/madman22222/VSCode_Random_Stuff/pull/42) |
| — | — | — | — | **P2** [#20 Expand tactical practice and support validated puzzle packs](https://github.com/madman22222/VSCode_Random_Stuff/issues/20) — [PR #42](https://github.com/madman22222/VSCode_Random_Stuff/pull/42) |
| — | — | — | — | **P2** [#21 Improve review explanations and annotated PGN export](https://github.com/madman22222/VSCode_Random_Stuff/issues/21) — [PR #42](https://github.com/madman22222/VSCode_Random_Stuff/pull/42) |
| — | — | — | — | **P2** [#23 Separate controller UI construction from task and game services](https://github.com/madman22222/VSCode_Random_Stuff/issues/23) — [PR #42](https://github.com/madman22222/VSCode_Random_Stuff/pull/42) |
| — | — | — | — | **P2** [#24 Make portable builds more reproducible and validate dependency updates](https://github.com/madman22222/VSCode_Random_Stuff/issues/24) — [PR #42](https://github.com/madman22222/VSCode_Random_Stuff/pull/42) |
| — | — | — | — | **P2** [#25 Add an update notification and data-safe upgrade walkthrough](https://github.com/madman22222/VSCode_Random_Stuff/issues/25) — [PR #42](https://github.com/madman22222/VSCode_Random_Stuff/pull/42) |
| — | — | — | — | **P3** [#27 Add local FEN setup and position-analysis tools](https://github.com/madman22222/VSCode_Random_Stuff/issues/27) — [PR #42](https://github.com/madman22222/VSCode_Random_Stuff/pull/42) |
| — | — | — | — | **P2** [#28 Improve issue reporting and contribution onboarding](https://github.com/madman22222/VSCode_Random_Stuff/issues/28) — [PR #42](https://github.com/madman22222/VSCode_Random_Stuff/pull/42) |

## Priorities and recommended order

- **P1:** reliability, data protection, and measurement foundations.
- **P2:** usability, maintainability, and improvements backed by measurements.
- **P3:** optional expansion; confirm demand and costs before starting.

The 17 implementation cards are complete. The remaining work requires external verification/resources.
For remaining work, use the [Windows/accessibility checklist](chess/MANUAL_VERIFICATION.md)
and [platform/signing plan](packaging/PORTABILITY_PLAN.md). Dependencies and design
tradeoffs for the implemented batch are in [the progress record](chess/BACKLOG_PROGRESS.md).

## Moving cards

1. Pick a Ready issue, add an owner if desired, and move its row to In progress.
2. Open a linked PR and move the card to Review / test once implementation is ready.
3. Meet the issue checklist and run relevant checks. Desktop work needs a real or
   virtual display; packaged-resource changes also need the extracted-ZIP smoke check.
4. Merge the PR, close the issue, and move its card to Done with the evidence link.
5. Update this file in the same PR so the board and implementation stay aligned.

Keep at most two implementation cards in progress for this home project. If blocked,
record the dependency in the issue and return it to Backlog rather than hiding it.
This Markdown board is manually maintained; closing an issue does not move a row
automatically. Issue checklists track acceptance; the board tracks workflow status.

## Completed-work evidence

| Merged PR | Delivered milestone |
| --- | --- |
| [#3](https://github.com/madman22222/VSCode_Random_Stuff/pull/3) | Working AI chess and self-play training |
| [#4](https://github.com/madman22222/VSCode_Random_Stuff/pull/4) | Responsive UI and removal of the scrolling ghosting path |
| [#5](https://github.com/madman22222/VSCode_Random_Stuff/pull/5) | Guided play, resumable training, comparison, and reliability |
| [#6](https://github.com/madman22222/VSCode_Random_Stuff/pull/6) | Practice, review, recovery, accessibility, and scoring experiments |
| [#7](https://github.com/madman22222/VSCode_Random_Stuff/pull/7) | Self-contained Windows ZIP and tested release pipeline |
| [#8](https://github.com/madman22222/VSCode_Random_Stuff/pull/8) | Documentation refresh |
| [#29](https://github.com/madman22222/VSCode_Random_Stuff/pull/29) | Populated project Kanban, 20 improvement issues, and planning workflow |
| [#42](https://github.com/madman22222/VSCode_Random_Stuff/pull/42) | 17 validated backlog improvements: profile safety, study/support tools, contextual memory, measured tuning and contribution guidance |

Done means delivered in the cited merged PR, not proof of perfect behavior or
increased chess strength. Future verification/enhancement cards intentionally build
on existing features. Historical test counts are in the PRs; current CI is authoritative.
The closed, unmerged historical PR #1 is not counted as delivered work. Unrelated
parking issue #2 remains untouched and is outside this chess board.
