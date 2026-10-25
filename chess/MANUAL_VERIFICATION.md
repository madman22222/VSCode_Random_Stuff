# Remaining hands-on checks

Automated Linux desktop tests exercise resizing, cached rendering, keyboard input,
large text, contrast, game/practice/review isolation, and background cancellation.
Windows CI exercises desktop and frozen-package paths. Those checks cannot verify
all Windows display drivers or assistive technologies.

## Windows display scaling — issue #11

On a real Windows 10/11 x64 laptop/desktop, record build revision, graphics driver,
display size and scaling. At 100%, 125%, 150%, and 200% scaling check:

- [ ] Start, maximize, restore, resize, and switch between monitors.
- [ ] All tabs and the Support & study menu are reachable; no stale pixels after interaction.
- [ ] Board clicks/focus match the displayed square, including Black orientation.
- [ ] Normal and Large text, contrast and all piece styles remain readable.
- [ ] Training Dashboard / Run settings / Memory pages do not clip controls.
- [ ] Practice lesson selection, automatic replies, hints and saved completion remain usable.
- [ ] Review line/details and its export are readable without covering navigation.

Record failures with reproduction steps. Native tabs remove the old scrolling
canvas path, but real driver behavior remains to be checked.

## Keyboard and screen reader — issue #22

- [ ] Complete a game, training start/stop, backup/restore preview and review without a mouse.
- [ ] Tab order and menu access work; arrow keys stay with form fields when editing.
- [ ] Verify board focus/status, selected pieces, moves and errors using NVDA/Narrator.
- [ ] Check high-contrast colors and large text on the actual display.

The board now exposes focus square/piece in visible feedback and supports keyboard
selection. Tk Canvas accessibility and automatic screen-reader announcements are
not proven; record concrete limitations before claiming support. Do not close the
accessibility audit based only on synthesized key events.

## Upgrade and interruption check

- [ ] Back up a real previous-version profile, extract the new ZIP elsewhere, and
      copy the entire old data folder into it; leave the backup unchanged.
- [ ] Confirm unfinished PGN/clock state, named profiles and solved practice remain
      available; train/save/restart/resume and compare the counters.
- [ ] Keep all `.checkpoint.json` files on subsequent upgrades. If gameplay/imports
      changed memory after training, verify Resume explains why exact counters
      cannot be reused and Start preserves that memory.

CI tests extracted source/frozen builds with temporary profiles and automated
interruption cases. This checklist records the owner/device-specific upgrade
experience; it has not been marked complete by those automated checks.
