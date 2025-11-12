# Chess AI with Learning - Code Documentation

## Architecture Overview

This chess application consists of three main components:

### 1. SimpleAI (Lines 60-850)
The chess engine with learning capability.

#### Core Search Algorithms

**Negamax with Alpha-Beta Pruning**
- Minimax variant optimized for zero-sum games
- Alpha-beta pruning eliminates branches that can't improve the result
- Typically reduces search tree by ~90% without changing the result

**Principal Variation Search (PVS)**
- First move searched with full window (most likely best)
- Remaining moves use null window (alpha, alpha+1)
- If null-window search fails high, re-search with full window
- Significantly faster than plain alpha-beta

**Late Move Reductions (LMR)**
- Reduce search depth for "quiet" moves (no capture/check/promotion)
- Only applied after first few moves and at depth ≥ 3
- Re-searches at full depth if reduced search shows promise
- Conservative implementation to preserve accuracy

**Quiescence Search**
- Extends search at leaf nodes to avoid "horizon effect"
- Only searches tactical moves (captures)
- Prevents evaluation of unstable positions (e.g., mid-capture)

**Iterative Deepening with Aspiration Windows**
- Gradually increases depth from 1 to target depth
- Uses narrow window around previous score
- Widens window on fail-low/fail-high
- Provides best move even if time runs out

#### Move Ordering (Critical for Performance)

Move ordering determines which moves are tried first. Good ordering leads to more cutoffs:

1. **Transposition Table Move** (+20,000 bonus)
   - Best move from a previous search of this position
   - Highest priority—usually correct

2. **Killer Moves** (+10,000 bonus)
   - Non-capture moves that caused beta cutoffs at same depth
   - Up to 2 killers stored per depth
   - Often work again in sibling nodes

3. **History Heuristic** (variable bonus)
   - Accumulates depth² for each move that causes cutoff
   - Rewards moves that historically work well

4. **Learned Preference** (+/- 100 bonus, when enabled)
   - Based on win/loss/draw statistics from past games
   - Small bonus to avoid overriding evaluation
   - Gentle nudge toward historically successful moves

5. **MVV-LVA Captures** (+200 + victim value)
   - Most Valuable Victim - Least Valuable Attacker
   - Queen captures pawns before pawns capture queens

6. **Special Moves**
   - Queen promotions: +1200
   - Other promotions: +900
   - Castling: +80
   - Checks: +40

#### Evaluation Function

The evaluation assigns a score (in centipawns) to a position:

**Material** (60-70% of score)
- Pawn: 100
- Knight: 320
- Bishop: 330
- Rook: 500
- Queen: 900
- King: 20,000 (infinite value)

**Piece-Square Tables** (15-20% of score)
- Positional bonuses for piece placement
- Example: Knights prefer center, kings hide in corner (middlegame)

**Mobility** (~5-10% of score)
- Number of legal moves available
- More options = better position

**King Safety** (~5-10% of score, middlegame only)
- Penalized for exposed king in center
- Bonus for castled position

**Pawn Structure** (~5% of score)
- Penalties for doubled, isolated, backward pawns
- Bonuses for passed pawns

**Special Bonuses**
- Bishop pair: +30 (they complement each other)

#### Learning System

**Data Structure:**
```json
{
  "fen_position|move_uci": {
    "w": 5,    // wins when this move was made
    "l": 2,    // losses
    "d": 1     // draws
  }
}
```

**Learning Flow:**
1. **During Game:** Each AI move is logged as (position, move, color)
2. **Game End:** Result is applied to all logged moves
   - Win: increment 'w' for that color's moves
   - Loss: increment 'l' for that color's moves
   - Draw: increment 'd' for both sides' moves
3. **Persistence:** Saved to `ai_learn.json` immediately
4. **Export:** Human-readable `ai_learn_readable.json` auto-generated

**Winrate Calculation:**
```python
winrate = (wins + 0.5 * draws) / total_games
ordering_bonus = (winrate - 0.5) * 200  # -100 to +100
```

**Usage:**
- 60% winrate → +20 bonus (slight preference)
- 50% winrate → 0 bonus (neutral)
- 40% winrate → -20 penalty (slight avoidance)

**Why It Works:**
- Doesn't override evaluation (bonus is small)
- Speeds up search by trying good moves first
- Improves over time without changing engine logic
- Works in all modes (PvP, PvAI, AI vs AI)

### 2. GameController (Lines 850-1900)
GUI coordinator handling user input, AI threading, and game flow.

#### Key Responsibilities

**Game State Management**
- Maintains chess.Board (python-chess library)
- Tracks selected square, move history, game mode
- Handles move validation (python-chess ensures legality)

**AI Threading**
- Runs AI search in background thread to keep UI responsive
- `run_ai_move()`: Worker thread that computes move
- `_finish_ai_move()`: Main thread callback that updates GUI
- Prevents UI freezing during long searches

**UI Coordination**
- BoardView: Visual chess board
- Control panel: Scrollable with all features
- Mode selector: Player vs Player, Player vs AI, AI vs AI
- Learning panel: Show/Export/Import/Reset learning
- Engine panel: External engine (Stockfish) integration

**Learning Integration**
- Calls `ai.finalize_game(result)` on checkmate/stalemate
- Displays "Why this move" explanation after AI moves
- Shows learned stats for current position on request
- Exports/imports learning files

#### Game Modes

**Player vs Player**
- Both sides controlled by manual input
- No AI intervention

**Player vs AI**
- Human plays one side (default: white)
- AI automatically moves after human
- Depth configurable (1-6)

**AI vs AI**
- Both sides automated
- Chains AI moves until game ends
- Manual input disabled
- Great for training/testing learning

### 3. Learning UI Features

#### Use Learning Bias Toggle
- Enables/disables learned bonus in move ordering
- Doesn't affect saved data
- Can compare AI with/without learning

#### Show Position Button
Opens dialog showing learned stats for current legal moves:
```
Move   Games   Winrate   W  L  D   Ordering bonus
e2e4     17     0.647    11 6  0   +29
d2d4     12     0.500     6 6  0   +0
```

#### Export Button
Saves human-readable JSON:
```json
{
  "meta": {
    "version": 1,
    "updated": "2025-11-12 14:30:00",
    "total_positions": 45,
    "total_entries": 203
  },
  "positions": {
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR": {
      "moves": {
        "e2e4": {
          "wins": 11,
          "losses": 6,
          "draws": 0,
          "games": 17,
          "winrate": 0.647,
          "ordering_bonus": 29
        }
      }
    }
  }
}
```

#### Import Button
- Merges learning from another file
- Accepts both raw and readable formats
- Adds counts (doesn't replace)
- Useful for:
  - Sharing learning between machines
  - Combining datasets from multiple sources
  - Bootstrapping with pre-trained data

#### Reset Button
- Clears all learning data
- Keeps game functional (no data = no bias)
- Use to start fresh or test unbiased play

### 4. Performance Optimization Summary

**Search Improvements:**
- PVS: ~2-3x faster than plain alpha-beta
- LMR: ~1.5-2x faster at high depths
- Transposition Table: ~3-5x fewer nodes (hit rate ~70-90%)
- Killer Moves: ~20-30% fewer nodes
- History Heuristic: ~10-15% fewer nodes
- **Combined:** ~10-20x faster than naive minimax at depth 5-6

**Learning Impact:**
- Ordering bonus: ~5-10% faster (better move ordering)
- No accuracy loss (evaluation unchanged)
- Accumulates over games

**Typical Performance (depth 4):**
- Without optimizations: ~100,000 nodes, 10-20 seconds
- With all optimizations: ~5,000-10,000 nodes, 0.5-2 seconds

### 5. File Structure

**Persistent Files:**
- `ai_learn.json` - Raw learning database (auto-saved)
- `ai_learn_readable.json` - Human-friendly export (auto-generated)
- `config.json` - Settings and statistics (if ConfigManager available)

**Source Files:**
- `game_controller.py` - Main file (this one) with AI and GUI
- `board_view.py` - Visual board component
- `enhanced_board_view.py` - Extended board with animations
- `constants.py` - Colors, themes, piece symbols
- `engine_manager.py` - UCI engine interface (Stockfish)
- `config_manager.py` - Persistent settings
- `sound_manager.py` - Move sound effects
- `chess_clock.py` - Time controls
- `image_generator.py` - Fallback piece images

### 6. Technical Notes

**Thread Safety:**
- AI search runs in daemon thread
- Board updates scheduled via `master.after()` to main thread
- Learning database updates only on main thread

**Error Handling:**
- All methods wrapped in try/except for robustness
- Silent failures for non-critical features (sounds, images)
- User notified of critical errors (save/load failures)

**Chess Rules:**
- python-chess library enforces all FIDE rules
- Legal move generation handles:
  - Normal moves, captures, en passant
  - Castling (kingside/queenside, checks legality)
  - Promotion (with UI dialog to choose piece)
  - Check, checkmate, stalemate detection
  - Threefold repetition, fifty-move rule

**Performance Considerations:**
- Iterative deepening allows early cutoff
- Background threading keeps UI responsive
- Transposition table grows unbounded (could add size limit)
- Learning database grows indefinitely (consider pruning old entries)

### 7. Extending the System

**Adding New Heuristics:**
1. Add bonus in `_move_score()` or `_order_moves()`
2. Test impact on speed and accuracy
3. Tune bonus magnitude

**Improving Learning:**
- Add position similarity (transpositions, symmetry)
- Weight recent games more heavily (decay old results)
- Learn evaluation corrections (not just ordering)
- Add opening book integration with learning

**UI Enhancements:**
- Live search statistics (nodes/sec, depth progress)
- Move quality indicator (book/learned/calculated)
- Analysis board (engine evaluation overlay)
- Game replay with learning annotations

### 8. Common Pitfalls

**Performance:**
- Depth 5+ can be slow without optimizations
- Ensure move ordering is effective (monitor cutoff rate)
- Transposition table hit rate should be >70%

**Learning:**
- Too large bonus overrides evaluation (keep < 100)
- Need many games for statistical significance (>10 per position)
- Import/export formats must match schema

**Threading:**
- Never update tkinter widgets from worker thread
- Use `master.after()` to schedule UI updates
- Set daemon=True on background threads

**Chess Logic:**
- Let python-chess handle legality checks
- Don't duplicate move generation
- Trust checkmate/stalemate detection

## Quick Reference

**Starting a Game:**
1. Select mode (Player vs Player / Player vs AI / AI vs AI)
2. Set AI depth (3 = fast, 5 = strong, 6 = slow)
3. Optionally enable learning bias
4. Play!

**Viewing Learning:**
1. Click "Show Position" to see learned stats
2. Click "Export" to save readable file
3. Open file in text editor or JSON viewer

**Improving AI:**
1. Play many games (or run AI vs AI overnight)
2. Learning accumulates automatically
3. Export to backup progress
4. Compare with "Use Learning Bias" on/off

**Debugging:**
1. Check console for error messages
2. Verify learning files exist and are valid JSON
3. Test with learning disabled to isolate issues
4. Use depth 3-4 for faster iteration

## License & Attribution

This system uses:
- **python-chess** by Niklas Fiekas (GPL-3.0)
- **Tkinter** (Python standard library)
- **PIL/Pillow** for image handling (optional)

The AI implements well-known algorithms from chess programming literature:
- Negamax: Classic minimax variant
- Alpha-beta pruning: McCarthy et al., 1956
- PVS: Tony Marsland, 1983
- LMR: Fruit chess engine, 2005
- Piece-square tables: Chess programming community

The learning system is a lightweight custom implementation inspired by:
- Reinforcement learning (outcome-based rewards)
- Experience replay (storing game history)
- Temporal difference learning (credit assignment)
