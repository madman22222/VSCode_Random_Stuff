"""Deterministic spaced review; timestamps are UTC seconds, never engine learning."""
import copy
import time

INTERVAL_DAYS = (1, 3, 7, 14, 30)


def record(stats, puzzle_id, success, assisted=False, now=None):
    now = time.time() if now is None else now
    result = copy.deepcopy(stats)
    item = dict(result.get(puzzle_id, {}))
    item.setdefault('successes', 0)
    item.setdefault('mistakes', 0)
    item.setdefault('streak', 0)
    if success:
        item['successes'] += 1
        item['streak'] = 0 if assisted else min(item['streak'] + 1, len(INTERVAL_DAYS))
        item['due'] = now + 86400 * INTERVAL_DAYS[max(0, item['streak'] - 1)]
    else:
        item['mistakes'] += 1
        item['streak'] = 0
        item['due'] = now
    item['last'] = now
    result[puzzle_id] = item
    if len(result) > 10000:
        oldest = min((key for key in result if key != puzzle_id), key=lambda key: result[key].get('last', 0))
        del result[oldest]
    return result


def recommend(puzzles, stats, solved=(), now=None):
    now = time.time() if now is None else now
    from curriculum import puzzle_level
    due = [p for p in puzzles if p.id in stats and stats[p.id].get('due', 0) <= now]
    if due:
        chosen = min(due, key=lambda p: (stats[p.id].get('streak', 0), stats[p.id].get('due', 0), p.id))
        return chosen, 'Review due: revisit an exercise before moving on.'
    mastered = sum(item.get('streak', 0) > 0 for item in stats.values())
    unlocked = min(3, 1 + mastered // 3)
    fresh = [p for p in puzzles if p.id not in stats and p.id not in solved]
    eligible = [p for p in fresh if puzzle_level(p.id) <= unlocked]
    if eligible:
        return min(eligible, key=lambda p: (puzzle_level(p.id), p.id)), f'New exercise: practice level {unlocked} is available.'
    if fresh:
        return min(fresh, key=lambda p: (puzzle_level(p.id), p.id)), 'Next available exercise; use hints when needed.'
    if puzzles:
        return min(puzzles, key=lambda p: stats.get(p.id, {}).get('due', 0)), 'Nothing is due yet; optional review of the next scheduled exercise.'
    return None, 'No exercises available.'
