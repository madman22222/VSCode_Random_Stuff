import unittest, os, csv, importlib.util, pathlib

THIS_DIR = pathlib.Path(__file__).parent
SCRIPT = THIS_DIR.parent / 'generate_metrics_sample.py'

class TestMetricsGeneration(unittest.TestCase):
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
        with open('metrics_sample.csv', 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader)
        expected = ['move','depth','nodes','branching','time','source']
        self.assertEqual(header, expected, 'Metrics CSV header mismatch')

if __name__ == '__main__':
    unittest.main()
