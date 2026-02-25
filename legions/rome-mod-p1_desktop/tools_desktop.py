import time
import json
import shlex
from dictator.core import mcp, run_cmd

@mcp.tool()
def desktop_screenshot(window_id: str = "") -> str:
    """Takes a screenshot using scrot. If window_id is provided, captures that window."""
    timestamp = int(time.time())
    path = f"/tmp/screenshot_{timestamp}.png"
    cmd = f"scrot {shlex.quote(path)}"
    if window_id:
        cmd = f"scrot -u -i {shlex.quote(window_id)} {shlex.quote(path)}"
    
    result = run_cmd(cmd)
    return json.dumps({"path": path, "output": result})

@mcp.tool()
def desktop_click(x: int, y: int, button: int = 1, clicks: int = 1, window_id: str = "") -> str:
    """Clicks at the specified coordinates using xdotool."""
    if window_id:
        run_cmd(f"xdotool windowactivate --sync {shlex.quote(window_id)}")
    
    cmd = f"xdotool mousemove --sync {x} {y} click --repeat {clicks} --delay 100 {button}"
    result = run_cmd(cmd)
    return json.dumps({"status": "clicked", "coords": (x, y), "output": result})

@mcp.tool()
def desktop_type_text(text: str, delay_ms: int = 12) -> str:
    """Types text using xdotool with a specified delay between keystrokes."""
    cmd = f"xdotool type --delay {delay_ms} {shlex.quote(text)}"
    result = run_cmd(cmd)
    return json.dumps({"status": "typed", "text": text, "output": result})

@mcp.tool()
def desktop_press_key(key: str) -> str:
    """Presses a specific key combination using xdotool."""
    cmd = f"xdotool key --clearmodifiers {shlex.quote(key)}"
    result = run_cmd(cmd)
    return json.dumps({"status": "pressed", "key": key, "output": result})

@mcp.tool()
def desktop_find_window(name: str = "", class_name: str = "") -> str:
    """Finds window IDs by name or class name using xdotool."""
    args = []
    if name:
        args.append(f"--name {shlex.quote(name)}")
    if class_name:
        args.append(f"--class {shlex.quote(class_name)}")
    
    if not args:
        return json.dumps({"error": "Must provide name or class_name"})
    
    cmd = f"xdotool search {' '.join(args)}"
    try:
        result = run_cmd(cmd).strip().split('
')
        ids = [i for i in result if i]
    except Exception:
        ids = []
    
    return json.dumps({"window_ids": ids})

@mcp.tool()
def desktop_focus_window(window_id: str) -> str:
    """Focuses a window by its ID."""
    cmd = f"xdotool windowactivate --sync {shlex.quote(window_id)}"
    result = run_cmd(cmd)
    return json.dumps({"status": "focused", "window_id": window_id, "output": result})

@mcp.tool()
def desktop_get_mouse_location() -> str:
    """Returns the current mouse coordinates and window ID."""
    cmd = "xdotool getmouselocation --shell"
    result = run_cmd(cmd)
    # Parse shell output (X=123 Y=456 SCREEN=0 WINDOW=789)
    data = {}
    for line in result.split():
        if '=' in line:
            k, v = line.split('=')
            data[k.lower()] = v
    return json.dumps(data)

@mcp.tool()
def desktop_notify(message: str, title: str = "ROME", urgency: str = "normal", expire_ms: int = 5000) -> str:
    """Sends a desktop notification using notify-send."""
    cmd = f"notify-send -u {shlex.quote(urgency)} -t {expire_ms} {shlex.quote(title)} {shlex.quote(message)}"
    result = run_cmd(cmd)
    return json.dumps({"status": "notified", "title": title, "message": message})
