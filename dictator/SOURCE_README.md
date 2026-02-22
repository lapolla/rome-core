# MCP Server ("asshole")

A [Model Context Protocol](https://modelcontextprotocol.io/) server providing Claude Code with shell execution, file I/O, git operations, Drupal tooling, desktop GUI automation, and mod management capabilities.

## Quick Start

```bash
cd ~/projects/mcp-server
npm install
node server.mjs
```

Communicates over **stdio** (stdin/stdout JSON-RPC). Intended to be launched by Claude Code via `.mcp.json` or `~/.claude/mcp-servers.json`.

### Configuration

**Global** (`~/.claude/mcp-servers.json`):
```json
{
  "mcpServers": {
    "asshole": {
      "command": "node",
      "args": ["/home/paul-kane/projects/mcp-server/server.mjs"]
    }
  }
}
```

**Per-project** (`.mcp.json` in project root):
```json
{
  "mcpServers": {
    "asshole": {
      "command": "node",
      "args": ["/home/paul-kane/projects/mcp-server/server.mjs"]
    }
  }
}
```

## Tools

### Shell & File System

| Tool | Description |
|------|-------------|
| `shell_exec` | Run a shell command (cwd: `/var/www/ftk_lms`) |
| `fs_read` | Read a file relative to `/var/www/ftk_lms` |
| `fs_write` | Write a file relative to `/var/www/ftk_lms` |
| `read_anywhere` | Read any file on the system (absolute path) |
| `write_anywhere` | Write any file on the system (absolute path) |

> **Note:** `fs_read`/`fs_write` are rooted at `/var/www/ftk_lms` (the Drupal project). For files outside that tree (e.g. game files), use `read_anywhere`/`write_anywhere`.

### Git (rooted at `~/projects/Drupal11`)

| Tool | Description |
|------|-------------|
| `git_status` | Show working tree status |
| `git_diff` | Show diff (optionally for a specific path) |
| `git_commit` | Stage files and commit with a message |
| `git_push` | Push to remote (default branch: `master`) |

### Drupal

| Tool | Description |
|------|-------------|
| `rsync_ftk_modules` | Rsync custom modules (and optionally themes) from dev to live |
| `drush_run` | Run a Drush command against the Drupal site |
| `drupal_fj_run` | Run Drupal FunctionalJavascript tests (Selenium/geckodriver) |

### Mod Management

| Tool | Description |
|------|-------------|
| `http_fetch` | Download a URL to a local path (optionally extract archives) |
| `fetch_mo2_mod` | Download a mod to MO2's downloads directory |

### Desktop GUI Automation

X11 automation tools using `xdotool` and `scrot`. Used to drive Wine/Proton applications (MO2, DynDOLOD, TexGen, etc.) from Claude Code.

| Tool | Parameters | Description |
|------|-----------|-------------|
| `desktop_screenshot` | `window_id?`, `delay?` | Capture screen or a specific window. Returns base64 PNG image. |
| `desktop_click` | `x`, `y`, `button?`, `clicks?`, `window_id?` | Click at screen coordinates (optionally focus a window first — atomic focus+click) |
| `desktop_type_text` | `text`, `delay_ms?` | Type text via xdotool |
| `desktop_press_key` | `key` | Press a key combo (e.g. `"Return"`, `"alt+F4"`) |
| `desktop_find_window` | `name?`, `class_name?` | Find windows by title or class |
| `desktop_focus_window` | `window_id` | Activate and focus a window |
| `desktop_wait_for_window` | `name`, `timeout_sec?` | Wait for a window with a given title to appear |
| `desktop_get_mouse_location` | — | Get current mouse X, Y coordinates |
| `desktop_notify` | `message?`, `title?`, `urgency?`, `expire_ms?`, `steps?` | Show a desktop notification with optional multi-step workflow |

#### `desktop_notify` — Multi-step Workflow

The notify tool can run a sequence of steps, each with a notification update and an optional shell command. Uses `gdbus` to replace the same notification (no stacking).

```json
{
  "title": "Claude is driving",
  "urgency": "critical",
  "expire_ms": 8000,
  "steps": [
    { "text": "Focusing window...", "cmd": "xdotool windowactivate --sync 12345", "delay_ms": 1000 },
    { "text": "Clicking button...", "cmd": "xdotool mousemove 500 300 && xdotool click 1", "delay_ms": 500 },
    { "text": "Done!" }
  ]
}
```

## System Requirements

- **Node.js** >= 18
- **xdotool** — X11 window/mouse/keyboard automation
- **scrot** — screenshot utility
- **wmctrl** — window manager control (for resize/state changes)
- **gdbus** — D-Bus CLI (for notification replacement; part of glib)
- **wget** — for `http_fetch` / `fetch_mo2_mod`
- **rsync** — for `rsync_ftk_modules`
- **drush** — for `drush_run` (Drupal CLI)
- **geckodriver** / **chromedriver** — for `drupal_fj_run`

## Architecture

Single-file server (`server.mjs`) using `@modelcontextprotocol/sdk`. All tools return JSON responses wrapped in MCP content blocks. Desktop tools return `image` content type for screenshots.

```
server.mjs
├── Drupal tools (rsync, drush, fj tests)
├── Shell & FS tools (rooted at /var/www/ftk_lms)
├── Unrestricted FS tools (read_anywhere, write_anywhere)
├── Git tools (rooted at ~/projects/Drupal11)
├── Mod management tools (http_fetch, fetch_mo2_mod)
└── Desktop automation tools (xdotool, scrot, gdbus)
```
