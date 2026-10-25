"""Build a Windows x64 portable ZIP with resources, notices and source archives."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def package_zip(app, output):
    app, output = Path(app), Path(output)
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(app.rglob('*')):
            if path.is_file():
                archive.write(path, Path('ChessStudio') / path.relative_to(app))
    checksum = sha256(output)
    output.with_suffix('.zip.sha256').write_text(f'{checksum}  {output.name}\n', encoding='utf-8')
    return checksum


def add_dependency_source(name, version, directory):
    request = urllib.request.Request(f'https://pypi.org/pypi/{name}/{version}/json',
                                     headers={'User-Agent': 'ChessStudio-release-builder'})
    with urllib.request.urlopen(request, timeout=60) as response:
        metadata = json.load(response)
    source = next(item for item in metadata['urls'] if item['packagetype'] == 'sdist')
    filename = Path(source['filename']).name
    if filename != source['filename'] or not source['url'].startswith('https://'):
        raise ValueError('Invalid dependency source metadata')
    with urllib.request.urlopen(source['url'], timeout=60) as response:
        content = response.read()
    if hashlib.sha256(content).hexdigest() != source['digests']['sha256']:
        raise ValueError(f'Source checksum mismatch: {name}')
    (directory / filename).write_bytes(content)


def add_notices(app):
    licenses = app / 'LICENSES'
    sources = app / 'SOURCE'
    licenses.mkdir()
    sources.mkdir()
    notes = ['Third-party components bundled with Chess Studio.',
             'Original licenses are preserved below and in package metadata.', '']
    for name in ('python-chess', 'chess', 'Pillow', 'pyinstaller', 'altgraph', 'pyinstaller-hooks-contrib', 'pefile', 'pywin32-ctypes', 'packaging', 'setuptools'):
        distribution = importlib.metadata.distribution(name)
        notes.append(f'{name} {distribution.version}')
        for file in distribution.files or []:
            if 'license' in str(file).lower() or Path(file).name.lower().startswith('copying'):
                path = Path(distribution.locate_file(file))
                if path.is_file():
                    target = licenses / name / str(file).replace('..', '_')
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, target)
        if name in ('python-chess', 'chess', 'pyinstaller'):
            add_dependency_source(name, distribution.version, sources)
    python_license = Path(sys.base_prefix) / 'LICENSE.txt'
    if python_license.exists():
        shutil.copy2(python_license, licenses / 'PYTHON-LICENSE.txt')
    for path in (app / '_internal').rglob('license.terms'):
        target = licenses / (path.parent.name + '-license.terms')
        shutil.copy2(path, target)
    (licenses / 'THIRD_PARTY_NOTICES.txt').write_text('\n'.join(notes), encoding='utf-8')
    files = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
    with zipfile.ZipFile(sources / 'ChessStudio-source.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for filename in files:
            path = ROOT / filename
            if not filename or not path.is_file():
                continue
            if (path.suffix in ('.py', '.md', '.txt', '.spec', '.yml', '.yaml', '.bat', '.png')
                    or path.name in ('.gitignore', '.gitattributes', 'LICENSE')
                    or path.suffix == '.json' and (filename.startswith('chess/assets/') or filename.startswith('benchmarks/'))):
                archive.write(path, filename)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='dist')
    parser.add_argument('--version', default=None)
    args = parser.parse_args()
    if sys.platform != 'win32' or platform.machine().lower() not in ('amd64', 'x86_64'):
        parser.error('Build this Windows x64 application on a Windows x64 runner.')
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
                    '--distpath', str(output), '--workpath', str(ROOT / 'build' / 'portable'),
                    str(ROOT / 'packaging' / 'ChessStudio.spec')], cwd=ROOT, check=True)
    app = output / 'ChessStudio'
    shutil.copy2(ROOT / 'packaging' / 'PORTABLE_README.txt', app / 'README.txt')
    (app / 'data').mkdir(exist_ok=True)
    (app / 'data' / 'KEEP_YOUR_SAVES_HERE.txt').write_text(
        'Preferences, unfinished games and training memory are written here.\n'
        'Keep this data folder when updating Chess Studio.\n', encoding='utf-8')
    revision = args.version or subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    info = {'application': 'Chess Studio', 'revision': revision, 'platform': 'Windows x64',
            'python': platform.python_version(), 'packages': {
                name: importlib.metadata.version(name) for name in ('python-chess', 'chess', 'Pillow', 'pyinstaller', 'altgraph', 'pyinstaller-hooks-contrib', 'pefile', 'pywin32-ctypes', 'packaging', 'setuptools')}}
    (app / 'BUILD_INFO.json').write_text(json.dumps(info, indent=2), encoding='utf-8')
    add_notices(app)
    zip_path = output / 'ChessStudio-Windows.zip'
    checksum = package_zip(app, zip_path)
    (output / 'ChessStudio-Windows.build-info.json').write_text(
        json.dumps(dict(info, sha256=checksum, size_bytes=zip_path.stat().st_size), indent=2), encoding='utf-8')
    print(f'Built {zip_path} ({zip_path.stat().st_size:,} bytes)')


if __name__ == '__main__':
    main()
