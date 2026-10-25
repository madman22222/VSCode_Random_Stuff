"""Test the ZIP's extracted executables with no Python/source paths available."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--zip', required=True)
    parser.add_argument('--report', default='portable-smoke-report.json')
    args = parser.parse_args()
    summary = {'success': False}
    try:
        with tempfile.TemporaryDirectory(prefix='Chess Studio portable test ') as temp:
            temp = Path(temp)
            with zipfile.ZipFile(args.zip) as archive:
                archive.extractall(temp)
            app = temp / 'ChessStudio'
            cwd = temp / 'Unrelated working directory'
            cwd.mkdir()
            env = dict(os.environ)
            for key in ('PYTHONHOME', 'PYTHONPATH', 'VIRTUAL_ENV', 'TCL_LIBRARY', 'TK_LIBRARY', 'CHESS_STUDIO_DATA_DIR'):
                env.pop(key, None)
            # Windows system libraries remain available; Python/pip are absent.
            env['PATH'] = os.path.join(env.get('SystemRoot', r'C:\Windows'), 'System32')
            report = temp / 'diagnostics.json'
            result = subprocess.run([str(app / 'ChessStudio.exe'), '--diagnostics-report', str(report)],
                                    cwd=cwd, env=env, capture_output=True, timeout=120)
            details = json.loads(report.read_text(encoding='utf-8')) if report.exists() else {}
            assert result.returncode == 0 and details.get('success'), str(details or result.stderr)
            assert details['frozen'], 'The check did not run a frozen executable'
            assert Path(details['data_directory']) == app / 'data', 'Data is not beside the extracted app'
            assert Path(details['resources']) == app / '_internal', 'Resources are outside the bundle'
            learning = app / 'data' / 'cli-check.json'
            cli = subprocess.run([str(app / 'ChessStudio-CLI.exe'), '--training', '--games', '1',
                                  '--depth', '1', '--move-ms', '5', '--max-plies', '4',
                                  '--learning-file', str(learning)], cwd=cwd, env=env,
                                 capture_output=True, text=True, timeout=60)
            assert cli.returncode == 0, cli.stderr
            assert Path(str(learning) + '.gz').exists(), 'Console training did not save'
            summary.update(success=True, diagnostics=details, cli_training=True,
                           python_removed_from_path=True, extracted_zip_tested=True)
    except Exception:
        import traceback
        summary['error'] = traceback.format_exc()
    Path(args.report).write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary, indent=2))
    return 0 if summary['success'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
