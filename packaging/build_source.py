"""Package the exact same tracked source for VS Code; never fork the application."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def source_files(root=ROOT):
    tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=root).decode().split('\0')
    for name in sorted(set(tracked)):
        path = root / name
        if not name or not path.is_file():
            continue
        if name.startswith(('chess/autosaves/', 'chess/converted_', 'chess/logs/', 'chess/profiles/', 'chess/backups/')):
            continue
        if path.suffix in ('.py', '.md', '.txt', '.spec', '.yml', '.yaml', '.bat', '.png', '.code-workspace') or path.name in ('.gitignore', '.gitattributes', 'LICENSE') or (
                path.suffix == '.json' and name.startswith(('chess/assets/', 'benchmarks/', '.vscode/'))):
            yield name, path


def build_source(target, root=ROOT):
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    files = list(source_files(root))
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, path in files:
            archive.write(path, 'ChessStudio-VSCode/' + name)
        archive.writestr('ChessStudio-VSCode/BUILD_INFO.json', json.dumps({
            'application': 'Chess Studio', 'edition': 'VS Code source', 'revision': revision,
            'shared_entry_point': 'chess/main.py', 'worktree_dirty': bool(subprocess.check_output(
                ['git', 'status', '--porcelain'], cwd=root, text=True).strip())}, indent=2))
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    target.with_suffix('.zip.sha256').write_text(f'{digest}  {target.name}\n')
    return target


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='dist/ChessStudio-VSCode.zip')
    args = parser.parse_args()
    print(build_source(args.output))
