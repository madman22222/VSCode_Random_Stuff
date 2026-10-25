# Review of the three supplied chess PDFs

Reviewed October 25, 2026 against the shared source used for the Windows and
VS Code editions. This is a compatibility and representative regression review,
not a certification that the engine solves every position in the books.

## Sources and review scope

| Supplied file | Scope / interpretation |
| --- | --- |
| `chess_cheat_sheet_pages.pdf` | 8 pages: board setup, moves, endings, special moves, basic principles and motifs |
| `The Complete Idiot'S Guide To Chess PDF.pdf` | 390 pages; the file identifies itself as a Bookey summary, with summaries, questions, repeated material and promotional pages. It is not treated as a verified full original textbook. |
| `TacticsCourse.pdf` | 84 pages: notation, short games, motifs, combinations, calculation and mating attacks |

Text was extracted across all 482 PDF pages and indexed by topic. Selected diagrams
were visually inspected; custom diagram fonts in the tactics course do not extract
reliably as board positions. Rules and representative factual move sequences were
checked with legal boards and regression tests. This does not verify every diagram,
exercise answer, historical statement or recommended variation. The PDFs themselves
are not copied into the public repository or redistributed in either edition.

## Compatibility map

| Material | Program support / evidence |
| --- | --- |
| Initial board, White first, piece moves and blocked paths | python-chess legality, board orientation, click/focus and setup regressions |
| Castling, immediate en passant, four promotion choices | Enforced by legal move generation; tests cover lost rights, unsafe king transit, an attacked rook, expired en passant and underpromotion |
| Check, mate, stalemate | Enforced and distinguished; test positions check both endings |
| Flag fall and insufficient mating material | Corrected: a nonflagging bare king does not win on time. Material detection is conservative, not a general solver for every dead/fortress position. |
| Resignation / draw agreement | Added to Support & study. Draw agreement requires Two players and at least one move by each player; no AI draw negotiation is simulated. |
| Repetition and move-count draws | The app deliberately auto-accepts claimable draws in casual play; it is not a tournament arbiter implementation. Search checks preserve that policy. |
| Algebraic notation / short games | PGN/SAN replay and review work. Three representative course games from PDF pp.10–13 replay legally, including en passant and disambiguation. Erroneous PGNs are rejected rather than silently loading a truncated game. |
| Recording and reviewing games | PGN now preserves results and loaded headers; declared endings are retained in review exports. Recovery does not reopen a finished declared game. |
| Forks, pins, skewers, discoveries | Rules allow them; bounded search may find them. A new original `reference-themes.json` practice pack demonstrates these motifs without copying the course diagrams. |
| Multi-move combinations, decoys, clearance, interference, overloading, zwischenzug, mating nets | Can be played/reviewed as legal games. No dedicated multi-reply puzzle curriculum or guarantee of finding every solution within a small search budget. |
| Material, development, center, king safety, pawn structures and endgames | Heuristic evaluation represents some principles. These are situational guidance, not additional legality rules or promises of perfect strategic/endgame play. No tablebase-perfect endings are claimed. |
| Learning from the PDFs | No direct PDF/text training exists. Move memory learns recorded game outcomes; the supported study inputs are PGN, FEN and validated JSON puzzle packs. |
| Tournament administration, touch-move, arbiter penalties, ratings, history and biographies | Outside this desktop app's enforcement scope; these are not automatically imported as software behavior. |

## Corrections and cautions in the references

- The summary's p.18 describes capturing a king; legal chess ends at checkmate,
  and a king is never captured. Its p.25 promotion wording is too broad: only
  queen, rook, bishop or knight is permitted, not another pawn or king.
- Cheat sheet p.4 needs the condition that a stalemated player is **not in check**.
  The same page's material wording should not be read as “cannot force mate”:
  inability to force a win is not the same as impossibility of any legal mate.
- Cheat sheet pp.3–4 simplify time losses and claimable draws. FIDE Articles 6.9,
  9.2–9.3 distinguish the timeout exception and draw claims. This app documents its
  automatic-claim policy; fivefold repetition and the 75-move rule are also handled
  by python-chess. Full dead-position detection and tournament procedures remain limits.
- Castling direction should be understood by board coordinates and orientation,
  not a fixed screen direction. A rook being attacked does not by itself forbid castling.
- Course p.7 uses historical notation such as `++` and long disambiguation. Use
  standard PGN/SAN when typing/importing games; PDF prose and diagram glyphs are
  not a machine-readable PGN file. Answer-only exercises need their starting FEN.
- General advice such as early castling, gaining material or counting attackers
  is not an unconditional move-selection rule. Checks, pins and intermediate moves
  can invalidate a simplistic material count.

Rules cross-check: [FIDE Laws of Chess](https://handbook.fide.com/chapter/E012023),
particularly 3.7–3.8, 5.2, 6.9 and 9.2–9.6. This is an app behavior review, not an
assertion of tournament certification.

## Bugs and optimization addressed

Flag adjudication now goes through the same once-only statistics, learning,
autosave and result pipeline as other endings. An expired clock cannot receive an
increment or accept a new human/AI move. Starting training pauses the live clock.
PGN load rejects parse errors/invalid positions before replacing the live game.
Manual/automatic PGN saves share one builder and keep result/header information.

Search avoids expensive prospective-draw checks when history/counters make them
impossible, and avoids checking the same terminal node twice at the normal-to-
quiescence boundary. Quiescence now honors the same draw policy as normal search.
The retained [A/B harness](../benchmarks/search_draw_ab.py) compares against full
python-chess checks; [raw results](../benchmarks/search-draw-ab.json) record five
runs per position, identical moves/node counts, and semantic checks on 400 seeded
positions. This is machine-specific performance evidence, not proof of stronger play.

Both editions use `chess/main.py`; see [VS Code setup](../VSCODE_GUIDE.md). The release
pipeline tests both extracted ZIPs from the same commit before publishing them together.
