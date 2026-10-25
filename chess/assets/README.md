# Piece images

The repository includes PNG pieces and the Windows portable build bundles them.
Settings → Access can also use symbols or letters.

| Color | Required filenames |
| --- | --- |
| White | `wp.png`, `wn.png`, `wb.png`, `wr.png`, `wq.png`, `wk.png` |
| Black | `bp.png`, `bn.png`, `bb.png`, `br.png`, `bq.png`, `bk.png` |

Use square PNGs, ideally with transparent backgrounds. The board scales and
caches images for the current square size rather than assuming a fixed 64×64
board. Source resources resolve relative to this project; portable resources
live under the bundled resource directory (`_internal/assets`). Mutable saves
belong in the data profile, not among assets.

For a custom source build, replace the relevant PNGs and restart the app. Rebuild
the Windows ZIP to distribute replacements. Preserve attribution/license notices
for any third-party artwork you add. See [packaging](../../packaging/README.md).
