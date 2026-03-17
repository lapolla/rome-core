"""Media tools: http_fetch, fetch_mo2_mod, music playback."""

import asyncio
import json
import shlex
import time
from pathlib import Path

from dictator.core import run_cmd, MO2_DOWNLOADS

MPV_SOCK = "/tmp/mpv_music"


def register(mcp):
    """Register Media tools with the given FastMCP instance."""

    @mcp.tool()
    async def http_fetch(url: str, dest_path: str, extract: bool = False) -> str:
        """Download a file from URL to dest_path. Optionally extract archive."""
        abs_path = Path(dest_path).resolve()
        abs_path.parent.mkdir(parents=True, exist_ok=True)

        dl_cmd = f"wget -O {shlex.quote(str(abs_path))} {shlex.quote(url)}"
        dl = await run_cmd(dl_cmd, cwd=str(abs_path.parent))

        extract_info = None
        if extract and dl.get("ok"):
            ext_cmd = None
            s = str(abs_path).lower()
            if s.endswith(".zip"):
                ext_cmd = f"unzip -o {shlex.quote(str(abs_path))}"
            elif s.endswith((".7z", ".7zip")):
                ext_cmd = f"7z x -y {shlex.quote(str(abs_path))}"
            elif s.endswith((".tar", ".tar.gz", ".tgz")):
                ext_cmd = f"tar xf {shlex.quote(str(abs_path))}"
            if ext_cmd:
                extract_info = await run_cmd(ext_cmd, cwd=str(abs_path.parent), max_output=50 * 1024 * 1024)
                extract_info["command"] = ext_cmd

        return json.dumps(
            {"ok": dl.get("ok", False), "url": url, "dest": str(abs_path), "download": dl, "extract": extract_info},
            indent=2,
        )

    @mcp.tool()
    async def fetch_mo2_mod(url: str, filename: str = "") -> str:
        """Download a mod to ~/Games/MO2/downloads."""
        MO2_DOWNLOADS.mkdir(parents=True, exist_ok=True)

        if not filename:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            last = parsed.path.split("/")[-1]
            filename = last if last else f"mod_{int(time.time())}.bin"

        dest = MO2_DOWNLOADS / filename
        dl_cmd = f"wget -O {shlex.quote(str(dest))} {shlex.quote(url)}"
        dl = await run_cmd(dl_cmd, cwd=str(MO2_DOWNLOADS))
        return json.dumps({"ok": dl.get("ok", False), "url": url, "dest": str(dest), "download": dl}, indent=2)

    @mcp.tool()
    async def music_play(query: str) -> str:
        """Play music via mpv+ytdl. Stops any current track first. Query is artist + song name."""
        await run_cmd("pkill -f 'mpv --no-video' || true", cwd="/tmp")
        await asyncio.sleep(0.5)
        sock = MPV_SOCK
        cmd = f'nohup mpv --no-video --input-ipc-server={shlex.quote(sock)} "ytdl://ytsearch1:{shlex.quote(query)}" > /dev/null 2>&1 &'
        await run_cmd(f"bash -c {shlex.quote(cmd)}", cwd="/tmp")
        return json.dumps({"ok": True, "playing": query, "socket": sock})

    @mcp.tool()
    async def music_stop() -> str:
        """Stop currently playing music."""
        await run_cmd("pkill -f 'mpv --no-video' || true", cwd="/tmp")
        await run_cmd(f"rm -f {shlex.quote(MPV_SOCK)} {shlex.quote(MPV_SOCK + '_new')}", cwd="/tmp")
        return json.dumps({"ok": True, "stopped": True})

    @mcp.tool()
    async def music_crossfade(query: str, fade_secs: float = 3.0) -> str:
        """Crossfade from current track to a new one. Falls back to play if nothing is playing."""
        old_sock = MPV_SOCK
        new_sock = f"{MPV_SOCK}_new"

        # Check if old mpv is actually alive (socket can linger after crash)
        old_alive = False
        if Path(old_sock).exists():
            check = await run_cmd(f"bash -c 'echo \'{{\"command\":[\"get_property\",\"playback-time\"]}}\' | socat - {shlex.quote(old_sock)} 2>/dev/null'", cwd="/tmp")
            old_alive = check.get("ok", False) and "error" not in check.get("stdout", "error")

        if not old_alive:
            return await music_play(query)

        # Write crossfade script to temp file — avoids quoting hell
        steps = 20
        interval = fade_secs / steps
        fade_cmds = "\n".join(
            f'echo \'{{"command":["set_property","volume",{i * 100 // steps}]}}\' | socat - {new_sock} 2>/dev/null'
            f'\necho \'{{"command":["set_property","volume",{(steps - i) * 100 // steps}]}}\' | socat - {old_sock} 2>/dev/null'
            f'\nsleep {interval:.3f}'
            for i in range(1, steps + 1)
        )
        script_path = "/tmp/rome_crossfade.sh"
        script_content = f"""#!/bin/bash
# Capture old mpv PID before launching new one
OLD_PID=$(pgrep -f "input-ipc-server={old_sock}" | grep -v "input-ipc-server={new_sock}" | head -1)
mpv --no-video --volume=0 --input-ipc-server={new_sock} "ytdl://ytsearch1:{query}" > /dev/null 2>&1 &
NEW_PID=$!
# Wait for actual audio playback (playback-time > 0), max 20s
READY=0
for i in $(seq 1 40); do
  sleep 0.5
  if ! kill -0 $NEW_PID 2>/dev/null; then break; fi
  if [ -S {new_sock} ]; then
    PT=$(echo '{{"command":["get_property","playback-time"]}}' | socat - {new_sock} 2>/dev/null)
    if echo "$PT" | grep -q '"data":[0-9]'; then READY=1; break; fi
  fi
done
if [ "$READY" -ne 1 ]; then
  kill $NEW_PID 2>/dev/null; rm -f {new_sock} {script_path}; exit 1
fi
# Fade
{fade_cmds}
# Only kill old if new is still alive
if kill -0 $NEW_PID 2>/dev/null && [ -n "$OLD_PID" ]; then
  kill $OLD_PID 2>/dev/null || true
  sleep 0.3
  mv {new_sock} {old_sock} 2>/dev/null || true
fi
rm -f {script_path}
"""
        Path(script_path).write_text(script_content)
        import os
        os.system(f"nohup bash {script_path} > /dev/null 2>&1 &")

        return json.dumps({"ok": True, "crossfaded_to": query, "fade_secs": fade_secs})
