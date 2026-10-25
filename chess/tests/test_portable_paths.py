"""Runtime paths must not confuse bundled resources with portable saves."""
import hashlib
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import app_paths
from config_manager import ConfigManager
from simple_ai import SimpleAI


class TestPortablePaths(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        app_paths.data_dir.cache_clear()
        self.addCleanup(app_paths.data_dir.cache_clear)

    def test_frozen_paths_are_independent_of_working_directory(self):
        exe = self.root / 'App with spaces' / 'ChessStudio.exe'
        resources = exe.parent / '_internal'
        resources.mkdir(parents=True)
        cwd = Path.cwd()
        unrelated = self.root / 'elsewhere'
        unrelated.mkdir()
        self.addCleanup(os.chdir, cwd)
        with patch.object(sys, 'frozen', True, create=True), patch.object(sys, 'executable', str(exe)), \
             patch.object(sys, '_MEIPASS', str(resources), create=True), patch.dict(os.environ, {}, clear=True):
            os.chdir(unrelated)
            self.assertEqual(app_paths.resource_dir(), resources)
            self.assertEqual(app_paths.data_dir(), exe.parent / 'data')
            self.assertNotEqual(app_paths.data_dir(), resources)
            config = ConfigManager()
            config.set('ai_depth', 2)
            self.assertTrue((exe.parent / 'data' / 'chess_config.json').exists())
            ai = SimpleAI()
            ai.learning_db['position|e2e4'] = {'w': 1, 'l': 0, 'd': 0}
            ai._save_learning_db()
            self.assertEqual(SimpleAI().learning_db, ai.learning_db)
            self.assertFalse((resources / 'ai_learn.json.gz').exists())

    def test_console_command_uses_bundled_executable_not_main_py(self):
        exe = self.root / 'ChessStudio.exe'
        cli = self.root / 'ChessStudio-CLI.exe'
        cli.touch()
        with patch.object(sys, 'frozen', True, create=True), patch.object(sys, 'executable', str(exe)):
            self.assertEqual(app_paths.training_command(), [str(cli)])

    def test_protected_app_folder_falls_back_to_local_appdata(self):
        local = self.root / 'local'
        expected = local / 'ChessStudio'
        with patch.object(sys, 'frozen', True, create=True), patch.object(sys, 'executable', str(self.root / 'ChessStudio.exe')), \
             patch.dict(os.environ, {'LOCALAPPDATA': str(local)}, clear=True), \
             patch('app_paths._writable', side_effect=[PermissionError('protected'), expected]) as probe:
            self.assertEqual(app_paths.data_dir(), expected)
            self.assertEqual(probe.call_count, 2)

    def test_explicit_data_override_is_respected(self):
        selected = self.root / 'selected'
        with patch.dict(os.environ, {'CHESS_STUDIO_DATA_DIR': str(selected)}):
            self.assertEqual(app_paths.data_dir(), selected)
            self.assertTrue(selected.is_dir())

    def test_source_checkout_keeps_existing_data_location(self):
        with patch.object(sys, 'frozen', False, create=True), patch.dict(os.environ, {}, clear=True):
            self.assertEqual(app_paths.data_dir(), Path(app_paths.__file__).resolve().parent)
            command = app_paths.training_command()
            self.assertEqual(command[0], sys.executable)
            self.assertEqual(Path(command[1]).name, 'main.py')

    def test_zip_has_one_app_folder_and_checksum_matches_bytes(self):
        script = Path(__file__).resolve().parents[2] / 'packaging' / 'build_windows.py'
        spec = importlib.util.spec_from_file_location('portable_builder', script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        app = self.root / 'app'
        (app / '_internal').mkdir(parents=True)
        (app / 'data').mkdir()
        (app / 'ChessStudio.exe').write_bytes(b'test executable placeholder')
        (app / '_internal' / 'python.dll').write_bytes(b'placeholder runtime')
        (app / 'data' / 'README.txt').write_text('Keep your saves')
        target = self.root / 'ChessStudio-Windows.zip'
        digest = module.package_zip(app, target)
        self.assertEqual(digest, hashlib.sha256(target.read_bytes()).hexdigest())
        self.assertIn(digest, target.with_suffix('.zip.sha256').read_text())
        with zipfile.ZipFile(target) as archive:
            self.assertIn('ChessStudio/ChessStudio.exe', archive.namelist())
            self.assertIn('ChessStudio/_internal/python.dll', archive.namelist())
            self.assertTrue(all(name.startswith('ChessStudio/') for name in archive.namelist()))
