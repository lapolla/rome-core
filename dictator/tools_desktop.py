"""Desktop automation tools: screenshot, click, type, press_key, find/focus window, mouse, notify."""

import json
import shlex
import time

from dictator.core import run_cmd


def register(registry):
    """Register Desktop tools with the given native ROME registry instance."""

    @registry.tool()
    async def desktop_screenshot(window_id: str = "") -> str:
        """Capture a screenshot. Returns path to the saved image."""
        path = f"/tmp/screenshot_{int(time.time())}.png"
        cmd = f"scrot {shlex.quote(path)}"
        if window_id:
            cmd = f"scrot -u {shlex.quote(path)} --window {shlex.quote(window_id)}"

        r = await run_cmd(cmd, cwd="/tmp")
        if r.get("ok"):
            return json.dumps({"ok": True, "path": path})
        return json.dumps(r)

    @registry.tool()
    async def desktop_click(x: int, y: int, button: int = 1, clicks: int = 1, window_id: str = "") -> str:
        """Click at screen coordinates."""
        if window_id:
            await run_cmd(f"xdotool windowactivate --sync {shlex.quote(window_id)}", cwd="/tmp")

        cmd = f"xdotool mousemove {x} {y} click --repeat {clicks} {button}"
        r = await run_cmd(cmd, cwd="/tmp")
        return json.dumps(r)

    @registry.tool()
    async def desktop_type_text(text: str, delay_ms: int = 12) -> str:
        """Type text via xdotool."""
        cmd = f"xdotool type --delay {delay_ms} -- {shlex.quote(text)}"
        r = await run_cmd(cmd, cwd="/tmp")
        return json.dumps(r)

    @registry.tool()
    async def desktop_press_key(key: str) -> str:
        """Press a key combo (e.g. 'Return', 'alt+F4')."""
        cmd = f"xdotool key --clearmodifiers {shlex.quote(key)}"
        r = await run_cmd(cmd, cwd="/tmp")
        return json.dumps(r)

    @registry.tool()
    async def desktop_find_window(name: str = "", class_name: str = "") -> str:
        """Find window IDs by title or class."""
        if name:
            cmd = f"xdotool search --name {shlex.quote(name)}"
        elif class_name:
            cmd = f"xdotool search --class {shlex.quote(class_name)}"
        else:
            return json.dumps({"ok": False, "message": "Must provide name or class_name"})

        r = await run_cmd(cmd, cwd="/tmp")
        ids = r.get("stdout", "").strip().split("\n") if r.get("ok") else []
        return json.dumps({"ok": r.get("ok"), "ids": [i for i in ids if i]})

    @registry.tool()
    async def desktop_focus_window(window_id: str) -> str:
        """Activate and focus a window."""
        r = await run_cmd(f"xdotool windowactivate --sync {shlex.quote(window_id)} windowfocus --sync {shlex.quote(window_id)}", cwd="/tmp")
        return json.dumps(r)

    @registry.tool()
    async def desktop_get_mouse_location() -> str:
        """Get current mouse X, Y coordinates."""
        r = await run_cmd("xdotool getmouselocation --shell", cwd="/tmp")
        return json.dumps({"ok": r.get("ok"), "data": r.get("stdout", "").strip()})

    @registry.tool()
    async def desktop_notify(message: str, title: str = "ROME", urgency: str = "normal", expire_ms: int = 5000) -> str:
        """Show a desktop notification using notify-send."""
        cmd = f"notify-send -t {expire_ms} -u {shlex.quote(urgency)} {shlex.quote(title)} {shlex.quote(message)}"
        r = await run_cmd(cmd, cwd="/tmp")
        return json.dumps(r)
