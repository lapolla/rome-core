"""Media tools: music_play, music_stop, music_status, http_fetch, fetch_mo2_mod."""

import asyncio
import json
import shlex
import subprocess
from pathlib import Path

from dictator.core import mcp, run_cmd, MO2_DOWNLOADS


@mcp.tool()
async def music_play(query: str, fade_ms: int = 500) -> str:
    """Play music via yt-dlp + mpv. Accepts a URL or search query."""
    try:
        is_url = query.startswith("http")
        ytdl_query = query if is_url else f"ytsearch:{query}"
        r = await run_cmd(f"yt-dlp --no-download --print webpage_url {shlex.quote(ytdl_query)}", cwd="/tmp")
        if not r.get("ok"):
            return json.dumps({"ok": False, "message": r.get("stderr", "yt-dlp failed")})
        url = r["stdout"].strip()
        sock = f"/tmp/mpv_{id(object()):x}.sock"
        proc = subprocess.Popen(
            ["mpv", url, "--no-video", "--volume=100", f"--input-ipc-server={sock}"],
            start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return json.dumps({"ok": True, "url": url, "pid": proc.pid, "sock": sock})
    except Exception as e:
        return json.dumps({"ok": False, "message": str(e)})


def _socat_vol(sock, vol):
    """Helper: build socat volume command."""
    return f'echo \'{{"command": ["set_property", "volume", {vol}]}}\' | socat - {sock} 2>/dev/null'


@mcp.tool()
async def music_stop(fade_ms: int = 0) -> str:
    """Stop all running mpv instances."""
    if fade_ms > 0:
        socks_raw = (await run_cmd("ls /tmp/mpv_*.sock 2>/dev/null", cwd="/tmp")).get("stdout", "").strip()
        socks = socks_raw.split() if socks_raw else []
        if socks:
            steps = 20
            step_s = fade_ms / steps / 1000
            for i in range(steps, -1, -1):
                vol = int((i / steps) * 100)
                for sock in socks:
                    await run_cmd(_socat_vol(sock, vol), cwd="/tmp")
                await asyncio.sleep(step_s)
    r = await run_cmd("pkill mpv", cwd="/tmp")
    await run_cmd("rm -f /tmp/mpv_*.sock", cwd="/tmp")
    return json.dumps(r)


@mcp.tool()
async def music_crossfade(query: str, fade_ms: int = 2000) -> str:
    """Crossfade from current track to a new one."""
    old_socks_raw = (await run_cmd("ls /tmp/mpv_*.sock 2>/dev/null", cwd="/tmp")).get("stdout", "").strip()
    old_socks = old_socks_raw.split() if old_socks_raw else []
    old_pids = (await run_cmd("pgrep mpv", cwd="/tmp")).get("stdout", "").split()
    # Start new track
    result = await music_play(query, fade_ms=0)
    res = json.loads(result)
    new_sock = res.get("sock", "")
    # Wait for mpv to create socket then set volume 0
    if new_sock:
        await asyncio.sleep(1.5)
        await run_cmd(_socat_vol(new_sock, 0), cwd="/tmp")
    # Crossfade: old down, new up in parallel
    steps = 20
    step_s = fade_ms / steps / 1000
    for i in range(steps, -1, -1):
        vol_old = int((i / steps) * 100)
        vol_new = 100 - vol_old
        for sock in old_socks:
            await run_cmd(_socat_vol(sock, vol_old), cwd="/tmp")
        if new_sock:
            await run_cmd(_socat_vol(new_sock, vol_new), cwd="/tmp")
        await asyncio.sleep(step_s)
    # Kill old processes and clean sockets
    for pid in old_pids:
        await run_cmd(f"kill {pid} 2>/dev/null", cwd="/tmp")
    for sock in old_socks:
        await run_cmd(f"rm -f {sock} 2>/dev/null", cwd="/tmp")
    return result


@mcp.tool()
async def music_status() -> str:
    """Check if mpv is currently playing."""
    r = await run_cmd("pgrep -l mpv", cwd="/tmp")
    is_playing = r.get("ok", False) and "mpv" in r.get("stdout", "")
    return json.dumps({"ok": True, "playing": is_playing, "output": r.get("stdout", "").strip()})


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
        filename = last if last else f"mod_{int(__import__('time').time())}.bin"

    dest = MO2_DOWNLOADS / filename
    dl_cmd = f"wget -O {shlex.quote(str(dest))} {shlex.quote(url)}"
    dl = await run_cmd(dl_cmd, cwd=str(MO2_DOWNLOADS))
    return json.dumps({"ok": dl.get("ok", False), "url": url, "dest": str(dest), "download": dl}, indent=2)
