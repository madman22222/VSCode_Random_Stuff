"""Launcher for the chess application.

Default behavior launches the GUI. Use CLI flags to run headless training.
"""

import argparse
import sys
import time


def run_gui() -> None:
    import tkinter as tk
    from game_controller import GameController

    root = tk.Tk()
    app = GameController(root)
    root.mainloop()


def run_training(args) -> int:
    """Run headless Training AI without GUI using CLI parameters."""
    from game_controller import SimpleAI, TrainingAI

    depth = max(1, int(args.depth))
    batch_size = max(1, int(args.batch_size))
    move_time_sec = max(0.05, float(args.move_ms) / 1000.0)
    snapshot_batches = int(args.snapshot_batches)
    export_interval = None if snapshot_batches <= 0 else snapshot_batches
    total_games = int(args.games)
    compress = not bool(args.no_compress)

    ai = SimpleAI(depth=depth)
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
    )
    trainer.start()

    if total_games > 0:
        # Wait until desired number of games completes
        try:
            while trainer.games_played < total_games:
                time.sleep(0.25)
        except KeyboardInterrupt:
            pass
        finally:
            trainer.stop()
    else:
        # Run until interrupted
        print("Press Ctrl+C to stop training...")
        try:
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            pass
        finally:
            trainer.stop()

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
    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.training:
        return run_training(args)
    else:
        run_gui()
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
# pyright: reportMissingImports=false, reportUnknownMemberType=false
