#!/usr/bin/env python3
"""CLI tool to verify a UCI engine binary (Stockfish).

Usage:
  python tools/check_engine.py --path path/to/stockfish

If no path is supplied the script will try ./engines/stockfish(.exe) and then PATH.
"""
import argparse
import os
import sys
import shutil
import chess
import chess.engine
import urllib.request
import json
import zipfile
import platform
import tempfile
import subprocess
import time

DEFAULT_REPO_API = 'https://api.github.com/repos/official-stockfish/Stockfish/releases/latest'


def find_default_engine():
    here = os.path.dirname(os.path.dirname(__file__))
    engines_dir = os.path.join(here, 'engines')
    candidates = []
    exe_name = 'stockfish'
    if sys.platform.startswith('win'):
        exe_name = 'stockfish.exe'
    # check engines/ folder
    if os.path.isdir(engines_dir):
        path = os.path.join(engines_dir, exe_name)
        if os.path.exists(path):
            return path
        # try any file starting with 'stockfish'
        for f in os.listdir(engines_dir):
            if f.lower().startswith('stockfish'):
                return os.path.join(engines_dir, f)
    # check PATH
    p = shutil.which('stockfish')
    if p:
        return p
    return None


def verify_engine(path: str, timeout: float) -> bool:
    try:
        engine = chess.engine.SimpleEngine.popen_uci(path)
    except Exception as e:
        print(f'ERROR: failed to start engine: {e}', file=sys.stderr)
        return False
    try:
        board = chess.Board()
        # request a very short play to check responsiveness
        res = engine.play(board, chess.engine.Limit(time=timeout))
        engine.quit()
        if res is None or not getattr(res, 'move', None):
            print('ERROR: engine did not return a move', file=sys.stderr)
            return False
        # probe identity via separate subprocess UCI handshake
        identity = probe_engine_identity(path)
        if identity:
            print('OK: engine responded with move', res.move, '-', identity)
        else:
            print('OK: engine responded with move', res.move)
        return True
    except Exception as e:
        try:
            engine.quit()
        except Exception:
            pass
        print(f'ERROR during engine play: {e}', file=sys.stderr)
        return False


def probe_engine_identity(path: str) -> str:
    try:
        proc = subprocess.Popen([path], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        out, err = proc.communicate('uci\nquit\n', timeout=5)
        name = None
        author = None
        for line in out.splitlines():
            line = line.strip()
            if line.lower().startswith('id name'):
                name = line[7:].strip()
            elif line.lower().startswith('id author'):
                author = line[9:].strip()
        parts = []
        if name:
            parts.append(name)
        if author:
            parts.append(f'by {author}')
        return ' '.join(parts)
    except Exception:
        return ''


def download_stockfish(engines_dir: str, prefer_platform: str = 'auto', token: str = '') -> str:
    """Download and extract Stockfish release into engines_dir. Returns path to executable or empty string.
    prefer_platform: one of 'auto','windows','macos','linux'
    token: optional GitHub token for API auth
    """
    headers = {'Accept': 'application/vnd.github.v3+json'}
    if token:
        headers['Authorization'] = f'token {token}'
    try:
        req = urllib.request.Request(DEFAULT_REPO_API, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.load(resp)
    except Exception as e:
        print('ERROR: could not query GitHub API:', e, file=sys.stderr)
        return ''
    assets = data.get('assets', []) if isinstance(data, dict) else []
    if not assets:
        print('ERROR: no release assets found', file=sys.stderr)
        return ''

    sysplat = platform.system().lower()
    if prefer_platform == 'auto':
        if sysplat.startswith('win'):
            prefer_platform = 'windows'
        elif sysplat.startswith('darwin'):
            prefer_platform = 'macos'
        else:
            prefer_platform = 'linux'

    candidate = None
    for a in assets:
        name = a.get('name', '').lower()
        url = a.get('browser_download_url')
        if not url:
            continue
        if prefer_platform == 'windows' and ('win' in name or 'windows' in name) and name.endswith('.zip'):
            candidate = url
            break
        if prefer_platform == 'macos' and ('mac' in name or 'osx' in name or 'macos' in name) and name.endswith('.zip'):
            candidate = url
            break
        if prefer_platform == 'linux' and ('linux' in name) and name.endswith('.zip'):
            candidate = url
            break
    if not candidate:
        for a in assets:
            name = a.get('name', '').lower()
            url = a.get('browser_download_url')
            if name.endswith('.zip'):
                candidate = url
                break
    if not candidate:
        print('ERROR: no suitable zip asset found', file=sys.stderr)
        return ''

    os.makedirs(engines_dir, exist_ok=True)
    try:
        tmpf = tempfile.NamedTemporaryFile(delete=False)
        tmp_path = tmpf.name
        tmpf.close()
        req = urllib.request.Request(candidate, headers=headers)
        with urllib.request.urlopen(req, timeout=60) as resp, open(tmp_path, 'wb') as out:
            shutil.copyfileobj(resp, out)
        with zipfile.ZipFile(tmp_path, 'r') as z:
            z.extractall(engines_dir)
        os.unlink(tmp_path)
        exe_name = 'stockfish'
        if sys.platform.startswith('win'):
            exe_name = 'stockfish.exe'
        found = ''
        for root, dirs, files in os.walk(engines_dir):
            for f in files:
                if f.lower().startswith('stockfish'):
                    candidate_path = os.path.join(root, f)
                    dest = os.path.join(engines_dir, exe_name)
                    try:
                        shutil.copyfile(candidate_path, dest)
                        found = dest
                        break
                    except Exception:
                        continue
            if found:
                break
        if not found:
            print('ERROR: no executable found after extraction', file=sys.stderr)
            return ''
        try:
            os.chmod(found, 0o755)
        except Exception:
            pass
        return found
    except Exception as e:
        print('ERROR: download/extract failed:', e, file=sys.stderr)
        return ''


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--path', '-p', help='Path to engine binary (Stockfish)')
    p.add_argument('--retries', '-r', type=int, default=2, help='Number of verification attempts')
    p.add_argument('--timeout', '-t', type=float, default=0.05, help='Engine play time limit in seconds')
    p.add_argument('--download', action='store_true', help='Attempt to download Stockfish on first failed attempt')
    p.add_argument('--token', help='GitHub token (or set GITHUB_TOKEN env var) to increase API rate limit')
    p.add_argument('--platform', choices=['auto', 'windows', 'macos', 'linux'], default='auto', help='Preferred platform asset to download')
    args = p.parse_args()
    path = args.path
    retries = max(1, args.retries)
    timeout = max(0.001, float(args.timeout))
    if not path:
        path = find_default_engine()
    if not path and not args.download:
        print('No engine found (checked engines/ and PATH).', file=sys.stderr)
        sys.exit(2)
    if path:
        print('Using engine:', path)
    last_err = None
    ok = False
    for attempt in range(1, retries + 1):
        print(f'Attempt {attempt}/{retries}...')
        try:
            ok = verify_engine(path, timeout)
        except Exception as e:
            last_err = str(e)
            ok = False
        if ok:
            break
        else:
            # small backoff
            time.sleep(0.5 * attempt)
            # if requested, try auto-download once
            if args.download and attempt == 1:
                print('Attempting to download Stockfish...')
                here = os.path.dirname(os.path.dirname(__file__))
                engines_dir = os.path.join(here, 'engines')
                token = args.token or os.environ.get('GITHUB_TOKEN', '')
                found = download_stockfish(engines_dir, prefer_platform=args.platform or 'auto', token=token)
                if found:
                    print('Downloaded engine to', found)
                    path = found
                else:
                    print('Download attempt failed')
    if not ok:
        print(f'Verification failed after {retries} attempts. Last error: {last_err}', file=sys.stderr)
    sys.exit(0 if ok else 1)
