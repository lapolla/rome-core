"""Media tools: music_play, music_stop, music_status, http_fetch, fetch_mo2_mod."""

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

        r = await run_cmd(
            f"yt-dlp --no-download --print webpage_url {shlex.quote(ytdl_query)}", cwd="/tmp"
        )
        if not r.get("ok"):
            return json.dumps({"ok": False, "message": r.get("stderr", "yt-dlp failed")})

        url = r["stdout"].strip()
        proc = subprocess.Popen(
            ["mpv", url, "--no-video", "--volume=100"],
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return json.dumps({"ok": True, "url": url, "pid": proc.pid})
    except Exception as e:
        return json.dumps({"ok": False, "message": str(e)})


@mcp.tool()
async def music_stop() -> str:
    """Stop all running mpv instances."""
    r = await run_cmd("pkill mpv", cwd="/tmp")
    return json.dumps(r)


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
