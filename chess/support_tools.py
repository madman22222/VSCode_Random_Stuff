"""Reusable support reporting and explicit, optional release lookup."""
import importlib.metadata
import json
from pathlib import Path
import platform
import sys
from urllib.request import Request, urlopen
from app_paths import data_dir, resource_dir, frozen

REPO = 'https://github.com/madman22222/VSCode_Random_Stuff'
RELEASE_API = 'https://api.github.com/repos/madman22222/VSCode_Random_Stuff/releases/latest'


def build_info():
    path = (Path(sys.executable).parent if frozen() else resource_dir().parent) / 'BUILD_INFO.json'
    info = json.loads(path.read_text()) if path.exists() else {'revision': 'source checkout'}
    if not frozen() and (resource_dir().parent / '.git').exists():
        import subprocess
        try:
            info['revision'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'],
                cwd=resource_dir().parent, text=True, timeout=3, stderr=subprocess.DEVNULL).strip()
        except (OSError, subprocess.SubprocessError):
            pass
    return {'build': info, 'platform': platform.platform(), 'python': platform.python_version(),
            'frozen': frozen(), 'data_directory': str(data_dir()),
            'packages': {n: importlib.metadata.version(n) for n in ('python-chess', 'chess', 'Pillow')}}


def support_report():
    info = build_info()
    info['privacy'] = 'No game history, learning memory, or logs included. Review paths before sharing.'
    return json.dumps(info, indent=2)


def latest_release():
    # Called only after explicit user action. Never download or replace executables.
    request = Request(RELEASE_API, headers={'Accept': 'application/vnd.github+json',
                                          'User-Agent': 'ChessStudio'})
    with urlopen(request, timeout=8) as response:
        raw = response.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        raise ValueError('Unexpected release response size')
    release = json.loads(raw)
    url = release.get('html_url', '')
    if not url.startswith(REPO + '/releases/tag/'):
        raise ValueError('Release did not contain a trusted project link')
    return {'tag': release['tag_name'], 'url': url, 'revision': release.get('target_commitish'),
            'published': release.get('published_at')}
