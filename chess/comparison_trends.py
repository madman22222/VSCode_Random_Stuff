"""Group comparable complete reports; keep incompatible budgets out of trends."""
import math


def observations(histories):
    result = []
    for source, data in histories:
        # A cancelled series may contain completed opponents; require whole series completion.
        if not isinstance(data, dict) or data.get('state') != 'completed':
            continue
        reports = data.get('reports') or [data]
        if not isinstance(reports, list):
            continue
        for report in reports:
            if not isinstance(report, dict) or report.get('state') != 'completed' or not report.get('completed_pairs'):
                continue
            suite = report.get('evaluation_suite', {})
            if not isinstance(suite, dict) or not isinstance(suite.get('sha256'), str) or report.get('evaluation_protocol') != 2:
                continue
            if any(type(report.get(key)) is not int or report[key] < minimum for key, minimum in
                   (('depth', 1), ('nodes_per_move', 1), ('max_plies', 1), ('seed', -10**12), ('completed_pairs', 1))):
                continue
            if not isinstance(report.get('baseline_memory_fingerprint'), str):
                continue
            score, interval = report.get('score_percent'), report.get('ci95_score_percent')
            if type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= 100:
                continue
            if not isinstance(interval, list) or len(interval) != 2 or any(type(x) not in (int, float) or not math.isfinite(x) or not 0 <= x <= 100 for x in interval) or interval[0] > interval[1]:
                continue
            if any(type(report.get(key, False)) is not bool for key in ('candidate_outcome_scoring', 'baseline_outcome_scoring')):
                continue
            if report.get('opponent') not in ('untrained', 'previous'):
                continue
            signature = (suite['sha256'], report.get('depth'), report.get('nodes_per_move'),
                         report.get('max_plies'), report.get('opponent'),
                         report.get('candidate_outcome_scoring', False), report.get('seed'),
                         report.get('baseline_memory_fingerprint'), report.get('baseline_outcome_scoring', False))
            result.append({'source': source, 'signature': signature,
                'memory': str(report.get('memory_fingerprint', data.get('memory_fingerprint', 'unknown'))),
                'score': report.get('score_percent'), 'interval': report.get('ci95_score_percent', [0, 100]),
                'pairs': report['completed_pairs'], 'cutoffs': report.get('move_limit_draws', 0),
                'remembered_roots': suite.get('remembered_roots', 'unknown')})
    return result


def trend_text(histories):
    groups = {}
    for item in observations(histories):
        groups.setdefault(item['signature'], []).append(item)
    lines = ['Comparison trends for this profile',
             'Scores are internal comparisons, not Elo. Different corpus/budgets/opponents/scoring modes are separated.',
             'Repeated runs of the same memory or seed are not independent evidence; intervals are not pooled.\n']
    for number, (signature, items) in enumerate(groups.items(), 1):
        corpus, depth, nodes, plies, opponent, scoring, seed, baseline, baseline_scoring = signature
        lines.append(f'Group {number}: corpus {corpus[:10]}, depth {depth}, nodes {nodes}, max plies {plies}, opponent {opponent}, scoring {scoring}, seed {seed}, baseline {str(baseline)[:10]}')
        for item in sorted(items, key=lambda x: x['source']):
            lines.append(f"{item['source']}: memory {item['memory'][:10]}, score {item['score']}%, 95% range {item['interval']}, pairs {item['pairs']}, cutoff draws {item['cutoffs']}, remembered roots {item['remembered_roots']}")
        if len(items) >= 2:
            first, last = sorted(items, key=lambda x: x['source'])[0], sorted(items, key=lambda x: x['source'])[-1]
            if isinstance(first['score'], (int, float)) and isinstance(last['score'], (int, float)):
                lines.append(f"First-to-latest observed change: {last['score'] - first['score']:+.1f} percentage points; descriptive only, not proof of improvement.")
        lines.append('')
    if not groups:
        lines.append('No complete protocol-2 comparison reports yet. Run Compare to begin. Older reports remain available in the raw history viewer.')
    return '\n'.join(lines)
