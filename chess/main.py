"""Launcher for the chess application.

Default behavior launches the GUI. Use CLI flags to run headless training.
"""

import argparse
import sys
from simple_ai import SimpleAI
from training_ai import TrainingAI, ComparisonSeries


def run_gui() -> None:
    import tkinter as tk
    from game_controller import GameController

    root = tk.Tk()
    GameController(root)
    root.mainloop()


def run_training(args) -> int:
    """Run headless Training AI without GUI using CLI parameters."""

    depth = max(1, int(args.depth))
    batch_size = max(1, int(args.batch_size))
    move_time_sec = max(0.001, float(args.move_ms) / 1000.0)
    snapshot_batches = int(args.snapshot_batches)
    export_interval = None if snapshot_batches <= 0 else snapshot_batches
    total_games = int(args.games)
    compress = not bool(args.no_compress)

    ai = SimpleAI(depth=depth, learning_path=args.learning_file)
    # Apply compression preference up front
    try:
        ai.compress_learning = compress
    except Exception:
        pass

    from parallel_training import training_factory
    trainer = training_factory(
        ai_instance=ai, workers=args.workers, cpu_percent=args.cpu_percent, checkpoint_keep=args.checkpoint_keep,
        depth=depth,
        batch_size=batch_size,
        export_interval=export_interval,
        move_time_limit=move_time_sec,
        max_games=total_games,
        max_moves=args.max_plies,
        exploration_rate=args.exploration,
        varied_starts=not args.no_varied_starts,
        seed=args.seed, resume=args.resume,
    )
    try:
        trainer.start()
    except (OSError, ValueError, RuntimeError) as exc:
        print(f'Cannot start training: {exc}', file=sys.stderr)
        return 1

    print("Training started. Press Ctrl+C to stop and save.")
    try:
        while trainer.thread.is_alive():
            trainer.thread.join(timeout=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        trainer.stop()
    print(f"Training stopped: {trainer.games_played} games; {trainer.results}")
    if trainer.last_error:
        print(f"Training failed: {trainer.last_error}", file=sys.stderr)
        return 1

    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Chess GUI and headless training")
    p.add_argument("--diagnostics-report", help="Run bundled startup/gameplay checks and write a JSON report")
    p.add_argument("--against", choices=("both", "untrained", "previous"), default="both", help="Comparison opponents")
    p.add_argument("--experiment", action="store_true", help="Test confidence-weighted root scoring without enabling it")
    p.add_argument("--benchmark", action="store_true", help="Compare saved learning against an untrained engine")
    p.add_argument("--resume", action="store_true", help="Resume saved training counters; games is the additional game limit")
    p.add_argument("--exploration", type=float, default=0.10, help="Early-game exploration probability (0 to 1)")
    p.add_argument("--no-varied-starts", action="store_true", help="Always train from the initial position")
    p.add_argument("--seed", type=int, default=42, help="Opening/exploration random seed")
    p.add_argument("--nodes", type=int, default=500, help="Comparison search nodes per move")
    p.add_argument("--workers", type=int, default=1, help="Training workers: 1 preserves online learning; 2–8 uses frozen waves")
    p.add_argument("--cpu-percent", type=int, default=100, help="Approximate per-worker CPU duty, 10–100")
    p.add_argument("--checkpoint-keep", type=int, default=3, help="Retain 1–10 rolling checkpoint generations")
    p.add_argument("--training", action="store_true", help="Run headless Training AI instead of GUI")
    p.add_argument("--depth", type=int, default=3, help="AI search depth (default: 3)")
    p.add_argument("--batch-size", type=int, default=100, help="Training: games per batch before saving (default: 100)")
    p.add_argument("--move-ms", type=int, default=250, help="Training: per-move time budget in ms (default: 250)")
    p.add_argument("--snapshot-batches", type=int, default=0, help="Training: export readable every N batches (0=off)")
    p.add_argument("--games", type=int, default=0, help="Training: stop after N games (0=run until Ctrl+C)")
    p.add_argument("--no-compress", action="store_true", help="Disable gzip compression for learning data")
    p.add_argument("--learning-file", default=None, help="Learning JSON path (automatically reloaded next run)")
    p.add_argument("--max-plies", type=int, default=300, help="Maximum half-moves per training game")
    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.diagnostics_report:
        from diagnostics import run_diagnostics
        return run_diagnostics(args.diagnostics_report)

    if args.games < 0 or args.depth < 1 or args.max_plies < 1 or args.move_ms < 1 or args.batch_size < 1:
        parser.error("Depth, move time, batch size and max plies must be positive; games cannot be negative")

    if not 0 <= args.exploration <= 1 or args.nodes < 1:
        parser.error("Exploration must be between 0 and 1; nodes must be positive")
    if not 1 <= args.workers <= 8 or not 10 <= args.cpu_percent <= 100 or not 1 <= args.checkpoint_keep <= 10:
        parser.error("Workers: 1–8; CPU duty: 10–100; checkpoints: 1–10")
    if args.training and args.benchmark:
        parser.error("Choose training or comparison, not both")
    if args.benchmark:
        import json
        games = args.games or 20
        if games < 2 or games % 2:
            parser.error("Comparison requires an even number of games (at least 2)")
        runner = ComparisonSeries(SimpleAI(learning_path=args.learning_file), games=games,
                                 depth=args.depth, node_limit=args.nodes,
                                 max_moves=args.max_plies, seed=args.seed, against=args.against, experimental=args.experiment)
        runner.start()
        try:
            while runner.thread.is_alive():
                runner.thread.join(0.25)
        except KeyboardInterrupt:
            runner.stop()
        print(json.dumps(runner.result, indent=2))
        return 1 if runner.last_error else 0
    if args.training:
        return run_training(args)
    else:
        run_gui()
        return 0


if __name__ == '__main__':
    import multiprocessing
    multiprocessing.freeze_support()
    raise SystemExit(main())
# pyright: reportMissingImports=false, reportUnknownMemberType=false
