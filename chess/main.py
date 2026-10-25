"""Launcher for the chess application.

Default behavior launches the GUI. Use CLI flags to run headless training.
"""

import argparse
import sys
from simple_ai import SimpleAI
from training_ai import TrainingAI


def run_gui() -> None:
    import tkinter as tk
    from game_controller import GameController

    root = tk.Tk()
    app = GameController(root)
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

    trainer = TrainingAI(
        ai_instance=ai,
        depth=depth,
        batch_size=batch_size,
        export_interval=export_interval,
        move_time_limit=move_time_sec,
        max_games=total_games,
        max_moves=args.max_plies,
    )
    trainer.start()

    print("Training started. Press Ctrl+C to stop and save.")
    try:
        while trainer.thread.is_alive():
            trainer.thread.join(timeout=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        trainer.stop()
    if trainer.last_error:
        print(f"Training failed: {trainer.last_error}", file=sys.stderr)
        return 1

    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Chess GUI and headless training")
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

    if args.games < 0 or args.depth < 1 or args.max_plies < 1 or args.move_ms < 1 or args.batch_size < 1:
        parser.error("Depth, move time, batch size and max plies must be positive; games cannot be negative")

    if args.training:
        return run_training(args)
    else:
        run_gui()
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
# pyright: reportMissingImports=false, reportUnknownMemberType=false
