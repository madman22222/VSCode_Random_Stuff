# Chess Studio project instructions

The Windows portable application and the VS Code developer edition must receive
the same application changes. Keep one canonical implementation in `chess/`,
launched through `chess/main.py`. Do not fork or copy the game logic into separate
edition directories. Edition-specific resource/data paths belong in `app_paths.py`.

The release workflow builds both ZIPs from the same commit, tests them after
extraction, uploads all assets to a draft, and publishes only after success.
Source edits require a rebuilt portable EXE; do not imply that old downloads or
personal profile data synchronize automatically. Keep the VS Code workspace,
launcher, developer guide and shared source-file packaging current.

Run `python run_tests.py`; desktop tests need a display. Changes to application or
packaging paths require the source-edition and actual frozen-Windows smoke checks
in CI. Keep user saves/training data out of source/build artifacts. Preserve
unreadable data and use the existing profile backup/restore and writer leases.

Update documentation and KANBAN.md with evidence. Do not mark real Windows DPI,
screen-reader, signing or other-platform checks complete without actual results.
PDF study references are not executable training data and are not redistributed
with the program. Do not claim that bounded search solves every textbook tactic.
