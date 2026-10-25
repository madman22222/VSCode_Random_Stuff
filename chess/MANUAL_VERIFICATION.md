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
