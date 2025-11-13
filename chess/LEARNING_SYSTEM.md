# AI Learning System Documentation

## Overview

The chess AI includes a **persistent learning system** that learns from every game played. The AI remembers which moves led to wins, losses, or draws, and uses this information to improve its play over time.

## How It Works

### 1. Move Recording
During gameplay, the AI records every move it makes along with:
- The position (FEN notation)
- The move played (UCI notation)
- Which side was moving

### 2. Game Outcome Processing
When a game ends (checkmate, stalemate, or draw), the system:
- Reviews all moves made by the AI during that game
- Updates win/loss/draw statistics for each (position, move) pair
- Saves the data to disk automatically

### 3. Learning Application
In future games, the AI:
- Checks its learned database for the current position
- Applies a small bonus (+/- 100 centipawns) to move ordering based on historical success
- Prefers moves that have led to wins in the past
- Avoids moves that have led to losses

### 4. Data Persistence
Learning data is stored in two files:
- **`ai_learn.json`**: Raw database (machine-readable)
- **`ai_learn_readable.json`**: Human-readable export with statistics

## Using the Learning System

### In the GUI

The **Learning** panel in the GUI provides full control:

1. **Use Learning Bias** checkbox
   - Enable/disable learning influence on move selection
   - Default: ON

2. **Learning Status Display**
   - Shows number of positions learned
   - Shows total games analyzed
   - Updates automatically after each game

3. **Show Position** button
   - View learned data for current board position
   - See winrates and ordering bonuses for each legal move

4. **Export** button
   - Save learning data to a file
   - Share learned data between computers
   - Backup your AI's knowledge

5. **Import** button
   - Load learning data from a file
   - Merge with existing knowledge (doesn't overwrite)
   - Import data from other sources

6. **Reset** button
   - Clear all learning data
   - Start fresh (cannot be undone!)

### Learning Modes

The AI learns in **all game modes**:

- **Player vs AI**: AI learns from games against you
- **AI vs AI**: AI learns from self-play (fastest learning!)
- **Engine vs AI**: AI learns from games against Stockfish

For fastest learning, use **AI vs AI mode with auto-restart** enabled.

## Learning Statistics

### Viewing Position Data

Click **Show Position** to see learned data for the current board:

```
Move   Games   Winrate   W  L  D   Ordering bonus
e2e4      50     0.680   34 12  4   +36
d2d4      30     0.533   16 11  3   +7
c2c4      10     0.400    4  5  1   -20
```

- **Games**: How many times this move was played
- **Winrate**: Win rate (0.0 = always loses, 1.0 = always wins)
- **W/L/D**: Wins, losses, draws for this move
- **Ordering bonus**: Centipawns added to move ordering

### Interpretation

- **Positive bonus**: Move has worked well historically (try it more)
- **Negative bonus**: Move has performed poorly (avoid it)
- **Zero bonus**: No clear pattern (50% winrate)

## Learning Process

### Example Scenario

1. **Game 1**: AI plays e2-e4 in starting position → Loses
   - Data: `starting_position|e2e4` → {w:0, l:1, d:0}
   - Ordering bonus: -100 (avoid this move)

2. **Game 2**: AI tries d2-d4 instead → Wins
   - Data: `starting_position|d2d4` → {w:1, l:0, d:0}
   - Ordering bonus: +100 (prefer this move)

3. **Games 3-10**: AI accumulates more data
   - Eventually: `starting_position|e2e4` → {w:15, l:5, d:2}
   - New ordering bonus: +36 (move is actually good!)

The AI **self-corrects** as it gains more experience.

## Advanced Features

### Exporting Learning Data

The exported readable format shows:
```json
{
  "version": "1.0",
  "timestamp": "2025-11-13T18:00:00Z",
  "total_positions": 1523,
  "positions": {
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR": {
      "moves": {
        "e2e4": {
          "wins": 45,
          "losses": 23,
          "draws": 12,
          "games": 80,
          "winrate": 0.638,
          "ordering_bonus": 28
        }
      }
    }
  }
}
```

### Importing/Merging Data

When importing:
- Statistics are **added** (not replaced)
- Allows combining data from multiple sources
- Example: Import data from 1000 AI vs AI games to jumpstart learning

### Learning in AI vs AI Mode

Best practice for training:
1. Set mode to **AI vs AI**
2. Enable **Auto-restart on game end**
3. Let it run for 50-100 games
4. Export the learned data
5. Import into your main learning database

## Performance Impact

### Memory
- Minimal: ~1KB per 10 learned positions
- Typical size after 100 games: ~50KB

### Speed
- Negligible: Learning lookup is O(1) hash table access
- Adds ~0.001 seconds per move

### Accuracy
- Improves with more games
- 10 games: Initial patterns
- 50 games: Useful biases
- 100+ games: Strong preferences

## Tips for Effective Learning

1. **Play diverse games**: Different opponents = better learning
2. **Use AI vs AI**: Fastest way to accumulate data
3. **Regular exports**: Back up your AI's knowledge
4. **Import community data**: Share and learn from others
5. **Reset if needed**: Clear bad data and start fresh

## Technical Details

### Storage Format
```python
{
  "position_fen|move_uci": {
    "w": wins,    # int
    "l": losses,  # int
    "d": draws    # int
  }
}
```

### Ordering Bonus Calculation
```python
winrate = (wins + 0.5 * draws) / total_games
bonus = (winrate - 0.5) * 200  # Range: -100 to +100
```

- 0% winrate → -100 bonus
- 50% winrate → 0 bonus
- 100% winrate → +100 bonus

### Move Ordering Integration
The learned bonus is **added to move ordering score** but:
- Does NOT override evaluation (evaluation is still primary)
- Only affects move ordering (which moves to search first)
- Better move ordering → more alpha-beta cutoffs → faster search

## Limitations

1. **Position-specific**: Learning is tied to exact positions
2. **Not transposition-aware**: Similar positions are treated separately
3. **Small influence**: Bonus is intentionally limited to avoid overfitting
4. **Requires volume**: Needs many games for statistical significance

## Future Enhancements (Ideas)

- Pattern recognition across similar positions
- Time-based decay (forget old data gradually)
- Separate learning for different time controls
- Opening repertoire building
- Endgame specialization

## Conclusion

The learning system makes the AI **adaptive and personalized**. Over time, it will:
- Learn from mistakes
- Develop preferences
- Adapt to your playing style
- Improve its opening repertoire

**The more you play, the smarter it gets!** 🧠♟️

---

*For questions or issues, see the main README.md or check the GUI tooltips.*
