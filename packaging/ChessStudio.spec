# Build on Windows: python -m PyInstaller --noconfirm --clean packaging/ChessStudio.spec
from pathlib import Path
from PyInstaller.utils.hooks import copy_metadata

root = Path(SPECPATH).parent
metadata = []
for package in ('python-chess', 'chess', 'Pillow'):
    metadata += copy_metadata(package)
a = Analysis(
    [str(root / 'chess' / 'main.py')],
    pathex=[str(root / 'chess')],
    binaries=[],
    datas=[(str(root / 'chess' / 'assets'), 'assets')] + metadata,
    hiddenimports=['PIL.ImageTk', 'chess.pgn', 'chess.engine', 'tools.batch_pgn_converter'],
    hookspath=[], runtime_hooks=[], excludes=['pytest', 'IPython', 'matplotlib', 'numpy'],
    noarchive=False,
)
pyz = PYZ(a.pure)
# Two small bootloaders share one set of Python/Tk/Pillow libraries.
gui = EXE(pyz, a.scripts, [], exclude_binaries=True, name='ChessStudio',
          debug=False, strip=False, upx=False, console=False)
cli = EXE(pyz, a.scripts, [], exclude_binaries=True, name='ChessStudio-CLI',
          debug=False, strip=False, upx=False, console=True)
app = COLLECT(gui, cli, a.binaries, a.datas, strip=False, upx=False, name='ChessStudio')
