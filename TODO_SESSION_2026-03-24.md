# Session 2026-03-24 — Issues to Fix

## Critical

### 1. SAFE_SHELL await race condition
- `handle_await` Phase 1 checks registry, Phase 2 subscribes to EventBus
- If task completes BETWEEN Phase 1 and Phase 2 subscribe — missed
- **Fix:** Re-check registry AFTER subscribing, before entering event loop
- **File:** `dictator/ws_server.py` → `handle_await()` ~line 615

### 2. `rome_await` MCP tool is unreliable by design
- MCP is request-response, can't hold persistent WS listener
- `ws_send("status", ...)` polling works fine — use that instead
- **Consider:** Deprecate `rome_await` MCP tool, replace with `ws_send` dispatch+poll pattern
- **File:** `dictator/tools_ws.py` → `rome_await()`

## Hardcoded Values

### 3. GEMINI_CLI path in ws_server.py
- Line 19: `GEMINI_CLI = "/home/paul-kane/.nvm/versions/node/v20.20.0/bin/gemini"` — stale
- **Fix:** Remove or read from config.json
- **File:** `dictator/ws_server.py:19`

### 4. base_dir in shell_executor.py
- Line 52: `base_dir = "/home/paul-kane/projects/rome-core/legions"` — hardcoded
- **Fix:** Derive from `Path(__file__).parent`
- **File:** `legions/shell_executor.py:52`

### 5. ROOT_DIR still points to FTK
- `config.json` → `root_dir: "/var/www/ftk_lms"` — single project hardcoded
- `fs_read` and `fs_write` tools still use ROOT_DIR (FTK-scoped)
- **Fix:** Either make per-project or remove ROOT_DIR dependency from tools
- **Files:** `dictator/core.py`, `dictator/tools_fs.py`, `dictator/config.json`

### 6. Remaining env vars
- `ROME_DAEMON` env checks still scattered (Gemini partially fixed — verify)
- **Files:** `dictator/ws_server.py`, `dictator/emit_helpers.py`

## Removed This Session

- [x] `shell_exec` MCP tool — removed from `tools_fs.py`
- [x] `shell_exec` refs — removed from `prefect_domains.json`, `SOURCE_README.md`, `legion_patches.json`
- [x] `ROME_ROOT` env var — replaced with `Path(__file__)` in `core.py`
- [x] `ROME_DAEMON` env var — replaced with `IS_DAEMON` bool in `core.py`/`daemon.py`

## Updated This Session

- [x] `core_arsenal.json` — gemini path → local build, model → `gemini-3.1-pro-preview`
- [x] `tools_fs.py` — gemini path → local build, model → `gemini-3.1-pro`
- [x] `core_arsenal.json` — `--include-directories` scoped to `rome-core` only
- [x] `events.py` — added `TaskRegistry.remove()` for duplicate task ID fix
- [x] `ws_server.py` — reset stale registry on re-dispatch
- [x] `tools_legion.py` — clear stale task dir on re-dispatch
- [x] `ops/rome-dictator.service` — fixed ExecStart to use `-m dictator.daemon --port 8741`

## Created This Session

- [x] `ops/com.rome.dictator.plist` — macOS launchd
- [x] `ops/rome-dictator-freebsd-rc` — FreeBSD rc.d
- [x] `SETUP.md` — cross-platform install guide
- [x] `HARDCODED_AUDIT.md` — full audit (101KB, needs summary)
