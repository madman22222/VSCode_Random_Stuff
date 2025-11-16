import unittest, os, csv, importlib.util, pathlib, tempfile, shutil

THIS_DIR = pathlib.Path(__file__).parent
SCRIPT = THIS_DIR.parent / 'generate_metrics_sample.py'

EXPECTED_HEADER = ['move','depth','nodes','branching','time','source']

class TestMetricsGeneration(unittest.TestCase):
    def setUp(self):
        # Isolate test output in a temp directory
        self._orig_cwd = os.getcwd()
        self._tmp = tempfile.TemporaryDirectory()
        os.chdir(self._tmp.name)
        # Ensure no pre-existing file
        try:
            os.remove('metrics_sample.csv')
        except OSError:
            pass

    def tearDown(self):
        # Restore working dir and cleanup
        os.chdir(self._orig_cwd)
        self._tmp.cleanup()

    def test_metrics_sample_generation(self):
        # Dynamically import the metrics script
        spec = importlib.util.spec_from_file_location('gen_metrics', str(SCRIPT))
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        # Run main to generate CSV
        mod.main()
        self.assertTrue(os.path.exists('metrics_sample.csv'), 'metrics_sample.csv not created')
        rows = []
        with open('metrics_sample.csv', 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader)
            self.assertEqual(header, EXPECTED_HEADER, 'Metrics CSV header mismatch')
            for r in reader:
                rows.append(r)
        self.assertGreater(len(rows), 0, 'No metrics rows generated')
        # Validate first row fields (basic sanity)
        first = rows[0]
        self.assertEqual(len(first), len(EXPECTED_HEADER), 'Row column count mismatch')
        # move non-empty
        self.assertTrue(first[0], 'Move field empty')
        # depth numeric
        self.assertTrue(first[1].isdigit(), 'Depth not numeric')
        # nodes may be numeric or blank (engine case) -> allow empty or digits
        self.assertTrue(first[2].isdigit() or first[2] == '' or first[2].lower() == 'none', 'Nodes field invalid')
        # branching numeric
        self.assertTrue(first[3].isdigit(), 'Branching not numeric')
        # time float
        try:
            float(first[4])
        except ValueError:
            self.fail('Time not float')
        # source recognized
        self.assertIn(first[5], {'iterative','aspiration','book','engine'}, 'Source unrecognized')

if __name__ == '__main__':
    unittest.main()
