# Chess AI with Learning - Quick Start Guide

## Running the Game

```bash
python game_controller.py
```

## Game Modes

### Player vs Player
- Both players make moves manually
- No AI involvement
- Good for testing or playing with a friend

### Player vs AI
- You play one color (default: White)
- AI plays the other color
- AI automatically responds after your move
- Adjust AI strength with depth slider (1-6)

### AI vs AI
- Both sides automated
- Great for training the AI
- Let it run overnight to accumulate learning data
- Manual moves are ignored in this mode

## AI Strength Settings

**Depth 1-2**: Beginner
- Very fast (~0.1 seconds)
- Makes obvious mistakes
- Good for learning chess

**Depth 3-4**: Intermediate
- Fast (~0.5-2 seconds)
- Plays reasonable chess
- Recommended for most games

**Depth 5**: Advanced
- Moderate speed (~2-5 seconds)
- Strong tactical play
- Good challenge for experienced players

**Depth 6**: Expert
- Slow (~5-20 seconds per move)
- Very strong play
- Only use if you have time

## Learning System

### How It Works

The AI learns from experience by tracking which moves lead to wins/losses/draws.

**During gameplay:**
- AI logs every move it makes
- Records: position + move + whose turn

**After game ends:**
- Updates win/loss/draw statistics
- Saves to `ai_learn.json`
- Auto-exports to `ai_learn_readable.json`

**In future games:**
- Adds small bonus (+/- 100 centipawns) to move ordering
- Doesn't override evaluation, just nudges toward successful moves
- Accumulates over many games

### Learning Controls

#### Use Learning Bias Toggle
- **ON**: AI uses learned bonuses in move ordering (default)
- **OFF**: AI ignores learning, plays purely by evaluation
- Compare performance with toggle on/off!

#### Show Position Button
Shows learned statistics for current position:
- All legal moves
- Games played with each move
- Win/loss/draw breakdown
- Current winrate
- Ordering bonus applied

#### Export Button
Saves human-readable JSON file:
- Choose save location
- View in text editor or JSON viewer
- Share with friends or backup progress

#### Import Button
Merges learning from another file:
- Accepts both raw and readable formats
- Adds counts (doesn't replace existing data)
- Useful for combining datasets

#### Reset Button
Clears all learning data:
- Deletes `ai_learn.json`
- Deletes `ai_learn_readable.json`
- AI continues working (no data = no bias)
- Use to start fresh

### Training Tips

**Quick Training (30 minutes):**
1. Set AI vs AI mode
2. Set depth to 3-4
3. Let it play 5-10 games
4. Check Show Position to see learned data

**Overnight Training:**
1. Set AI vs AI mode
2. Set depth to 4-5
3. Leave running overnight
4. Next day: 50-100 games of data!
5. Export to backup your progress

**Testing Learning:**
1. Reset learning data
2. Play 5 games with learning OFF
3. Note AI's performance
4. Play 5 games with learning ON
5. Compare results

## Understanding the Display

### Why This Move?
After AI moves, you'll see an explanation:
```
Why this move: e2e4 (15 games, 67% winrate, +33 bonus)
```

- **15 games**: Position seen 15 times before
- **67% winrate**: AI won 10, drew 1, lost 4
- **+33 bonus**: Gets +33 centipawns in move ordering

### Move Hints
Hover over pieces or squares to see:
- Legal moves for that piece
- Captures highlighted
- Special moves (castling, en passant, promotion)
- AI's last move explanation (if applicable)

## File Locations

**Learning Data:**
- `ai_learn.json` - Raw database (auto-saved after each game)
- `ai_learn_readable.json` - Human-friendly export (auto-generated)

**Other Files:**
- `config.json` - Settings and statistics (if using ConfigManager)
- `game_controller.py` - Main program (this file)

## Troubleshooting

### AI is too slow
- Reduce depth to 3 or 4
- Disable fancy board animations (if available)
- Close other programs

### AI makes bad moves
- Increase depth to 5 or 6
- Check if learning data has bad patterns (reset if needed)
- Ensure "Use Learning Bias" is appropriate (try toggling)

### Learning data corrupted
1. Click "Reset" in Learning panel
2. Start fresh
3. Let AI play 10+ games before judging

### Can't import learning file
- Ensure file is valid JSON
- Check it came from this program
- Try exporting a fresh file and comparing format

### Game freezes during AI thinking
- This is normal! AI runs in background
- UI stays responsive, but moves are queued
- For very long thinks (depth 6), be patient

## Advanced: Understanding the Numbers

### Evaluation Scores
- Measured in "centipawns" (1/100 of a pawn)
- +100 = white is up one pawn
- -300 = black is up three pawns (or a knight)
- +900 = white is up a queen

### Ordering Bonuses
- TT best move: +20,000 (transposition table hit)
- Killer move: +10,000 (caused cutoff before)
- Queen promotion: +1,200
- Other promotion: +900
- Capture (MVV-LVA): +200 to +1,100
- Check: +40
- History: 0 to +1,000+ (depends on success rate)
- **Learned bonus: -100 to +100** (based on winrate)

Notice learned bonus is small! This is intentional - we don't want
to override the engine's evaluation, just gently guide move ordering.

### Winrate Calculation
```
winrate = (wins + 0.5 * draws) / total_games
bonus = (winrate - 0.5) * 200

Examples:
- 10 wins, 0 draws, 0 losses: 100% winrate → +100 bonus
- 5 wins, 0 draws, 5 losses: 50% winrate → 0 bonus
- 2 wins, 4 draws, 4 losses: 40% winrate → -20 bonus
```

## Performance Metrics

**Typical nodes searched (depth 4):**
- Without optimizations: ~100,000 nodes
- With all optimizations: ~5,000-10,000 nodes
- **10-20x speedup!**

**Optimizations used:**
- Principal Variation Search (PVS): 2-3x faster
- Late Move Reductions (LMR): 1.5-2x faster
- Transposition Table: 3-5x fewer nodes
- Killer + History: 20-40% fewer nodes
- Good move ordering: Critical for all of above!

## Next Steps

1. **Play a few games** to get familiar with the UI
2. **Try AI vs AI** for 5-10 games to seed learning data
3. **Experiment with depth** to find sweet spot for your machine
4. **Export learning** regularly to back up progress
5. **Compare with/without learning** to see improvement
6. **Share learning files** with friends to combine datasets!

## Further Reading

- `DOCUMENTATION.md` - Detailed technical documentation
- `game_controller.py` - Source code with extensive comments
- Python-chess docs: https://python-chess.readthedocs.io/

## Tips for Best Results

✓ Let AI play at least 10 games before judging learning
✓ Use depth 4-5 for training (good balance of speed and quality)
✓ Export learning files regularly (backup your progress!)
✓ Reset learning if AI develops bad habits
✓ Import pre-trained data to bootstrap learning
✓ Run AI vs AI overnight for massive training

✗ Don't use depth 1-2 for serious games (too weak)
✗ Don't expect learning from just 2-3 games (not enough data)
✗ Don't manually edit JSON files (use Import instead)
✗ Don't set depth 6 in AI vs AI mode (too slow for training)

Enjoy your chess AI! 🎯♟️
