import os
import shutil
import urllib.request
import json
import zipfile
import tempfile
import platform
import subprocess
import time
from typing import Optional, Tuple

import chess
import chess.engine

DEFAULT_REPO_API = 'https://api.github.com/repos/official-stockfish/Stockfish/releases/latest'


class EngineManager:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.engines_dir = os.path.join(self.base_dir, 'engines')
        os.makedirs(self.engines_dir, exist_ok=True)
        self.engine: Optional[chess.engine.SimpleEngine] = None
        self.path: Optional[str] = None

    def detect(self) -> Optional[str]:
        # check engines/ folder first
        exe_name = 'stockfish'
        if platform.system().lower().startswith('windows'):
            exe_name = 'stockfish.exe'
        path = os.path.join(self.engines_dir, exe_name)
        if os.path.exists(path):
            return path
        for f in os.listdir(self.engines_dir):
            if f.lower().startswith('stockfish'):
                return os.path.join(self.engines_dir, f)
        # fallback to PATH
        p = shutil.which('stockfish')
        if p:
            return p
        return None

    def start(self, path: str) -> bool:
        """Start engine process and keep reference. Returns True on success."""
        try:
            self.stop()
            eng = chess.engine.SimpleEngine.popen_uci(path)
            self.engine = eng
            self.path = path
            return True
        except Exception:
            self.engine = None
            return False

    def stop(self):
        try:
            if self.engine:
                try:
                    self.engine.quit()
                except Exception:
                    pass
        finally:
            self.engine = None
            self.path = None

    def play(self, board: chess.Board, limit: chess.engine.Limit):
        if not self.engine:
            raise RuntimeError('Engine not started')
        return self.engine.play(board, limit)

    def probe_identity(self, path: str) -> str:
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

    def download_stockfish(self, prefer_platform: str = 'auto', token: str = '') -> str:
        headers = {'Accept': 'application/vnd.github.v3+json'}
        if token:
            headers['Authorization'] = f'token {token}'
        try:
            req = urllib.request.Request(DEFAULT_REPO_API, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.load(resp)
        except Exception:
            return ''

        assets = data.get('assets', []) if isinstance(data, dict) else []
        if not assets:
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
        candidate_name = None
        for a in assets:
            name = a.get('name', '').lower()
            url = a.get('browser_download_url')
            if not url:
                continue
            if prefer_platform == 'windows' and ('win' in name or 'windows' in name) and name.endswith('.zip'):
                candidate = url
                candidate_name = name
                break
            if prefer_platform == 'macos' and ('mac' in name or 'osx' in name or 'macos' in name) and name.endswith('.zip'):
                candidate = url
                candidate_name = name
                break
            if prefer_platform == 'linux' and ('linux' in name) and name.endswith('.zip'):
                candidate = url
                candidate_name = name
                break

        if not candidate:
            for a in assets:
                name = a.get('name', '').lower()
                url = a.get('browser_download_url')
                if name.endswith('.zip'):
                    candidate = url
                    candidate_name = name
                    break

        if not candidate:
            return ''

        try:
            tmpf = tempfile.NamedTemporaryFile(delete=False)
            tmp_path = tmpf.name
            tmpf.close()
            req = urllib.request.Request(candidate, headers=headers)
            with urllib.request.urlopen(req, timeout=60) as resp, open(tmp_path, 'wb') as out:
                shutil.copyfileobj(resp, out)
            with zipfile.ZipFile(tmp_path, 'r') as z:
                z.extractall(self.engines_dir)
            os.unlink(tmp_path)

            exe_name = 'stockfish'
            if platform.system().lower().startswith('windows'):
                exe_name = 'stockfish.exe'

            found = ''
            for root, dirs, files in os.walk(self.engines_dir):
                for f in files:
                    if f.lower().startswith('stockfish'):
                        candidate_path = os.path.join(root, f)
                        dest = os.path.join(self.engines_dir, exe_name)
                        try:
                            shutil.copyfile(candidate_path, dest)
                            found = dest
                            break
                        except Exception:
                            continue
                if found:
                    break

            if not found:
                return ''
            try:
                os.chmod(found, 0o755)
            except Exception:
                pass
            return found
        except Exception:
            return ''

    def verify_engine(self, path: Optional[str], retries: int = 2, timeout: float = 0.05, auto_download: bool = False,
                      prefer_platform: str = 'auto', backoff: str = 'linear', max_wait: float = 5.0, token: str = '') -> Tuple[bool, str, Optional[str]]:
        """Verify engine responds. Returns (ok, message, path)."""
        if not path:
            return False, 'No engine path', None
        last_err = ''
        tried_download = False
        base_backoff = 0.5
        for attempt in range(1, max(1, retries) + 1):
            try:
                eng = chess.engine.SimpleEngine.popen_uci(path)
                b = chess.Board()
                res = eng.play(b, chess.engine.Limit(time=timeout))
                try:
                    eng.quit()
                except Exception:
                    pass
                if res is None or not getattr(res, 'move', None):
                    last_err = 'Engine started but did not return a move'
                else:
                    info = self.probe_identity(path)
                    msg = f'Engine responded with move: {res.move} (attempt {attempt}/{retries})'
                    if info:
                        msg += f' — {info}'
                    return True, msg, path
            except Exception as e:
                last_err = str(e)

            if auto_download and not tried_download:
                tried_download = True
                found = self.download_stockfish(prefer_platform=prefer_platform, token=token)
                if found:
                    path = found

            if attempt < retries:
                if backoff == 'constant':
                    wait = min(max_wait, base_backoff)
                elif backoff == 'exponential':
                    wait = min(max_wait, base_backoff * (2 ** (attempt - 1)))
                else:
                    wait = min(max_wait, base_backoff * attempt)
                time.sleep(wait)

        return False, f'Engine verification failed after {retries} attempts: {last_err}', None
