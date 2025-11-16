import os, json, unittest, importlib.util, tempfile, shutil

# Dynamically load converter module
ROOT = os.path.dirname(os.path.dirname(__file__))
CONVERTER_PATH = os.path.join(ROOT, 'tools', 'batch_pgn_converter.py')
spec = importlib.util.spec_from_file_location('batch_pgn_converter', CONVERTER_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

SAMPLE_PGN_SINGLE = """[Event "Single"]\n[Site "Local"]\n[Date "2025.11.15"]\n[Round "1"]\n[White "A"]\n[Black "B"]\n[Result "1-0"]\n\n1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 5. O-O Be7 6. Re1 O-O 7. c3 d5 8. exd5 Nxd5 9. Nxe5 Nxe5 10. Rxe5 Nf4 11. d4 Bd6 12. Bxf4 1-0\n"""
SAMPLE_PGN_MULTI = """[Event "G1"]\n[Site "Local"]\n[Date "2025.11.15"]\n[Round "1"]\n[White "A"]\n[Black "B"]\n[Result "1-0"]\n\n1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 5. O-O Be7 6. Re1 O-O 7. c3 d5 8. exd5 Nxd5 9. Nxe5 Nxe5 10. Rxe5 Nf4 11. d4 Bd6 12. Bxf4 1-0\n\n[Event "G2"]\n[Site "Local"]\n[Date "2025.11.15"]\n[Round "2"]\n[White "C"]\n[Black "D"]\n[Result "0-1"]\n\n1. d4 Nf6 2. c4 e6 3. Nc3 Bb4 4. e3 O-O 5. Bd3 d5 6. Nf3 c5 7. O-O Nc6 8. a3 Bxc3 9. bxc3 dxc4 10. Bxc4 Qc7 11. Qe2 e5 12. d5 e4 13. dxc6 e5 14. Qxf3 Ng4 0-1\n"""

class TestBatchPGNConverter(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='pgn_conv_test_')
        self.input_dir = os.path.join(self.tmp, 'in')
        os.makedirs(self.input_dir, exist_ok=True)
        with open(os.path.join(self.input_dir, 'single.pgn'),'w',encoding='utf-8') as f: f.write(SAMPLE_PGN_SINGLE)
        with open(os.path.join(self.input_dir, 'multi.pgn'),'w',encoding='utf-8') as f: f.write(SAMPLE_PGN_MULTI)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_json_conversion(self):
        out = os.path.join(self.tmp, 'json')
        rep = mod.batch_convert(self.input_dir, out, fmt='json')
        self.assertEqual(rep['error'], 0)
        self.assertTrue(os.path.exists(os.path.join(out,'single.json')))
        self.assertTrue(os.path.exists(os.path.join(out,'multi.json')))
        # multi should be an array in JSON
        data = json.load(open(os.path.join(out,'multi.json'), 'r', encoding='utf-8'))
        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 2)

    def test_summary_conversion(self):
        out = os.path.join(self.tmp, 'summary')
        rep = mod.batch_convert(self.input_dir, out, fmt='summary')
        self.assertEqual(rep['ok'], 2)
        text = open(os.path.join(out,'multi.txt'),'r',encoding='utf-8').read()
        self.assertIn('Game 2', text)

    def test_csv_and_aggregate(self):
        out = os.path.join(self.tmp, 'csv')
        rep = mod.batch_convert(self.input_dir, out, fmt='csv')
        self.assertEqual(rep['ok'], 2)
        self.assertTrue(os.path.exists(os.path.join(out,'aggregate.csv')))
        agg_head = open(os.path.join(out,'aggregate.csv'),'r',encoding='utf-8').read().splitlines()[0]
        self.assertIn('file,game,ply,color,san', agg_head.replace(' ',''))

    def test_minimal(self):
        out = os.path.join(self.tmp, 'minimal')
        rep = mod.batch_convert(self.input_dir, out, fmt='minimal')
        self.assertEqual(rep['ok'], 2)
        txt = open(os.path.join(out,'single.txt'),'r',encoding='utf-8').read().strip()
        self.assertTrue(len(txt.split()) > 5)

if __name__ == '__main__':
    unittest.main()
