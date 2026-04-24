# Notify Effect: Hacker Lock

This note preserves the fourth notify animation prototype so it can be rebuilt
later without relying on conversation context.

## Visual Idea

The target pane is treated like a terminal HUD. Four corner brackets start near
the pane edges and converge toward the center while short diagnostic strings
flicker inside the frame. The effect ends with a locked target card:

```text
TARGET LOCKED: BOBO
window=613:6 pane=%4143
```

The feel should be tactical and terminal-native, not game-like. It should read
as "Hive has acquired the pane that needs attention."

## Timing

- Full-pane borderless `tmux display-popup` overlay.
- Bracket converge: about 0.6-0.8s.
- Lock pulse: about 0.5-0.8s.
- Collapse/exit: about 0.2s.
- Total target duration: 1.4-1.8s.

## Motion Beats

1. Clear overlay and hide cursor.
2. Draw four HUD corners at the outer pane region.
3. Move corners inward using cubic ease-out.
4. During convergence, sprinkle short green diagnostic strings.
5. After halfway, show a `SCAN <hex/noise>` line near center.
6. Flash a centered target card with `TARGET LOCKED: <agent>`.
7. Show a small diagnostic line with window and pane id.
8. Collapse to a short green horizontal line and clear.
9. Restore cursor.

## Demo Script Shape

The prototype used a full-pane popup and generated all content inside Python:

```sh
tmux display-popup \
  -c "$client_tty" \
  -t "$target_pane" \
  -B \
  -x '#{popup_pane_left}' \
  -y '#{popup_pane_top}' \
  -w "$pane_width" \
  -h "$pane_height" \
  -E "python3 - <<'PY'
# Python animation body:
# - get terminal size via shutil.get_terminal_size()
# - define at(y, x, text)
# - define corner(y, x, sx, sy)
# - converge corners with ease-out
# - render random diagnostic strings from '01ABCDEF/%#@{}[]'
# - pulse centered target box
# - clear and restore cursor
PY"
```

## Implementation Notes

- Keep it as an optional theme or experimental effect, not the only reliable
  notify surface.
- The reliable pane marker remains `@hive-notify-active` plus
  `pane-border-format`.
- Do not write escape sequences to the target pane TTY.
- Do not pass `#{pane_top}` as numeric `display-popup -y`; tmux positions
  numeric `-y` by the popup bottom edge, which pushes full-height popups for
  lower splits into the pane above. Use `#{popup_pane_top}` instead.
- Use `display-popup -c <client>` only when the active client can be resolved.
- Fall back silently to the border marker if popup/client resolution fails.
- Template variables should be `<agent>`, `<window_target>`, and `<pane_id>`.

## Known Tradeoffs

- Popup is client-local, not pane-local. Multi-client tmux sessions can show it
  on the wrong client unless a concrete client tty is passed.
- It is intentionally strong and cinematic. It may be too loud as the default
  repeated notify effect, but it is a good candidate for an optional visual
  theme.
