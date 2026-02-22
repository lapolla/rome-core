# FIXME — MCP Server Issues

## SOLVED: Proper pivot/turn-in-place tool
- `skyrim_pivot` tool implemented using dynamic mouse calibration (~300px per 90deg base).
- Uses `SkyrimStateExporter` heading data to calibrate `pxPerDegree` on the fly.
- `skyrim_compound_move` can now turn in place by passing `look_dx` without a `direction`.

## SOLVED: Key sending to Wine/Proton
- xdotool DOES work for MCM Helper keybinds — the issue was wrong key names
- **Required recipe**: click inside window first (Wine focus), then `xdotool keydown --clearmodifiers <key> && sleep 0.12 && xdotool keyup --clearmodifiers <key>`
- SexLabMadness hotkeys: `backslash` = toggle, `minus` = alter passive, `equal` = alter active
- ydotool/evdev NOT needed — xdotool is sufficient with proper focus + clearmodifiers
