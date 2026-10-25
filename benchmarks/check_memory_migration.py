"""Isolated migration smoke experiment; deliberately too small for strength claims."""
import argparse
import json
from pathlib import Path
import sys
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'chess'))
import chess
from simple_ai import SimpleAI
from training_ai import TrainingAI, ComparisonSeries


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / 'ai_learn.json'
        legacy_key = chess.Board().board_fen() + '|e2e4'
        legacy = {'meta': {'version': 2, 'outcome_scoring': True},
                  'data': {legacy_key: {'w': 10, 'l': 2, 'd': 3}}}
        path.write_text(json.dumps(legacy))
        ai = SimpleAI(depth=1, learning_path=path)
        assert not ai.use_outcome_scoring
        trainer = TrainingAI(ai, max_games=4, max_moves=12, move_time_limit=.002, depth=1)
        trainer.start()
        trainer.thread.join(30)
        assert not trainer.running and not trainer.last_error, trainer.last_error
        assert ai.learning_db[legacy_key] == legacy['data'][legacy_key]
        series = ComparisonSeries(ai, games=4, depth=1, node_limit=40, max_moves=12, against='both')
        series.start()
        series.thread.join(60)
        assert not series.running and not series.last_error, series.last_error
        report = {'legacy_record_preserved': True, 'scoring_reset': not ai.use_outcome_scoring,
                  'legacy_input_bytes': len(json.dumps(legacy).encode()),
                  'saved_compressed_bytes': Path(str(path) + '.gz').stat().st_size,
                  'new_contextual_entries': sum(' ' in key.split('|')[0] for key in ai.learning_db),
                  'comparison': series.result,
                  'limitation': 'Tiny cutoff-heavy smoke check, not evidence of greater chess strength or comparable file compression ratios.'}
        Path(args.output).write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(args.output)


if __name__ == '__main__':
    main()
