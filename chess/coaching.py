"""Select useful review moments without presenting shallow search as certainty."""

def topic_for(row):
    text = ' '.join(row.get('facts', []) + row.get('played_facts', [])).lower()
    if 'checkmate' in text:
        return 'mates', 'mate-white'
    if 'pin' in text:
        return 'pins', 'guided:pin'
    if 'multiple' in text:
        return 'forks', 'guided:fork'
    if 'capture to inspect' in text:
        return 'defense', 'extended:block-check'
    if 'check' in text:
        return 'forcing moves', 'guided:discovery'
    import chess
    if row.get('fen_before') and len(chess.Board(row['fen_before']).piece_map()) <= 10:
        return 'endgame technique', 'guided:rook-mate'
    return ('opening principles', 'extended:develop') if row.get('ply', 0) < 12 else ('endgame technique', 'guided:rook-mate')


def coaching_moments(rows, limit=3):
    if limit <= 0:
        return []
    ranked = sorted(enumerate(rows), key=lambda pair: (-(pair[1].get('estimated_loss_cp') or 0), pair[0]))
    selected = []
    # Prefer different ideas; then fill remaining slots with distinct positions.
    for unique_topics in (True, False):
        for index, row in ranked:
            if any(item['index'] == index for item in selected):
                continue
            enriched = dict(row, ply=index)
            topic, puzzle_id = topic_for(enriched)
            if unique_topics and any(item['topic'] == topic for item in selected):
                continue
            selected.append({'index': index, 'topic': topic, 'puzzle_id': puzzle_id,
                'text': f"Move {row.get('move_number', index // 2 + 1)}{('...' if row['side'] == 'black' else '.') if 'side' in row else ('.' if index % 2 == 0 else '...')} {row['san']}: inspect {topic}. "
                        f"Search suggested {row['suggested']}. " +
                        (' '.join(row.get('facts', [])) or row.get('reason', 'Compare checks, captures and threats.')) +
                        ' Budget-limited suggestion; verify the reply.'})
            if len(selected) == limit:
                return selected
    return selected
