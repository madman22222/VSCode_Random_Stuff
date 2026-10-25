"""Launch the extracted VS Code edition with Python, separately from its repository."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--zip', required=True)
    parser.add_argument('--revision', required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='Chess source test ') as temp:
        temp = Path(temp).resolve()
        with zipfile.ZipFile(args.zip) as archive:
            archive.extractall(temp)
        app = temp / 'ChessStudio-VSCode'
        assert json.loads((app / 'BUILD_INFO.json').read_text())['revision'] == args.revision
        assert (app / '.vscode/launch.json').is_file()
        assert (app / 'ChessStudio.code-workspace').is_file()
        env = dict(os.environ, CHESS_STUDIO_DATA_DIR=str(temp / 'data'))
        env.pop('PYTHONPATH', None)
        report = temp / 'diagnostics.json'
        subprocess.run([sys.executable, str(app / 'chess/main.py'), '--diagnostics-report', str(report)],
                       cwd=temp, env=env, check=True, timeout=120)
        result = json.loads(report.read_text())
        assert result['success'] and not result['frozen'], result
        print('Extracted VS Code source passed diagnostics at revision ' + args.revision)


if __name__ == '__main__':
    main()
