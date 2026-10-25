# Optional sound assets

`SoundManager` looks for these WAV filenames under `assets/sounds/`:

| Filename | Event |
| --- | --- |
| `move.wav` | Regular move |
| `capture.wav` | Capture |
| `check.wav` | Check |
| `checkmate.wav` | Checkmate |
| `castle.wav` | Castling |
| `illegal.wav` | Illegal move |

Toggle playback in Settings → Appearance. Playback uses Windows `winsound`;
on other systems it currently does nothing. Missing WAV files fall back to
Windows system beeps for check, checkmate, and illegal moves. Sounds are optional
and never required for play.

Add WAV assets here for source use and rebuild to include them in portable
releases. Bundled resources live in `_internal/assets/sounds`. Preserve the
licenses and attribution for any audio you add.
