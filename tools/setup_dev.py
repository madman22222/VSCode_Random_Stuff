"""Create a local VS Code interpreter without installing anything globally."""
from pathlib import Path
import subprocess
import sys
import venv


def main():
    if sys.version_info < (3, 10):
        raise SystemExit('Python 3.10 or newer is required.')
    root = Path(__file__).resolve().parents[1]
    environment = root / '.venv'
    python = environment / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')
    if not python.exists():
        venv.EnvBuilder(with_pip=True).create(environment)
    subprocess.run([str(python), '-m', 'pip', 'install', '-c', str(root / 'packaging/constraints-build.txt'), '-r', str(root / 'chess/requirements.txt')], check=True)
    subprocess.run([str(python), '-c', 'import tkinter, chess.pgn, PIL; print("Dependencies ready")'], check=True)
    print(f'In VS Code choose Python: Select Interpreter → {python}, then press F5.')
    print('On Linux, install your system Tkinter package if the tkinter check fails.')


if __name__ == '__main__':
    main()
