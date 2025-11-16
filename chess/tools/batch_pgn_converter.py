"""batch_pgn_converter

Placeholder module replacing an assumed legacy .NET "Batch Convert PGN" tool.

Purpose:
    Provide a Python implementation stub for batch conversion of PGN files
    located in a directory into alternative serialized formats (currently JSON
    and a simple text summary). Intended for later expansion (e.g., CSV, DB load,
    feature extraction for AI training, statistics aggregation).

Design Goals:
    - Minimal, dependency-light (relies on python-chess already in requirements).
    - Clear extension points via functions and simple Strategy-style handler map.
    - Safe file handling: never overwrites existing outputs unless force=True.
    - Resilient: continues processing other files when one fails, aggregates errors.

CLI Usage (placeholder):
    python -m chess.tools.batch_pgn_converter --input autosaves --output converted --format json

Public API:
    convert_pgn_file(input_path: str, output_path: str, fmt: str = 'json', force: bool = False) -> dict
        Parse single PGN and write converted artifact.
    batch_convert(input_dir: str, output_dir: str, pattern: str = '*.pgn', fmt: str = 'json', force: bool = False) -> dict
        Iterate over PGN files, perform conversion, return report.
    summarize_game(game: chess.pgn.Game) -> dict
        Extract lightweight summary metadata.

Future Enhancements (placeholder notes):
    - Add threading for large directories.
    - Add advanced statistics (material imbalance charts, opening classification).
    - Integrate with training AI pipeline (feeding converted data).
    - Support incremental conversion (skip unchanged PGNs using mtime hash cache).

"""
from __future__ import annotations

import os
import sys
import json
import glob
import argparse
from typing import List, Dict, Any, Tuple

try:
    import chess.pgn  # type: ignore
except Exception as e:  # pragma: no cover
    raise RuntimeError("python-chess must be installed to use batch_pgn_converter") from e

DEFAULT_FORMAT = "json"
SUPPORTED_FORMATS = {"json", "summary", "csv", "minimal"}


def summarize_game(game: "chess.pgn.Game") -> Dict[str, Any]:
    """Return a lightweight summary for a single PGN game.

    Fields included (extend as needed):
        - result: Game result string from PGN headers (e.g., "1-0")
        - white: White player name
        - black: Black player name
        - ply_count: Half-move count
        - moves: Simple SAN move list (optional; can be large)

    NOTE: This keeps moves for transparency; remove if size is an issue.
    """
    headers = game.headers
    moves: List[str] = []
    node = game
    while node and node.variations:
        node = node.variations[0]
        try:
            moves.append(node.move.san())  # python-chess move SAN
        except Exception:
            try:
                moves.append(node.san())
            except Exception:
                moves.append("?")

    return {
        "result": headers.get("Result", "*"),
        "white": headers.get("White", "Unknown"),
        "black": headers.get("Black", "Unknown"),
        "ply_count": len(moves),
        "moves": moves,
    }


def _read_all_games(path: str) -> List["chess.pgn.Game"]:
    games: List["chess.pgn.Game"] = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        while True:
            g = chess.pgn.read_game(f)
            if g is None:
                break
            games.append(g)
    return games


def convert_pgn_file(input_path: str, output_path: str, fmt: str = DEFAULT_FORMAT, force: bool = False, multi: bool = True) -> Dict[str, Any]:
    """Convert a single PGN file to the requested format (supports multi-game PGNs).

    Parameters:
        input_path: Path to source .pgn file.
        output_path: Target file path (extension managed by caller).
        fmt: One of SUPPORTED_FORMATS.
        force: Overwrite existing output if True.

    Returns:
        report dict with keys: 'input', 'output', 'status', 'error' (optional).

    Behavior:
        - Parses only the first game if multiple present (extendable).
        - Writes JSON summary or plain text summary.
    """
    report = {"input": input_path, "output": output_path, "status": "pending"}
    if fmt not in SUPPORTED_FORMATS:
        report["status"] = "skipped"
        report["error"] = f"Unsupported format: {fmt}"
        return report

    if not os.path.isfile(input_path):
        report["status"] = "error"
        report["error"] = "Input file not found"
        return report

    if os.path.exists(output_path) and not force:
        report["status"] = "skipped"
        report["error"] = "Output exists (use force=True to overwrite)"
        return report

    try:
        games = _read_all_games(input_path) if multi else games  # if multi False, undefined; multi always True here
        if not games:
            report["status"] = "error"
            report["error"] = "No games parsed (empty or invalid PGN)"
            return report
        summaries = [summarize_game(g) for g in games]
        if fmt == "json":
            with open(output_path, "w", encoding="utf-8") as out:
                json.dump(summaries if len(summaries) > 1 else summaries[0], out, separators=(",", ":"))
        elif fmt == "summary":
            blocks: List[str] = []
            for i, summary in enumerate(summaries, start=1):
                lines = [
                    f"Game {i}",
                    f"Result: {summary['result']}",
                    f"White: {summary['white']}",
                    f"Black: {summary['black']}",
                    f"Ply Count: {summary['ply_count']}",
                    "Moves:",
                    " ".join(summary["moves"]),
                ]
                blocks.append("\n".join(lines))
            with open(output_path, "w", encoding="utf-8") as out:
                out.write("\n\n".join(blocks))
        elif fmt == "csv":
            import csv
            with open(output_path, 'w', newline='', encoding='utf-8') as fcsv:
                writer = csv.writer(fcsv)
                writer.writerow(["game","ply","color","san","result","white","black"])
                for gi, summary in enumerate(summaries, start=1):
                    color = True
                    for idx, san in enumerate(summary["moves"], start=1):
                        writer.writerow([gi, idx, 'W' if color else 'B', san, summary['result'], summary['white'], summary['black']])
                        color = not color
        elif fmt == "minimal":
            with open(output_path, "w", encoding="utf-8") as out:
                for summary in summaries:
                    out.write(" ".join(summary["moves"]))
                    out.write("\n")
        report["status"] = "ok"
    except Exception as e:  # pragma: no cover
        report["status"] = "error"
        report["error"] = str(e)
    return report


def batch_convert(input_dir: str, output_dir: str, pattern: str = "*.pgn", fmt: str = DEFAULT_FORMAT, force: bool = False, aggregate_csv: bool = True) -> Dict[str, Any]:
    """Batch convert PGN files from input_dir to output_dir.

    Parameters:
        input_dir: Directory containing PGN files.
        output_dir: Destination directory for converted artifacts.
        pattern: Glob pattern for PGN selection (default '*.pgn').
        fmt: Conversion format (json or summary).
        force: Overwrite existing outputs.

    Returns:
        Aggregate report dict: { 'total': int, 'ok': int, 'skipped': int, 'error': int, 'files': [file reports...] }
    """
    os.makedirs(output_dir, exist_ok=True)
    files = glob.glob(os.path.join(input_dir, pattern))
    reports: List[Dict[str, Any]] = []
    counts = {"ok": 0, "skipped": 0, "error": 0}

    aggregate_rows: List[Tuple] = []
    for fpath in files:
        base = os.path.splitext(os.path.basename(fpath))[0]
        if fmt == 'json':
            ext = 'json'
        elif fmt == 'csv':
            ext = 'csv'
        else:
            ext = 'txt'
        out_path = os.path.join(output_dir, f"{base}.{ext}")
        rep = convert_pgn_file(fpath, out_path, fmt=fmt, force=force, multi=True)
        reports.append(rep)
        if rep["status"] in counts:
            counts[rep["status"]] += 1
        # Collect rows for aggregate CSV
        if fmt == 'csv' and rep['status'] == 'ok':
            # Re-open produced CSV and append rows
            import csv
            try:
                with open(out_path, 'r', encoding='utf-8') as fcsv:
                    reader = csv.reader(fcsv)
                    header = next(reader, [])
                    for row in reader:
                        if row and row[0].startswith('#'):
                            continue
                        # Expect columns: game, ply, color, san, result, white, black
                        if len(row) == 7:
                            aggregate_rows.append((base,)+tuple(row))
            except Exception:
                pass

    # Write aggregate CSV if requested
    if fmt == 'csv' and aggregate_csv and aggregate_rows:
        import csv
        agg_path = os.path.join(output_dir, 'aggregate.csv')
        if not (os.path.exists(agg_path) and not force):
            with open(agg_path, 'w', newline='', encoding='utf-8') as fagg:
                writer = csv.writer(fagg)
                writer.writerow(["file","game","ply","color","san","result","white","black"])
                for row in aggregate_rows:
                    writer.writerow(row)

    return {
        "total": len(files),
        **counts,
        "files": reports,
    }


def _parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch convert PGN files (placeholder module)")
    parser.add_argument("--input", required=True, help="Input directory containing .pgn files")
    parser.add_argument("--output", required=True, help="Output directory for converted files")
    parser.add_argument("--pattern", default="*.pgn", help="Glob pattern for PGN selection")
    parser.add_argument("--format", default=DEFAULT_FORMAT, choices=sorted(SUPPORTED_FORMATS), help="Output format")
    parser.add_argument("--force", action="store_true", help="Overwrite existing outputs")
    parser.add_argument("--no-aggregate", action="store_true", help="Disable aggregate CSV output (csv format only)")
    parser.add_argument("--print-report", action="store_true", help="Print JSON report to stdout")
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    report = batch_convert(args.input, args.output, pattern=args.pattern, fmt=args.format, force=args.force, aggregate_csv=not args.no_aggregate)
    if args.print_report:
        print(json.dumps(report, indent=2))
    else:
        print(f"Converted {report['ok']} OK / {report['skipped']} skipped / {report['error']} errors (total {report['total']})")
    return 0 if report['error'] == 0 else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
