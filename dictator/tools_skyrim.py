"""Skyrim tools: state, console, face, follow, pivot, compound_move, compile_papyrus."""

import json
import shlex
from pathlib import Path

from dictator.core import mcp, run_cmd, SKYRIM_STATE_FILE, PAPYRUS_COMPILER


@mcp.tool()
async def skyrim_read_state(path: str = "") -> str:
    """Read Skyrim state JSON (optionally a dot-path like 'player.health')."""
    try:
        if not SKYRIM_STATE_FILE.exists():
            return json.dumps({"ok": False, "message": "Skyrim state file not found"})
        state = json.loads(SKYRIM_STATE_FILE.read_text())
        if path:
            value = state
            for key in path.split("."):
                value = value[key]
            return json.dumps({"ok": True, "path": path, "value": value}, indent=2)
        return json.dumps({"ok": True, **state}, indent=2)
    except Exception as e:
        return json.dumps({"ok": False, "message": str(e)})


@mcp.tool()
async def skyrim_console(commands: list[str]) -> str:
    """Send console commands to Skyrim via xdotool."""
    try:
        r = await run_cmd('xdotool search --name "Skyrim Special Edition"', cwd="/tmp")
        if r.get("ok"):
            for wid in r["stdout"].strip().split("\n"):
                wid = wid.strip()
                if not wid:
                    continue
                name_r = await run_cmd(f"xdotool getwindowname {wid}", cwd="/tmp")
                name = name_r.get("stdout", "")
                if "Mod Organizer" not in name:
                    await run_cmd(f"xdotool windowactivate --sync {wid} windowfocus --sync {wid}", cwd="/tmp")
                    break

        await run_cmd("xdotool key grave", cwd="/tmp")
        for cmd in commands:
            await run_cmd(f"xdotool type --delay 12 -- {shlex.quote(cmd)}", cwd="/tmp")
            await run_cmd("xdotool key Return", cwd="/tmp")
        await run_cmd("xdotool key grave", cwd="/tmp")

        return json.dumps({"ok": True, "commands": commands})
    except Exception as e:
        return json.dumps({"ok": False, "message": str(e)})


@mcp.tool()
async def skyrim_face_actor(actor_id: str = "player") -> str:
    """Make the specified actor face the camera."""
    cmd = [f"prid {actor_id}", "lookat player"]
    return await skyrim_console(cmd)


@mcp.tool()
async def skyrim_follow_actor(actor_id: str, target_id: str = "player") -> str:
    """Make an actor follow a target."""
    cmd = [f"prid {actor_id}", "setav variable01 1", "evp"]
    return await skyrim_console(cmd)


@mcp.tool()
async def skyrim_pivot(degrees: float) -> str:
    """Turn the player in place by a relative degree using dynamic mouse calibration (~300px per 90deg)."""
    state_r = await skyrim_read_state()
    state = json.loads(state_r)
    if not state.get("ok"):
        return state_r

    px_to_move = int(degrees * 3.33)
    await run_cmd(f"xdotool mousemove_relative -- {px_to_move} 0", cwd="/tmp")

    return json.dumps({"ok": True, "degrees": degrees, "px_moved": px_to_move})


@mcp.tool()
async def skyrim_compound_move(look_dx: int = 0, direction: str = "") -> str:
    """Execute a turn or a move command. Passing look_dx without a direction turns in place."""
    if look_dx != 0:
        await run_cmd(f"xdotool mousemove_relative -- {look_dx} 0", cwd="/tmp")

    if direction:
        key_map = {"forward": "w", "back": "s", "left": "a", "right": "d"}
        key = key_map.get(direction.lower())
        if key:
            await run_cmd(f"xdotool keydown {key} sleep 0.5 keyup {key}", cwd="/tmp")

    return json.dumps({"ok": True, "look_dx": look_dx, "direction": direction})


@mcp.tool()
async def compile_papyrus(mod_name: str, scripts: list[str] | None = None) -> str:
    """
    Compile Papyrus scripts using compile_papyrus.sh.
    mod_name: The folder name under MO2/mods/.
    scripts: Optional list of .psc basenames (without extension). If omitted, all scripts in the mod are compiled.
    """
    if not PAPYRUS_COMPILER.exists():
        return json.dumps({"ok": False, "message": f"Compiler script not found at {PAPYRUS_COMPILER}"})

    cmd = f"bash {shlex.quote(str(PAPYRUS_COMPILER))} {shlex.quote(mod_name)}"
    if scripts:
        cmd += " " + " ".join(shlex.quote(s) for s in scripts)

    r = await run_cmd(cmd, cwd=PAPYRUS_COMPILER.parent)
    r["command"] = cmd
    return json.dumps(r, indent=2)
