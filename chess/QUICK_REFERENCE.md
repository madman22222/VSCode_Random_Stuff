# 🎮 Chess Application - Quick Reference

## 🚀 Getting Started

```bash
python main.py
```

## 🎯 Main Features

### 🎨 Themes
- **Light Mode**: Classic chess board colors
- **Dark Mode**: Dark theme for night play
- Toggle via dropdown: Features → Theme → Light/Dark

### 🔊 Sounds
- **Move**: Standard piece movement
- **Capture**: Taking opponent's piece
- **Check**: King under attack
- **Checkmate**: Game over sound
- **Castle**: Castling move
- Toggle: Features → Sound button

### ⏱️ Chess Clock
- **Enable**: Features → Clock → Enable Clock
- **Time Control**: Default 10 minutes per side
- **Increment**: Configurable (default 0 seconds)
- **Reset**: Features → Clock → Reset
- **Display**: White clock (black background), Black clock (white background)

### 🔄 Board Controls
- **Flip Board**: Rotate 180° to play from black's side
- **Coordinates**: File (a-h) and Rank (1-8) labels
- **Last Move**: Yellow highlight on from/to squares

### 🤖 AI Settings
- **Depth Slider**: 1-6 (higher = stronger but slower)
  - Depth 1: Instant (~0.1s)
  - Depth 2: Fast (~0.5s)
  - Depth 3: Normal (~2s) ← **Default**
  - Depth 4: Strong (~8s)
  - Depth 5: Very Strong (~30s)
  - Depth 6: Maximum (~120s)

### 📊 Statistics
- **Games Played**: Total games completed
- **White Wins**: Games won as white
- **Black Wins**: Games won as black
- **Draws**: Stalemate or insufficient material
- **Total Moves**: Across all games

## ⌨️ Keyboard Shortcuts

| Key | Action |
|-----|--------|
| Click piece → Click destination | Make move |
| Drag & Drop | Move piece (in enhanced mode) |

## 🎲 Game Controls

### Top Panel:
- **Save PGN**: Export game to file
- **Load PGN**: Import game from file
- **Undo**: Take back last move

### Engine Panel:
- **Detect**: Find Stockfish on system
- **Download**: Get Stockfish from GitHub
- **Verify**: Test engine installation
- **Use Engine**: Toggle AI (Engine vs Built-in)

## 🎯 AI Strategies

### Opening Play:
- AI uses opening book for first few moves
- Recognizable openings: e4, d4, Sicilian, French, etc.

### Middlegame:
- Evaluates piece activity
- Values central control
- Protects king safety
- Considers pawn structure

### Endgame:
- Activates king
- Pushes passed pawns
- Values piece activity

### Special Features:
- **Transposition Table**: Caches positions for speed
- **Quiescence Search**: Sees forced sequences
- **Mobility**: Prefers active pieces
- **King Safety**: Bonus for castling, pawn shield
- **Pawn Structure**: Evaluates passed/isolated pawns

## 📁 Files & Configuration

### Config File:
`chess_config.json` - Auto-created on first run

### Sound Files (Optional):
```
assets/sounds/
  ├── move.wav        (regular move)
  ├── capture.wav     (capture)
  ├── check.wav       (check)
  ├── checkmate.wav   (game over)
  ├── castle.wav      (castling)
  └── illegal.wav     (illegal move)
```

### Piece Images:
```
assets/
  ├── wb.png, wk.png, wn.png, wp.png, wq.png, wr.png  (white pieces)
  └── bb.png, bk.png, bn.png, bp.png, bq.png, br.png  (black pieces)
```

## 🎨 Customization

### Change Clock Time:
Edit `chess_config.json`:
```json
{
  "clock_time": 300,      // 5 minutes
  "clock_increment": 3    // 3-second increment
}
```

### Change AI Depth:
```json
{
  "ai_depth": 4           // Stronger but slower
}
```

### Change Theme:
```json
{
  "theme": "dark"         // or "light"
}
```

### Disable Sounds:
```json
{
  "sound_enabled": false
}
```

## 🐛 Troubleshooting

### No Sounds Playing:
1. Check "Sound" button shows "On"
2. Add WAV files to `assets/sounds/`
3. System beeps used as fallback

### AI Too Slow:
1. Reduce AI depth slider to 2 or 3
2. Check transposition table is working
3. Close other applications

### Clock Not Counting:
1. Click "Enable Clock" button
2. Make a move to start countdown
3. Check clock displays are visible

### Board Looks Wrong:
1. Click "Flip Board" to rotate
2. Check theme setting (light/dark)
3. Restart application

### Engine Not Working:
1. Click "Detect" to find Stockfish
2. Click "Download" if not found
3. Click "Verify" to test
4. Check engine path in text box

## 📖 Game Rules

### Special Moves:
- **Castling**: King moves 2 squares, rook jumps over
- **En Passant**: Pawn captures passing pawn
- **Promotion**: Pawn reaching end promotes to Queen/Rook/Bishop/Knight

### Game Endings:
- **Checkmate**: King cannot escape attack (Win/Loss)
- **Stalemate**: No legal moves, not in check (Draw)
- **Insufficient Material**: Cannot force checkmate (Draw)
- **Time Forfeit**: Clock runs out (Loss on time)

## 💡 Tips & Tricks

### For Beginners:
1. Use AI depth 2-3 for learning
2. Enable sound for move feedback
3. Watch last move highlighting
4. Study statistics to track progress

### For Intermediate:
1. Use AI depth 3-4 for challenge
2. Enable clock for time pressure practice
3. Analyze pawn structure
4. Study opening book moves

### For Advanced:
1. Use AI depth 5-6 for serious games
2. Use short time controls (3+2)
3. Compare built-in AI vs Engine
4. Export games for analysis

### Best Practices:
- Save important games (Save PGN)
- Review statistics regularly
- Practice with clock enabled
- Flip board to see opponent's view

## 🎓 Learning Resources

### Understanding AI Evaluation:
- **Material**: Piece values (Pawn=100, Knight=320, etc.)
- **Position**: Piece-square tables guide placement
- **Mobility**: More legal moves = better position
- **King Safety**: Castling bonus, center penalty
- **Pawn Structure**: Passed pawns valuable, doubled pawns weak

### Improving Your Play:
1. **Opening**: Follow AI's book moves to learn openings
2. **Middlegame**: Watch for tactical opportunities
3. **Endgame**: Study pawn races and king activity
4. **Practice**: Use different time controls

## 🏆 Statistics Tracking

Your progress is automatically tracked:
- Every completed game counts
- Wins/losses/draws recorded
- Total moves tracked across sessions
- Data persists in `chess_config.json`

### Reset Statistics:
Delete or edit `chess_config.json`:
```json
{
  "statistics": {
    "games_played": 0,
    "white_wins": 0,
    "black_wins": 0,
    "draws": 0,
    "total_moves": 0
  }
}
```

## 📞 Support & Documentation

- `README.md` - Project overview
- `AI_IMPROVEMENTS.md` - AI technical details
- `UPGRADES_GUIDE.md` - Feature implementation guide
- `IMPLEMENTATION_COMPLETE.md` - Complete changelog

## 🎉 Enjoy Your Game!

Have fun playing chess with a professional-grade AI, time controls, themes, and statistics tracking!

**Happy Chess Playing! ♟️👑**
