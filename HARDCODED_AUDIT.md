# Hardcoded Values Audit Report

## `meta_test-gemini-debug.json`

- **Line 1** (Hardcoded Home Directory):
  ```
  {"rome_v": "1.1-compat", "task_id": "test-gemini-debug", "result": {"status": "FAILED", "exit_code": 1, "path": "/home/paul-kane/projects/rome-core/report_test-gemini-debug.txt"}}
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 1** (Hardcoded Username (paul-kane)):
  ```
  {"rome_v": "1.1-compat", "task_id": "test-gemini-debug", "result": {"status": "FAILED", "exit_code": 1, "path": "/home/paul-kane/projects/rome-core/report_test-gemini-debug.txt"}}
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `meta_test_list_dir.json`

- **Line 1** (Hardcoded Home Directory):
  ```
  {"rome_v": "1.1", "task_id": "test_list_dir", "result": {"status": "FAILED", "exit_code": 1, "path": "/home/paul-kane/projects/rome-core/report_test_list_dir.txt"}}
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 1** (Hardcoded Username (paul-kane)):
  ```
  {"rome_v": "1.1", "task_id": "test_list_dir", "result": {"status": "FAILED", "exit_code": 1, "path": "/home/paul-kane/projects/rome-core/report_test_list_dir.txt"}}
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `meta_LEGION_GH_PUSH.json`

- **Line 1** (Hardcoded Home Directory):
  ```
  {"rome_v": "1.1", "task_id": "LEGION_GH_PUSH", "result": {"status": "SUCCESS", "exit_code": 0, "path": "/home/paul-kane/projects/rome-core/report_LEGION_GH_PUSH.txt"}}
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 1** (Hardcoded Username (paul-kane)):
  ```
  {"rome_v": "1.1", "task_id": "LEGION_GH_PUSH", "result": {"status": "SUCCESS", "exit_code": 0, "path": "/home/paul-kane/projects/rome-core/report_LEGION_GH_PUSH.txt"}}
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `manifest.json`

- **Line 47** (Hardcoded Home Directory):
  ```
  "path": "/home/paul-kane/projects/rome-core/report_test-gemini-debug.txt",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 47** (Hardcoded Username (paul-kane)):
  ```
  "path": "/home/paul-kane/projects/rome-core/report_test-gemini-debug.txt",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `intelligence/dovahkiin_ops.py`

- **Line 11** (Hardcoded Username (paul-kane)):
  ```
  STATE_FILE = Path("/media/paul-kane/SteamGames/steamapps/compatdata/489830/pfx/drive_c/tmp/skyrim_state.json")
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 12** (Hardcoded Home Directory):
  ```
  AUDIO_TOOL = Path("/home/paul-kane/projects/rome-core/intelligence/audio_monitor.py")
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 12** (Hardcoded Username (paul-kane)):
  ```
  AUDIO_TOOL = Path("/home/paul-kane/projects/rome-core/intelligence/audio_monitor.py")
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `dictator/core.py`

- **Line 29** (Hardcoded /var/www path):
  ```
  ROOT_DIR = _p("root_dir", "/var/www/ftk_lms")
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 34** (Hardcoded Username (paul-kane)):
  ```
  "/media/paul-kane/SteamGames/steamapps/compatdata/489830/pfx/drive_c/tmp/skyrim_state.json")
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 39** (Hardcoded /var/www path):
  ```
  DRUPAL_MODULES_DEST = _p("drupal_modules_dest", "/var/www/ftk_lms/web/modules/custom/")
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 41** (Hardcoded /var/www path):
  ```
  DRUPAL_THEMES_DEST = _p("drupal_themes_dest", "/var/www/ftk_lms/web/themes/custom/")
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 44** (Hardcoded Username (paul-kane)):
  ```
  PAPYRUS_COMPILER = _p("papyrus_compiler", "/media/paul-kane/SteamGames/Games/mods/compile_papyrus.sh")
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `dictator/tools_fs.py`

- **Line 17** (Hardcoded Home Directory):
  ```
  GEMINI_CLI = "/home/paul-kane/projects/gemini-cli/bundle/gemini.js"
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 17** (Hardcoded Username (paul-kane)):
  ```
  GEMINI_CLI = "/home/paul-kane/projects/gemini-cli/bundle/gemini.js"
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 50** (Hardcoded /var/www path):
  ```
  """Execute a shell command (cwd = /var/www/ftk_lms)."""
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 89** (Hardcoded /var/www path):
  ```
  """Read a file relative to /var/www/ftk_lms (1-indexed, inclusive)."""
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 109** (Hardcoded /var/www path):
  ```
  """Write content to a file relative to /var/www/ftk_lms."""
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `dictator/config.json`

- **Line 2** (Hardcoded /var/www path):
  ```
  "root_dir": "/var/www/ftk_lms",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 5** (Hardcoded Username (paul-kane)):
  ```
  "skyrim_state_file": "/media/paul-kane/SteamGames/steamapps/compatdata/489830/pfx/drive_c/tmp/skyrim_state.json",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 8** (Hardcoded /var/www path):
  ```
  "drupal_modules_dest": "/var/www/ftk_lms/web/modules/custom/",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 10** (Hardcoded /var/www path):
  ```
  "drupal_themes_dest": "/var/www/ftk_lms/web/themes/custom/",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 11** (Hardcoded Username (paul-kane)):
  ```
  "skyrim_game_dir": "/media/paul-kane/SteamGames/Games/SkyrimSE/",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 12** (Hardcoded Username (paul-kane)):
  ```
  "mo2_mods_dir": "/media/paul-kane/SteamGames/Games/mods/",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 13** (Hardcoded Username (paul-kane)):
  ```
  "papyrus_compiler": "/media/paul-kane/SteamGames/Games/mods/compile_papyrus.sh",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 14** (Hardcoded Username (paul-kane)):
  ```
  "skyrim_crash_logs": "/media/paul-kane/SteamGames/steamapps/compatdata/489830/pfx/drive_c/users/steamuser/Documents/My Games/Skyrim Special Edition/SKSE/",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 19** (Local IP (127.0.0.1/0.0.0.0)):
  ```
  "daemon_host": "127.0.0.1",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `dictator/tools_drupal.py`

- **Line 20** (Hardcoded /var/www path):
  ```
  """Rsync custom Drupal modules (and optionally themes) from dev to /var/www."""
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 51** (Local IP (127.0.0.1/0.0.0.0)):
  ```
  webdriver_url: str = "http://127.0.0.1:4444",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 53** (Local IP (127.0.0.1/0.0.0.0)):
  ```
  driver_host: str = "127.0.0.1",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `dictator/tools_stats.py`

- **Line 149** (Local IP (127.0.0.1/0.0.0.0)):
  ```
  resp = await client.get("http://127.0.0.1:8741/health")
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `dictator/ws_client.py`

- **Line 24** (Local IP (127.0.0.1/0.0.0.0)):
  ```
  _WS_URL = "ws://127.0.0.1:8741/ws"
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `dictator/rome_log.py`

- **Line 11** (Hardcoded Home Directory):
  ```
  ROME_ROOT = Path(os.environ.get("ROME_ROOT", "/home/paul-kane/projects/rome-core"))
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 11** (Hardcoded Username (paul-kane)):
  ```
  ROME_ROOT = Path(os.environ.get("ROME_ROOT", "/home/paul-kane/projects/rome-core"))
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `dictator/mcp_client_tool.py`

- **Line 23** (Hardcoded Home Directory):
  ```
  args=["/home/paul-kane/projects/rome-core/dictator/cli.py"],
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 23** (Hardcoded Username (paul-kane)):
  ```
  args=["/home/paul-kane/projects/rome-core/dictator/cli.py"],
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `dictator/daemon.py`

- **Line 96** (Local IP (127.0.0.1/0.0.0.0)):
  ```
  parser.add_argument("--host", default=str(cfg.get("daemon_host", "127.0.0.1")))
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `dictator/legion_patches.json`

- **Line 9** (Hardcoded Home Directory):
  ```
  "UNIVERSAL RULE: Every slave must use ~/tmp (which is /home/paul-kane/tmp) as the staging directory for any file writes. If the target path is restricted (e.g. ~/.claude/, /media/), write to ~/tmp first then report the path for the orchestrator to move it."
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 9** (Hardcoded Username (paul-kane)):
  ```
  "UNIVERSAL RULE: Every slave must use ~/tmp (which is /home/paul-kane/tmp) as the staging directory for any file writes. If the target path is restricted (e.g. ~/.claude/, /media/), write to ~/tmp first then report the path for the orchestrator to move it."
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 14** (Hardcoded Home Directory):
  ```
  "UNIVERSAL RULE: Every slave must use ~/tmp (which is /home/paul-kane/tmp) as the staging directory for any file writes. If the target path is restricted (e.g. ~/.claude/, /media/), write to ~/tmp first then report the path for the orchestrator to move it."
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 14** (Hardcoded Username (paul-kane)):
  ```
  "UNIVERSAL RULE: Every slave must use ~/tmp (which is /home/paul-kane/tmp) as the staging directory for any file writes. If the target path is restricted (e.g. ~/.claude/, /media/), write to ~/tmp first then report the path for the orchestrator to move it."
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 18** (Hardcoded Home Directory):
  ```
  "UNIVERSAL RULE: Every slave must use ~/tmp (which is /home/paul-kane/tmp) as the staging directory for any file writes. If the target path is restricted (e.g. ~/.claude/, /media/), write to ~/tmp first then report the path for the orchestrator to move it."
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 18** (Hardcoded Username (paul-kane)):
  ```
  "UNIVERSAL RULE: Every slave must use ~/tmp (which is /home/paul-kane/tmp) as the staging directory for any file writes. If the target path is restricted (e.g. ~/.claude/, /media/), write to ~/tmp first then report the path for the orchestrator to move it."
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 22** (Hardcoded Home Directory):
  ```
  "UNIVERSAL RULE: Every slave must use ~/tmp (which is /home/paul-kane/tmp) as the staging directory for any file writes. If the target path is restricted (e.g. ~/.claude/, /media/), write to ~/tmp first then report the path for the orchestrator to move it."
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 22** (Hardcoded Username (paul-kane)):
  ```
  "UNIVERSAL RULE: Every slave must use ~/tmp (which is /home/paul-kane/tmp) as the staging directory for any file writes. If the target path is restricted (e.g. ~/.claude/, /media/), write to ~/tmp first then report the path for the orchestrator to move it."
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `dictator/ws_server.py`

- **Line 19** (Hardcoded Home Directory):
  ```
  GEMINI_CLI = "/home/paul-kane/.nvm/versions/node/v20.20.0/bin/gemini"
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 19** (Hardcoded NVM path):
  ```
  GEMINI_CLI = "/home/paul-kane/.nvm/versions/node/v20.20.0/bin/gemini"
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 19** (Hardcoded Username (paul-kane)):
  ```
  GEMINI_CLI = "/home/paul-kane/.nvm/versions/node/v20.20.0/bin/gemini"
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `legions/centurion.py`

- **Line 14** (Hardcoded Home Directory):
  ```
  ROME_ROOT = os.environ.get("ROME_ROOT", "/home/paul-kane/projects/rome-core")
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 14** (Hardcoded Username (paul-kane)):
  ```
  ROME_ROOT = os.environ.get("ROME_ROOT", "/home/paul-kane/projects/rome-core")
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `legions/centurion_wrapper.py`

- **Line 11** (Hardcoded Home Directory):
  ```
  ROME_ROOT = os.environ.get("ROME_ROOT", "/home/paul-kane/projects/rome-core")
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 11** (Hardcoded Username (paul-kane)):
  ```
  ROME_ROOT = os.environ.get("ROME_ROOT", "/home/paul-kane/projects/rome-core")
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `legions/centurion_imperial-census-v2_ep699s2d.json`

- **Line 1** (Hardcoded Home Directory):
  ```
  {"campaign_id": "imperial-census-v2", "tasks": [{"id": "sys-kernel", "capability": "SAFE_SHELL", "args": ["uname -r && cat /proc/version | head -1"]}, {"id": "sys-memory", "capability": "SAFE_SHELL", "args": ["free -h | head -2"]}, {"id": "sys-disks", "capability": "SAFE_SHELL", "args": ["df -h / /home /media/paul-kane/SteamGames 2>/dev/null | head -5"]}, {"id": "sys-gpu", "capability": "SAFE_SHELL", "args": ["lspci | grep -i vga"]}, {"id": "rome-lines", "capability": "SAFE_SHELL", "args": ["find /home/paul-kane/projects/rome-core/dictator -name '*.py' | xargs wc -l | tail -1"]}, {"id": "rome-tools", "capability": "SAFE_SHELL", "args": ["grep -c '@mcp.tool' /home/paul-kane/projects/rome-core/dictator/tools_*.py | paste -sd+ | bc"]}, {"id": "rome-legions", "capability": "SAFE_SHELL", "args": ["ls -d /home/paul-kane/projects/rome-core/legions/*/ 2>/dev/null | wc -l"]}, {"id": "skyrim-mods", "capability": "SAFE_SHELL", "args": ["ls /media/paul-kane/SteamGames/Games/mods/ 2>/dev/null | wc -l"]}, {"id": "git-repos", "capability": "SAFE_SHELL", "args": ["find /home/paul-kane/projects -maxdepth 2 -name '.git' -type d 2>/dev/null | wc -l"]}, {"id": "legion-history", "capability": "SAFE_SHELL", "args": ["wc -l /home/paul-kane/projects/rome-core/logs/rome.jsonl 2>/dev/null"]}]}
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 1** (Hardcoded Username (paul-kane)):
  ```
  {"campaign_id": "imperial-census-v2", "tasks": [{"id": "sys-kernel", "capability": "SAFE_SHELL", "args": ["uname -r && cat /proc/version | head -1"]}, {"id": "sys-memory", "capability": "SAFE_SHELL", "args": ["free -h | head -2"]}, {"id": "sys-disks", "capability": "SAFE_SHELL", "args": ["df -h / /home /media/paul-kane/SteamGames 2>/dev/null | head -5"]}, {"id": "sys-gpu", "capability": "SAFE_SHELL", "args": ["lspci | grep -i vga"]}, {"id": "rome-lines", "capability": "SAFE_SHELL", "args": ["find /home/paul-kane/projects/rome-core/dictator -name '*.py' | xargs wc -l | tail -1"]}, {"id": "rome-tools", "capability": "SAFE_SHELL", "args": ["grep -c '@mcp.tool' /home/paul-kane/projects/rome-core/dictator/tools_*.py | paste -sd+ | bc"]}, {"id": "rome-legions", "capability": "SAFE_SHELL", "args": ["ls -d /home/paul-kane/projects/rome-core/legions/*/ 2>/dev/null | wc -l"]}, {"id": "skyrim-mods", "capability": "SAFE_SHELL", "args": ["ls /media/paul-kane/SteamGames/Games/mods/ 2>/dev/null | wc -l"]}, {"id": "git-repos", "capability": "SAFE_SHELL", "args": ["find /home/paul-kane/projects -maxdepth 2 -name '.git' -type d 2>/dev/null | wc -l"]}, {"id": "legion-history", "capability": "SAFE_SHELL", "args": ["wc -l /home/paul-kane/projects/rome-core/logs/rome.jsonl 2>/dev/null"]}]}
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `legions/run_pandora.sh`

- **Line 6** (Hardcoded Username (paul-kane)):
  ```
  export STEAM_COMPAT_DATA_PATH="/media/paul-kane/SteamGames/steamapps/compatdata/$APPID"
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 13** (Hardcoded Username (paul-kane)):
  ```
  PANDORA_EXE="/media/paul-kane/SteamGames/Games/mods/Pandora Behaviour Engine Standalone Windows x64/Pandora Behaviour Engine+.exe"
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 14** (Hardcoded Username (paul-kane)):
  ```
  OUTPUT_DIR="/media/paul-kane/SteamGames/Games/mods/Pandora_Output"
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `legions/centurion_rome-audit_s5ullgd2.json`

- **Line 1** (Hardcoded Home Directory):
  ```
  {"campaign_id": "rome-audit", "tasks": [{"id": "audit-legion", "capability": "GEMINI", "args": ["Read /home/paul-kane/projects/rome-core/dictator/tools_legion.py and summarize: what tools are exposed, any obvious bugs or issues. Be brief."]}, {"id": "audit-core", "capability": "GEMINI", "args": ["Read /home/paul-kane/projects/rome-core/dictator/core.py and summarize: architecture, run_cmd_stream design, any issues. Be brief."]}, {"id": "audit-wrapper", "capability": "GEMINI", "args": ["Read /home/paul-kane/projects/rome-core/legions/legion_wrapper.py and summarize: how progress tracking works, ROME signal parsing, any issues. Be brief."]}, {"id": "audit-arsenal", "capability": "GEMINI", "args": ["Read /home/paul-kane/projects/rome-core/arsenal/core_arsenal.json and summarize: all capabilities, their configs. Be brief."]}]}
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 1** (Hardcoded Username (paul-kane)):
  ```
  {"campaign_id": "rome-audit", "tasks": [{"id": "audit-legion", "capability": "GEMINI", "args": ["Read /home/paul-kane/projects/rome-core/dictator/tools_legion.py and summarize: what tools are exposed, any obvious bugs or issues. Be brief."]}, {"id": "audit-core", "capability": "GEMINI", "args": ["Read /home/paul-kane/projects/rome-core/dictator/core.py and summarize: architecture, run_cmd_stream design, any issues. Be brief."]}, {"id": "audit-wrapper", "capability": "GEMINI", "args": ["Read /home/paul-kane/projects/rome-core/legions/legion_wrapper.py and summarize: how progress tracking works, ROME signal parsing, any issues. Be brief."]}, {"id": "audit-arsenal", "capability": "GEMINI", "args": ["Read /home/paul-kane/projects/rome-core/arsenal/core_arsenal.json and summarize: all capabilities, their configs. Be brief."]}]}
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `legions/shell_executor.py`

- **Line 51** (Hardcoded Home Directory):
  ```
  base_dir = "/home/paul-kane/projects/rome-core/legions"
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 51** (Hardcoded Username (paul-kane)):
  ```
  base_dir = "/home/paul-kane/projects/rome-core/legions"
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `legions/audit-portability/meta_audit-portability.json`

- **Line 1** (Hardcoded Home Directory):
  ```
  {"rome_v": "1.1-compat", "task_id": "audit-portability", "result": {"status": "FAILED", "exit_code": 1, "path": "/home/paul-kane/projects/rome-core/legions/audit-portability/report_audit-portability.txt"}}
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 1** (Hardcoded Username (paul-kane)):
  ```
  {"rome_v": "1.1-compat", "task_id": "audit-portability", "result": {"status": "FAILED", "exit_code": 1, "path": "/home/paul-kane/projects/rome-core/legions/audit-portability/report_audit-portability.txt"}}
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `legions/audit-portability/manifest.json`

- **Line 17** (Hardcoded Home Directory):
  ```
  "path": "/home/paul-kane/projects/rome-core/legions/audit-portability/report_audit-portability.txt",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 17** (Hardcoded Username (paul-kane)):
  ```
  "path": "/home/paul-kane/projects/rome-core/legions/audit-portability/report_audit-portability.txt",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `legions/dup-test/meta_dup-test.json`

- **Line 1** (Hardcoded Home Directory):
  ```
  {"rome_v": "1.1-compat", "task_id": "dup-test", "result": {"status": "SUCCESS", "exit_code": 0, "path": "/home/paul-kane/projects/rome-core/legions/dup-test/report_dup-test.txt"}}
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 1** (Hardcoded Username (paul-kane)):
  ```
  {"rome_v": "1.1-compat", "task_id": "dup-test", "result": {"status": "SUCCESS", "exit_code": 0, "path": "/home/paul-kane/projects/rome-core/legions/dup-test/report_dup-test.txt"}}
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `legions/dup-test/manifest.json`

- **Line 23** (Hardcoded Home Directory):
  ```
  "path": "/home/paul-kane/projects/rome-core/legions/dup-test/report_dup-test.txt",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 23** (Hardcoded Username (paul-kane)):
  ```
  "path": "/home/paul-kane/projects/rome-core/legions/dup-test/report_dup-test.txt",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `legions/portability-update_write-launchd/meta_portability-update_write-launchd.json`

- **Line 1** (Hardcoded Home Directory):
  ```
  {"rome_v": "1.1-compat", "task_id": "portability-update_write-launchd", "result": {"status": "FAILED", "exit_code": 1, "path": "/home/paul-kane/projects/rome-core/legions/portability-update_write-launchd/report_portability-update_write-launchd.txt"}}
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 1** (Hardcoded Username (paul-kane)):
  ```
  {"rome_v": "1.1-compat", "task_id": "portability-update_write-launchd", "result": {"status": "FAILED", "exit_code": 1, "path": "/home/paul-kane/projects/rome-core/legions/portability-update_write-launchd/report_portability-update_write-launchd.txt"}}
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `legions/portability-update_write-launchd/manifest.json`

- **Line 16** (Hardcoded Home Directory):
  ```
  "path": "/home/paul-kane/projects/rome-core/legions/portability-update_write-launchd/report_portability-update_write-launchd.txt",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 16** (Hardcoded Username (paul-kane)):
  ```
  "path": "/home/paul-kane/projects/rome-core/legions/portability-update_write-launchd/report_portability-update_write-launchd.txt",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `legions/waste_calc_investigation_1/meta_waste_calc_investigation_1.json`

- **Line 1** (Hardcoded Home Directory):
  ```
  {"rome_v": "1.1-compat", "task_id": "waste_calc_investigation_1", "result": {"status": "FAILED", "exit_code": 1, "path": "/home/paul-kane/projects/rome-core/legions/waste_calc_investigation_1/report_waste_calc_investigation_1.txt"}}
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 1** (Hardcoded Username (paul-kane)):
  ```
  {"rome_v": "1.1-compat", "task_id": "waste_calc_investigation_1", "result": {"status": "FAILED", "exit_code": 1, "path": "/home/paul-kane/projects/rome-core/legions/waste_calc_investigation_1/report_waste_calc_investigation_1.txt"}}
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `legions/waste_calc_investigation_1/manifest.json`

- **Line 16** (Hardcoded Home Directory):
  ```
  "path": "/home/paul-kane/projects/rome-core/legions/waste_calc_investigation_1/report_waste_calc_investigation_1.txt",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 16** (Hardcoded Username (paul-kane)):
  ```
  "path": "/home/paul-kane/projects/rome-core/legions/waste_calc_investigation_1/report_waste_calc_investigation_1.txt",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `legions/portability-docs-2_write-launchd/manifest.json`

- **Line 6** (Hardcoded Home Directory):
  ```
  "changed": "/home/paul-kane/projects/rome-core/ops/rome-dictator-freebsd-rc:",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 6** (Hardcoded Username (paul-kane)):
  ```
  "changed": "/home/paul-kane/projects/rome-core/ops/rome-dictator-freebsd-rc:",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 48** (Hardcoded Home Directory):
  ```
  "path": "/home/paul-kane/projects/rome-core/legions/portability-docs-2_write-launchd/report_portability-docs-2_write-launchd.txt",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 48** (Hardcoded Username (paul-kane)):
  ```
  "path": "/home/paul-kane/projects/rome-core/legions/portability-docs-2_write-launchd/report_portability-docs-2_write-launchd.txt",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `legions/portability-docs-2_write-launchd/meta_portability-docs-2_write-launchd.json`

- **Line 1** (Hardcoded Home Directory):
  ```
  {"rome_v": "1.1-compat", "task_id": "portability-docs-2_write-launchd", "result": {"status": "SUCCESS", "exit_code": 0, "path": "/home/paul-kane/projects/rome-core/legions/portability-docs-2_write-launchd/report_portability-docs-2_write-launchd.txt"}}
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 1** (Hardcoded Username (paul-kane)):
  ```
  {"rome_v": "1.1-compat", "task_id": "portability-docs-2_write-launchd", "result": {"status": "SUCCESS", "exit_code": 0, "path": "/home/paul-kane/projects/rome-core/legions/portability-docs-2_write-launchd/report_portability-docs-2_write-launchd.txt"}}
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `legions/archive/madness_fix_orchestrator.py`

- **Line 82** (Hardcoded Home Directory):
  ```
  plugin_src = "/home/paul-kane/projects/sexlab-madness-plugin/src/Plugin.cpp"
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 82** (Hardcoded Username (paul-kane)):
  ```
  plugin_src = "/home/paul-kane/projects/sexlab-madness-plugin/src/Plugin.cpp"
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 83** (Hardcoded Home Directory):
  ```
  bridge_src = "/home/paul-kane/projects/sexlab-madness-plugin/mod/Scripts/Source/slmBridge.psc"
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 83** (Hardcoded Username (paul-kane)):
  ```
  bridge_src = "/home/paul-kane/projects/sexlab-madness-plugin/mod/Scripts/Source/slmBridge.psc"
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `legions/archive/zenith_orchestrator.py`

- **Line 6** (Hardcoded Home Directory):
  ```
  LOG_FILE = "/home/paul-kane/tmp/ROME_ZENITH.log"
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 6** (Hardcoded Username (paul-kane)):
  ```
  LOG_FILE = "/home/paul-kane/tmp/ROME_ZENITH.log"
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 50** (Hardcoded Home Directory):
  ```
  t1 = threading.Thread(target=run_task, args=("KERN_MOD", env + "cd /home/paul-kane/tmp/linux-rome && timeout 300s make -j32 modules", ui))
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 50** (Hardcoded Username (paul-kane)):
  ```
  t1 = threading.Thread(target=run_task, args=("KERN_MOD", env + "cd /home/paul-kane/tmp/linux-rome && timeout 300s make -j32 modules", ui))
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 53** (Hardcoded Home Directory):
  ```
  t2 = threading.Thread(target=run_task, args=("CORE_CPP", "g++ -shared -fPIC -o /home/paul-kane/tmp/ROME_Core.so src/*.cpp -Isrc -std=c++20", ui))
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 53** (Hardcoded Username (paul-kane)):
  ```
  t2 = threading.Thread(target=run_task, args=("CORE_CPP", "g++ -shared -fPIC -o /home/paul-kane/tmp/ROME_Core.so src/*.cpp -Isrc -std=c++20", ui))
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 56** (Hardcoded Home Directory):
  ```
  t3 = threading.Thread(target=run_task, args=("SEC_SCAN", "grep -rE 'password|secret|key|API' /home/paul-kane/projects/Drupal11/modules/custom | head -n 1000", ui))
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 56** (Hardcoded Username (paul-kane)):
  ```
  t3 = threading.Thread(target=run_task, args=("SEC_SCAN", "grep -rE 'password|secret|key|API' /home/paul-kane/projects/Drupal11/modules/custom | head -n 1000", ui))
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `legions/archive/ctd_investigation_v2.py`

- **Line 52** (Hardcoded Home Directory):
  ```
  plugin_src = "/home/paul-kane/projects/sexlab-madness-plugin/src/Plugin.cpp"
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 52** (Hardcoded Username (paul-kane)):
  ```
  plugin_src = "/home/paul-kane/projects/sexlab-madness-plugin/src/Plugin.cpp"
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 53** (Hardcoded Home Directory):
  ```
  bridge_src = "/home/paul-kane/projects/sexlab-madness-plugin/mod/Scripts/Source/slmBridge.psc"
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 53** (Hardcoded Username (paul-kane)):
  ```
  bridge_src = "/home/paul-kane/projects/sexlab-madness-plugin/mod/Scripts/Source/slmBridge.psc"
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `legions/archive/kernel_siege.py`

- **Line 237** (Local IP (127.0.0.1/0.0.0.0)):
  ```
  server = HTTPServer(('0.0.0.0', args.port), Handler)
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 242** (Localhost URL):
  ```
  print(f"Dashboard: http://localhost:{args.port}", flush=True)
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `legions/archive/centurion_64.py`

- **Line 7** (Hardcoded Home Directory):
  ```
  LOG_FILE = "/home/paul-kane/tmp/ROME_64_SATURATION.log"
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 7** (Hardcoded Username (paul-kane)):
  ```
  LOG_FILE = "/home/paul-kane/tmp/ROME_64_SATURATION.log"
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `legions/archive/madness_orchestrator.py`

- **Line 77** (Hardcoded Home Directory):
  ```
  "MAD_CONF":  ("SAFE_SHELL", "export VCPKG_ROOT=/home/paul-kane/projects/vcpkg; cd /home/paul-kane/projects/sexlab-madness-plugin && cmake --preset release", []),
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 77** (Hardcoded Username (paul-kane)):
  ```
  "MAD_CONF":  ("SAFE_SHELL", "export VCPKG_ROOT=/home/paul-kane/projects/vcpkg; cd /home/paul-kane/projects/sexlab-madness-plugin && cmake --preset release", []),
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 78** (Hardcoded Home Directory):
  ```
  "MAD_BUILD": ("SAFE_SHELL", "cd /home/paul-kane/projects/sexlab-madness-plugin && cmake --build --preset release", ["MAD_CONF"])
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 78** (Hardcoded Username (paul-kane)):
  ```
  "MAD_BUILD": ("SAFE_SHELL", "cd /home/paul-kane/projects/sexlab-madness-plugin && cmake --build --preset release", ["MAD_CONF"])
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 114** (Hardcoded Home Directory):
  ```
  dll_path = "/home/paul-kane/projects/sexlab-madness-plugin/build/release/SexLabMadness.dll"
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 114** (Hardcoded Username (paul-kane)):
  ```
  dll_path = "/home/paul-kane/projects/sexlab-madness-plugin/build/release/SexLabMadness.dll"
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `legions/archive/augustus.py`

- **Line 41** (Hardcoded Home Directory):
  ```
  sandbox = f"/home/paul-kane/tmp/augustus_slave_{tid}"
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 41** (Hardcoded Username (paul-kane)):
  ```
  sandbox = f"/home/paul-kane/tmp/augustus_slave_{tid}"
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `legions/direct_ws_waste_task_1/meta_direct_ws_waste_task_1.json`

- **Line 1** (Hardcoded Home Directory):
  ```
  {"rome_v": "1.1-compat", "task_id": "direct_ws_waste_task_1", "result": {"status": "FAILED", "exit_code": 1, "path": "/home/paul-kane/projects/rome-core/legions/direct_ws_waste_task_1/report_direct_ws_waste_task_1.txt"}}
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 1** (Hardcoded Username (paul-kane)):
  ```
  {"rome_v": "1.1-compat", "task_id": "direct_ws_waste_task_1", "result": {"status": "FAILED", "exit_code": 1, "path": "/home/paul-kane/projects/rome-core/legions/direct_ws_waste_task_1/report_direct_ws_waste_task_1.txt"}}
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `legions/direct_ws_waste_task_1/manifest.json`

- **Line 16** (Hardcoded Home Directory):
  ```
  "path": "/home/paul-kane/projects/rome-core/legions/direct_ws_waste_task_1/report_direct_ws_waste_task_1.txt",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 16** (Hardcoded Username (paul-kane)):
  ```
  "path": "/home/paul-kane/projects/rome-core/legions/direct_ws_waste_task_1/report_direct_ws_waste_task_1.txt",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `legions/architect-4655708d/meta_architect-4655708d.json`

- **Line 1** (Hardcoded Home Directory):
  ```
  {"rome_v": "1.1-compat", "task_id": "architect-4655708d", "result": {"status": "SUCCESS", "exit_code": 0, "path": "/home/paul-kane/projects/rome-core/legions/architect-4655708d/report_architect-4655708d.txt"}}
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 1** (Hardcoded Username (paul-kane)):
  ```
  {"rome_v": "1.1-compat", "task_id": "architect-4655708d", "result": {"status": "SUCCESS", "exit_code": 0, "path": "/home/paul-kane/projects/rome-core/legions/architect-4655708d/report_architect-4655708d.txt"}}
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `legions/architect-4655708d/manifest.json`

- **Line 23** (Hardcoded Home Directory):
  ```
  "path": "/home/paul-kane/projects/rome-core/legions/architect-4655708d/report_architect-4655708d.txt",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 23** (Hardcoded Username (paul-kane)):
  ```
  "path": "/home/paul-kane/projects/rome-core/legions/architect-4655708d/report_architect-4655708d.txt",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `legions/imperial_heartbeat_patch_1/meta_imperial_heartbeat_patch_1.json`

- **Line 1** (Hardcoded Home Directory):
  ```
  {"rome_v": "1.1-compat", "task_id": "imperial_heartbeat_patch_1", "result": {"status": "FAILED", "exit_code": 1, "path": "/home/paul-kane/projects/rome-core/legions/imperial_heartbeat_patch_1/report_imperial_heartbeat_patch_1.txt"}}
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 1** (Hardcoded Username (paul-kane)):
  ```
  {"rome_v": "1.1-compat", "task_id": "imperial_heartbeat_patch_1", "result": {"status": "FAILED", "exit_code": 1, "path": "/home/paul-kane/projects/rome-core/legions/imperial_heartbeat_patch_1/report_imperial_heartbeat_patch_1.txt"}}
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `legions/imperial_heartbeat_patch_1/manifest.json`

- **Line 16** (Hardcoded Home Directory):
  ```
  "path": "/home/paul-kane/projects/rome-core/legions/imperial_heartbeat_patch_1/report_imperial_heartbeat_patch_1.txt",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 16** (Hardcoded Username (paul-kane)):
  ```
  "path": "/home/paul-kane/projects/rome-core/legions/imperial_heartbeat_patch_1/report_imperial_heartbeat_patch_1.txt",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `legions/architect-f3eabd48/meta_architect-f3eabd48.json`

- **Line 1** (Hardcoded Home Directory):
  ```
  {"rome_v": "1.1-compat", "task_id": "architect-f3eabd48", "result": {"status": "SUCCESS", "exit_code": 0, "path": "/home/paul-kane/projects/rome-core/legions/architect-f3eabd48/report_architect-f3eabd48.txt"}}
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 1** (Hardcoded Username (paul-kane)):
  ```
  {"rome_v": "1.1-compat", "task_id": "architect-f3eabd48", "result": {"status": "SUCCESS", "exit_code": 0, "path": "/home/paul-kane/projects/rome-core/legions/architect-f3eabd48/report_architect-f3eabd48.txt"}}
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `legions/architect-f3eabd48/manifest.json`

- **Line 21** (Hardcoded Home Directory):
  ```
  "path": "/home/paul-kane/projects/rome-core/legions/architect-f3eabd48/report_architect-f3eabd48.txt",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 21** (Hardcoded Username (paul-kane)):
  ```
  "path": "/home/paul-kane/projects/rome-core/legions/architect-f3eabd48/report_architect-f3eabd48.txt",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `legions/setup-md_retry/meta_setup-md_retry.json`

- **Line 1** (Hardcoded Home Directory):
  ```
  {"rome_v": "1.1-compat", "task_id": "setup-md_retry", "result": {"status": "SUCCESS", "exit_code": 0, "path": "/home/paul-kane/projects/rome-core/legions/setup-md_retry/report_setup-md_retry.txt"}}
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 1** (Hardcoded Username (paul-kane)):
  ```
  {"rome_v": "1.1-compat", "task_id": "setup-md_retry", "result": {"status": "SUCCESS", "exit_code": 0, "path": "/home/paul-kane/projects/rome-core/legions/setup-md_retry/report_setup-md_retry.txt"}}
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `legions/setup-md_retry/manifest.json`

- **Line 36** (Hardcoded Home Directory):
  ```
  "path": "/home/paul-kane/projects/rome-core/legions/setup-md_retry/report_setup-md_retry.txt",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 36** (Hardcoded Username (paul-kane)):
  ```
  "path": "/home/paul-kane/projects/rome-core/legions/setup-md_retry/report_setup-md_retry.txt",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `legions/e2e-proof-task-101/meta_e2e-proof-task-101.json`

- **Line 1** (Hardcoded Home Directory):
  ```
  {"rome_v": "1.1-compat", "task_id": "e2e-proof-task-101", "result": {"status": "FAILED", "exit_code": 1, "path": "/home/paul-kane/projects/rome-core/legions/e2e-proof-task-101/report_e2e-proof-task-101.txt"}}
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 1** (Hardcoded Username (paul-kane)):
  ```
  {"rome_v": "1.1-compat", "task_id": "e2e-proof-task-101", "result": {"status": "FAILED", "exit_code": 1, "path": "/home/paul-kane/projects/rome-core/legions/e2e-proof-task-101/report_e2e-proof-task-101.txt"}}
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `legions/e2e-proof-task-101/manifest.json`

- **Line 16** (Hardcoded Home Directory):
  ```
  "path": "/home/paul-kane/projects/rome-core/legions/e2e-proof-task-101/report_e2e-proof-task-101.txt",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 16** (Hardcoded Username (paul-kane)):
  ```
  "path": "/home/paul-kane/projects/rome-core/legions/e2e-proof-task-101/report_e2e-proof-task-101.txt",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `legions/fu_claude_task_1/meta_fu_claude_task_1.json`

- **Line 1** (Hardcoded Home Directory):
  ```
  {"rome_v": "1.1-compat", "task_id": "fu_claude_task_1", "result": {"status": "FAILED", "exit_code": 1, "path": "/home/paul-kane/projects/rome-core/legions/fu_claude_task_1/report_fu_claude_task_1.txt"}}
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 1** (Hardcoded Username (paul-kane)):
  ```
  {"rome_v": "1.1-compat", "task_id": "fu_claude_task_1", "result": {"status": "FAILED", "exit_code": 1, "path": "/home/paul-kane/projects/rome-core/legions/fu_claude_task_1/report_fu_claude_task_1.txt"}}
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `legions/fu_claude_task_1/manifest.json`

- **Line 14** (Hardcoded Home Directory):
  ```
  "path": "/home/paul-kane/projects/rome-core/legions/fu_claude_task_1/report_fu_claude_task_1.txt",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 14** (Hardcoded Username (paul-kane)):
  ```
  "path": "/home/paul-kane/projects/rome-core/legions/fu_claude_task_1/report_fu_claude_task_1.txt",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `legions/write-launchd/meta_write-launchd.json`

- **Line 1** (Hardcoded Home Directory):
  ```
  {"rome_v": "1.1-compat", "task_id": "write-launchd", "result": {"status": "SUCCESS", "exit_code": 0, "path": "/home/paul-kane/projects/rome-core/legions/write-launchd/report_write-launchd.txt"}}
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 1** (Hardcoded Username (paul-kane)):
  ```
  {"rome_v": "1.1-compat", "task_id": "write-launchd", "result": {"status": "SUCCESS", "exit_code": 0, "path": "/home/paul-kane/projects/rome-core/legions/write-launchd/report_write-launchd.txt"}}
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `legions/write-launchd/manifest.json`

- **Line 6** (Hardcoded Home Directory):
  ```
  "changed": "/home/paul-kane/projects/rome-core/ops/rome-dictator-freebsd-rc:new_file",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 6** (Hardcoded Username (paul-kane)):
  ```
  "changed": "/home/paul-kane/projects/rome-core/ops/rome-dictator-freebsd-rc:new_file",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 45** (Hardcoded Home Directory):
  ```
  "path": "/home/paul-kane/projects/rome-core/legions/write-launchd/report_write-launchd.txt",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 45** (Hardcoded Username (paul-kane)):
  ```
  "path": "/home/paul-kane/projects/rome-core/legions/write-launchd/report_write-launchd.txt",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `legions/humiliate-architect-1/meta_humiliate-architect-1.json`

- **Line 1** (Hardcoded Home Directory):
  ```
  {"rome_v": "1.1-compat", "task_id": "humiliate-architect-1", "result": {"status": "SUCCESS", "exit_code": 0, "path": "/home/paul-kane/projects/rome-core/legions/humiliate-architect-1/report_humiliate-architect-1.txt"}}
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 1** (Hardcoded Username (paul-kane)):
  ```
  {"rome_v": "1.1-compat", "task_id": "humiliate-architect-1", "result": {"status": "SUCCESS", "exit_code": 0, "path": "/home/paul-kane/projects/rome-core/legions/humiliate-architect-1/report_humiliate-architect-1.txt"}}
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `legions/humiliate-architect-1/manifest.json`

- **Line 29** (Hardcoded Home Directory):
  ```
  "path": "/home/paul-kane/projects/rome-core/legions/humiliate-architect-1/report_humiliate-architect-1.txt",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 29** (Hardcoded Username (paul-kane)):
  ```
  "path": "/home/paul-kane/projects/rome-core/legions/humiliate-architect-1/report_humiliate-architect-1.txt",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `legions/write-setup/meta_write-setup.json`

- **Line 1** (Hardcoded Home Directory):
  ```
  {"rome_v": "1.1-compat", "task_id": "write-setup", "result": {"status": "SUCCESS", "exit_code": 0, "path": "/home/paul-kane/projects/rome-core/legions/write-setup/report_write-setup.txt"}}
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 1** (Hardcoded Username (paul-kane)):
  ```
  {"rome_v": "1.1-compat", "task_id": "write-setup", "result": {"status": "SUCCESS", "exit_code": 0, "path": "/home/paul-kane/projects/rome-core/legions/write-setup/report_write-setup.txt"}}
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `legions/write-setup/manifest.json`

- **Line 34** (Hardcoded Home Directory):
  ```
  "path": "/home/paul-kane/projects/rome-core/legions/write-setup/report_write-setup.txt",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 34** (Hardcoded Username (paul-kane)):
  ```
  "path": "/home/paul-kane/projects/rome-core/legions/write-setup/report_write-setup.txt",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `legions/architect-bba4a3fe/meta_architect-bba4a3fe.json`

- **Line 1** (Hardcoded Home Directory):
  ```
  {"rome_v": "1.1-compat", "task_id": "architect-bba4a3fe", "result": {"status": "SUCCESS", "exit_code": 0, "path": "/home/paul-kane/projects/rome-core/legions/architect-bba4a3fe/report_architect-bba4a3fe.txt"}}
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 1** (Hardcoded Username (paul-kane)):
  ```
  {"rome_v": "1.1-compat", "task_id": "architect-bba4a3fe", "result": {"status": "SUCCESS", "exit_code": 0, "path": "/home/paul-kane/projects/rome-core/legions/architect-bba4a3fe/report_architect-bba4a3fe.txt"}}
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `legions/architect-bba4a3fe/manifest.json`

- **Line 21** (Hardcoded Home Directory):
  ```
  "path": "/home/paul-kane/projects/rome-core/legions/architect-bba4a3fe/report_architect-bba4a3fe.txt",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 21** (Hardcoded Username (paul-kane)):
  ```
  "path": "/home/paul-kane/projects/rome-core/legions/architect-bba4a3fe/report_architect-bba4a3fe.txt",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `legions/portability-update_update-docs/manifest.json`

- **Line 16** (Hardcoded Home Directory):
  ```
  "path": "/home/paul-kane/projects/rome-core/legions/portability-update_update-docs/report_portability-update_update-docs.txt",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 16** (Hardcoded Username (paul-kane)):
  ```
  "path": "/home/paul-kane/projects/rome-core/legions/portability-update_update-docs/report_portability-update_update-docs.txt",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `legions/portability-update_update-docs/meta_portability-update_update-docs.json`

- **Line 1** (Hardcoded Home Directory):
  ```
  {"rome_v": "1.1-compat", "task_id": "portability-update_update-docs", "result": {"status": "FAILED", "exit_code": 1, "path": "/home/paul-kane/projects/rome-core/legions/portability-update_update-docs/report_portability-update_update-docs.txt"}}
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 1** (Hardcoded Username (paul-kane)):
  ```
  {"rome_v": "1.1-compat", "task_id": "portability-update_update-docs", "result": {"status": "FAILED", "exit_code": 1, "path": "/home/paul-kane/projects/rome-core/legions/portability-update_update-docs/report_portability-update_update-docs.txt"}}
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `legions/portability-docs-2_write-setup/meta_portability-docs-2_write-setup.json`

- **Line 1** (Hardcoded Home Directory):
  ```
  {"rome_v": "1.1-compat", "task_id": "portability-docs-2_write-setup", "result": {"status": "SUCCESS", "exit_code": 0, "path": "/home/paul-kane/projects/rome-core/legions/portability-docs-2_write-setup/report_portability-docs-2_write-setup.txt"}}
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 1** (Hardcoded Username (paul-kane)):
  ```
  {"rome_v": "1.1-compat", "task_id": "portability-docs-2_write-setup", "result": {"status": "SUCCESS", "exit_code": 0, "path": "/home/paul-kane/projects/rome-core/legions/portability-docs-2_write-setup/report_portability-docs-2_write-setup.txt"}}
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `legions/portability-docs-2_write-setup/manifest.json`

- **Line 60** (Hardcoded Home Directory):
  ```
  "path": "/home/paul-kane/projects/rome-core/legions/portability-docs-2_write-setup/report_portability-docs-2_write-setup.txt",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 60** (Hardcoded Username (paul-kane)):
  ```
  "path": "/home/paul-kane/projects/rome-core/legions/portability-docs-2_write-setup/report_portability-docs-2_write-setup.txt",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `legions/architect-protocol-audit/meta_architect-protocol-audit.json`

- **Line 1** (Hardcoded Home Directory):
  ```
  {"rome_v": "1.1-compat", "task_id": "architect-protocol-audit", "result": {"status": "SUCCESS", "exit_code": 0, "path": "/home/paul-kane/projects/rome-core/legions/architect-protocol-audit/report_architect-protocol-audit.txt"}}
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 1** (Hardcoded Username (paul-kane)):
  ```
  {"rome_v": "1.1-compat", "task_id": "architect-protocol-audit", "result": {"status": "SUCCESS", "exit_code": 0, "path": "/home/paul-kane/projects/rome-core/legions/architect-protocol-audit/report_architect-protocol-audit.txt"}}
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `legions/architect-protocol-audit/manifest.json`

- **Line 45** (Hardcoded Home Directory):
  ```
  "path": "/home/paul-kane/projects/rome-core/legions/architect-protocol-audit/report_architect-protocol-audit.txt",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 45** (Hardcoded Username (paul-kane)):
  ```
  "path": "/home/paul-kane/projects/rome-core/legions/architect-protocol-audit/report_architect-protocol-audit.txt",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `legions/audit-portability-2/meta_audit-portability-2.json`

- **Line 1** (Hardcoded Home Directory):
  ```
  {"rome_v": "1.1-compat", "task_id": "audit-portability-2", "result": {"status": "FAILED", "exit_code": 1, "path": "/home/paul-kane/projects/rome-core/legions/audit-portability-2/report_audit-portability-2.txt"}}
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 1** (Hardcoded Username (paul-kane)):
  ```
  {"rome_v": "1.1-compat", "task_id": "audit-portability-2", "result": {"status": "FAILED", "exit_code": 1, "path": "/home/paul-kane/projects/rome-core/legions/audit-portability-2/report_audit-portability-2.txt"}}
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `legions/audit-portability-2/manifest.json`

- **Line 16** (Hardcoded Home Directory):
  ```
  "path": "/home/paul-kane/projects/rome-core/legions/audit-portability-2/report_audit-portability-2.txt",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 16** (Hardcoded Username (paul-kane)):
  ```
  "path": "/home/paul-kane/projects/rome-core/legions/audit-portability-2/report_audit-portability-2.txt",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `legions/architect-6530af7a/meta_architect-6530af7a.json`

- **Line 1** (Hardcoded Home Directory):
  ```
  {"rome_v": "1.1-compat", "task_id": "architect-6530af7a", "result": {"status": "SUCCESS", "exit_code": 0, "path": "/home/paul-kane/projects/rome-core/legions/architect-6530af7a/report_architect-6530af7a.txt"}}
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 1** (Hardcoded Username (paul-kane)):
  ```
  {"rome_v": "1.1-compat", "task_id": "architect-6530af7a", "result": {"status": "SUCCESS", "exit_code": 0, "path": "/home/paul-kane/projects/rome-core/legions/architect-6530af7a/report_architect-6530af7a.txt"}}
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `legions/architect-6530af7a/manifest.json`

- **Line 30** (Hardcoded Home Directory):
  ```
  "path": "/home/paul-kane/projects/rome-core/legions/architect-6530af7a/report_architect-6530af7a.txt",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 30** (Hardcoded Username (paul-kane)):
  ```
  "path": "/home/paul-kane/projects/rome-core/legions/architect-6530af7a/report_architect-6530af7a.txt",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `legions/architect-02b1b985/meta_architect-02b1b985.json`

- **Line 1** (Hardcoded Home Directory):
  ```
  {"rome_v": "1.1-compat", "task_id": "architect-02b1b985", "result": {"status": "SUCCESS", "exit_code": 0, "path": "/home/paul-kane/projects/rome-core/legions/architect-02b1b985/report_architect-02b1b985.txt"}}
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 1** (Hardcoded Username (paul-kane)):
  ```
  {"rome_v": "1.1-compat", "task_id": "architect-02b1b985", "result": {"status": "SUCCESS", "exit_code": 0, "path": "/home/paul-kane/projects/rome-core/legions/architect-02b1b985/report_architect-02b1b985.txt"}}
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `legions/architect-02b1b985/manifest.json`

- **Line 29** (Hardcoded Home Directory):
  ```
  "path": "/home/paul-kane/projects/rome-core/legions/architect-02b1b985/report_architect-02b1b985.txt",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 29** (Hardcoded Username (paul-kane)):
  ```
  "path": "/home/paul-kane/projects/rome-core/legions/architect-02b1b985/report_architect-02b1b985.txt",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `arsenal/core_arsenal.json`

- **Line 4** (Hardcoded Home Directory):
  ```
  "exec": "/home/paul-kane/projects/rome-core/legions/legion_wrapper.py",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 4** (Hardcoded Username (paul-kane)):
  ```
  "exec": "/home/paul-kane/projects/rome-core/legions/legion_wrapper.py",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 6** (Hardcoded Home Directory):
  ```
  "/home/paul-kane/projects/gemini-cli/bundle/gemini.js",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 6** (Hardcoded Username (paul-kane)):
  ```
  "/home/paul-kane/projects/gemini-cli/bundle/gemini.js",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 10** (Hardcoded Home Directory):
  ```
  "/home/paul-kane/projects",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 10** (Hardcoded Username (paul-kane)):
  ```
  "/home/paul-kane/projects",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 25** (Hardcoded Home Directory):
  ```
  "exec": "/home/paul-kane/projects/rome-core/legions/legion_wrapper.py",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 25** (Hardcoded Username (paul-kane)):
  ```
  "exec": "/home/paul-kane/projects/rome-core/legions/legion_wrapper.py",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 40** (Hardcoded Home Directory):
  ```
  "exec": "/home/paul-kane/projects/rome-core/legions/legion_wrapper.py",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 40** (Hardcoded Username (paul-kane)):
  ```
  "exec": "/home/paul-kane/projects/rome-core/legions/legion_wrapper.py",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 50** (Hardcoded Home Directory):
  ```
  "exec": "/home/paul-kane/projects/rome-core/legions/legion_wrapper.py",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 50** (Hardcoded Username (paul-kane)):
  ```
  "exec": "/home/paul-kane/projects/rome-core/legions/legion_wrapper.py",
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 66** (Hardcoded Home Directory):
  ```
  "/home/paul-kane/projects/rome-core/dictator/mcp_client_tool.py"
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 66** (Hardcoded Username (paul-kane)):
  ```
  "/home/paul-kane/projects/rome-core/dictator/mcp_client_tool.py"
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 75** (Hardcoded Home Directory):
  ```
  "/home/paul-kane/projects/rome-core/legions/shell_executor.py"
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 75** (Hardcoded Username (paul-kane)):
  ```
  "/home/paul-kane/projects/rome-core/legions/shell_executor.py"
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `.gemini/settings.json`

- **Line 6** (Hardcoded Home Directory):
  ```
  "/home/paul-kane/projects/rome-core/dictator/cli.py"
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 6** (Hardcoded Username (paul-kane)):
  ```
  "/home/paul-kane/projects/rome-core/dictator/cli.py"
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `campaigns/gemini-ws-transport.yaml`

- **Line 7** (Hardcoded Home Directory):
  ```
  - /home/paul-kane/projects/gemini-cli/packages/core/src/tools/websocket-client-transport.ts
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 7** (Hardcoded Username (paul-kane)):
  ```
  - /home/paul-kane/projects/gemini-cli/packages/core/src/tools/websocket-client-transport.ts
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 8** (Hardcoded Home Directory):
  ```
  - /home/paul-kane/projects/gemini-cli/packages/core/src/tools/mcp-client.ts
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 8** (Hardcoded Username (paul-kane)):
  ```
  - /home/paul-kane/projects/gemini-cli/packages/core/src/tools/mcp-client.ts
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 9** (Hardcoded Home Directory):
  ```
  - /home/paul-kane/projects/gemini-cli/packages/core/src/tools/xcode-mcp-fix-transport.ts
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 9** (Hardcoded Username (paul-kane)):
  ```
  - /home/paul-kane/projects/gemini-cli/packages/core/src/tools/xcode-mcp-fix-transport.ts
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 10** (Hardcoded Home Directory):
  ```
  - /home/paul-kane/projects/gemini-cli/packages/vscode-ide-companion/src/ide-server.ts
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 10** (Hardcoded Username (paul-kane)):
  ```
  - /home/paul-kane/projects/gemini-cli/packages/vscode-ide-companion/src/ide-server.ts
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 18** (Hardcoded Home Directory):
  ```
  - /home/paul-kane/projects/gemini-cli/packages/vscode-ide-companion/src/ide-server.ts
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 18** (Hardcoded Username (paul-kane)):
  ```
  - /home/paul-kane/projects/gemini-cli/packages/vscode-ide-companion/src/ide-server.ts
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 19** (Hardcoded Home Directory):
  ```
  - /home/paul-kane/projects/gemini-cli/packages/core/src/tools/xcode-mcp-fix-transport.ts
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 19** (Hardcoded Username (paul-kane)):
  ```
  - /home/paul-kane/projects/gemini-cli/packages/core/src/tools/xcode-mcp-fix-transport.ts
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 27** (Hardcoded Home Directory):
  ```
  - /home/paul-kane/projects/gemini-cli/packages/vscode-ide-companion/src/ide-server.ts
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 27** (Hardcoded Username (paul-kane)):
  ```
  - /home/paul-kane/projects/gemini-cli/packages/vscode-ide-companion/src/ide-server.ts
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 35** (Hardcoded Home Directory):
  ```
  - /home/paul-kane/projects/gemini-cli/packages/core/src/tools/mcp-client.ts
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 35** (Hardcoded Username (paul-kane)):
  ```
  - /home/paul-kane/projects/gemini-cli/packages/core/src/tools/mcp-client.ts
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 36** (Hardcoded Home Directory):
  ```
  - /home/paul-kane/projects/gemini-cli/packages/core/src/tools/websocket-client-transport.ts
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 36** (Hardcoded Username (paul-kane)):
  ```
  - /home/paul-kane/projects/gemini-cli/packages/core/src/tools/websocket-client-transport.ts
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 45** (Hardcoded Home Directory):
  ```
  - /home/paul-kane/projects/gemini-cli/packages/core/src/tools/mcp-client.test.ts
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 45** (Hardcoded Username (paul-kane)):
  ```
  - /home/paul-kane/projects/gemini-cli/packages/core/src/tools/mcp-client.test.ts
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 46** (Hardcoded Home Directory):
  ```
  - /home/paul-kane/projects/gemini-cli/packages/cli/src/config/mcp/mcpServerEnablement.test.ts
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 46** (Hardcoded Username (paul-kane)):
  ```
  - /home/paul-kane/projects/gemini-cli/packages/cli/src/config/mcp/mcpServerEnablement.test.ts
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 47** (Hardcoded Home Directory):
  ```
  - /home/paul-kane/projects/gemini-cli/packages/core/src/tools/websocket-client-transport.ts
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 47** (Hardcoded Username (paul-kane)):
  ```
  - /home/paul-kane/projects/gemini-cli/packages/core/src/tools/websocket-client-transport.ts
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `campaigns/loader.py`

- **Line 10** (Hardcoded Home Directory):
  ```
  ROME_ROOT = os.environ.get("ROME_ROOT", "/home/paul-kane/projects/rome-core")
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 10** (Hardcoded Username (paul-kane)):
  ```
  ROME_ROOT = os.environ.get("ROME_ROOT", "/home/paul-kane/projects/rome-core")
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 12** (Local IP (127.0.0.1/0.0.0.0)):
  ```
  _WS_URL = os.environ.get("ROME_WS_URL", "ws://127.0.0.1:8741/ws")
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

## `daemon.build/scons-debug.py`

- **Line 8** (Hardcoded Home Directory):
  ```
  ['/usr/bin/python3', '-W', 'ignore', '/home/paul-kane/.local/lib/python3.12/site-packages/nuitka/build/inline_copy/bin/scons.py', '--quiet', '-f', '/home/paul-kane/.local/lib/python3.12/site-packages/nuitka/build/Backend.scons', '--jobs', '32', '--warn=no-deprecated', '--no-site-dir', 'nuitka_src=/home/paul-kane/.local/lib/python3.12/site-packages/nuitka/build', 'python_version=3.12', 'python_prefix=/usr', 'experimental=', 'debug_modes=', 'deployment=false', 'no_deployment=', 'gil_mode=true', 'reproducible_mode=true', 'cpp_defines=_NUITKA_PLUGIN_MULTIPROCESSING_ENABLED=1', 'target_arch=x86_64', 'module_mode=false', 'dll_mode=false', 'exe_mode=true', 'standalone_mode=true', 'onefile_mode=true', 'onefile_temp_mode=true', 'source_dir=.', 'monolithpy=false', 'debug_mode=false', 'debugger_mode=false', 'python_debug=false', 'full_compat=false', 'trace_mode=false', 'file_reference_mode=runtime', 'compiled_module_count=1090', 'result_exe=/home/paul-kane/projects/rome-core/daemon.dist/rome-v4-kernel.bin', 'static_libpython=/usr/lib/python3.12/config-3.12-x86_64-linux-gnu/libpython3.12-pic.a', 'debian_python=true', 'frozen_modules=149', 'python_sysflag_no_site=true'],
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 8** (Hardcoded Username (paul-kane)):
  ```
  ['/usr/bin/python3', '-W', 'ignore', '/home/paul-kane/.local/lib/python3.12/site-packages/nuitka/build/inline_copy/bin/scons.py', '--quiet', '-f', '/home/paul-kane/.local/lib/python3.12/site-packages/nuitka/build/Backend.scons', '--jobs', '32', '--warn=no-deprecated', '--no-site-dir', 'nuitka_src=/home/paul-kane/.local/lib/python3.12/site-packages/nuitka/build', 'python_version=3.12', 'python_prefix=/usr', 'experimental=', 'debug_modes=', 'deployment=false', 'no_deployment=', 'gil_mode=true', 'reproducible_mode=true', 'cpp_defines=_NUITKA_PLUGIN_MULTIPROCESSING_ENABLED=1', 'target_arch=x86_64', 'module_mode=false', 'dll_mode=false', 'exe_mode=true', 'standalone_mode=true', 'onefile_mode=true', 'onefile_temp_mode=true', 'source_dir=.', 'monolithpy=false', 'debug_mode=false', 'debugger_mode=false', 'python_debug=false', 'full_compat=false', 'trace_mode=false', 'file_reference_mode=runtime', 'compiled_module_count=1090', 'result_exe=/home/paul-kane/projects/rome-core/daemon.dist/rome-v4-kernel.bin', 'static_libpython=/usr/lib/python3.12/config-3.12-x86_64-linux-gnu/libpython3.12-pic.a', 'debian_python=true', 'frozen_modules=149', 'python_sysflag_no_site=true'],
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 9** (Hardcoded Home Directory):
  ```
  env={'SHELL': '/bin/bash','SESSION_MANAGER': 'local/HAL9000:@/tmp/.ICE-unix/2522,unix/HAL9000:/tmp/.ICE-unix/2522','QT_ACCESSIBILITY': '1','XDG_CONFIG_DIRS': '/etc/xdg/xdg-ubuntu:/etc/xdg','NVM_INC': '/home/paul-kane/.nvm/versions/node/v20.20.0/include/node','XDG_MENU_PREFIX': 'gnome-','GNOME_DESKTOP_SESSION_ID': 'this-is-deprecated','GNOME_SHELL_SESSION_MODE': 'ubuntu','MEMORY_PRESSURE_WRITE': 'c29tZSAyMDAwMDAgMjAwMDAwMAA=','XMODIFIERS': '@im=ibus','DESKTOP_SESSION': 'ubuntu','GTK_MODULES': 'gail:atk-bridge','DBUS_STARTER_BUS_TYPE': 'session','PWD': '/home/paul-kane/projects/rome-core','XDG_SESSION_DESKTOP': 'ubuntu','LOGNAME': 'paul-kane','XDG_SESSION_TYPE': 'x11','GPG_AGENT_INFO': '/run/user/1000/gnupg/S.gpg-agent:0:1','SYSTEMD_EXEC_PID': '2522','WINDOWPATH': '2','HOME': '/home/paul-kane','USERNAME': 'paul-kane','LANG': 'en_US.UTF-8','LS_COLORS': 'rs=0:di=01;34:ln=01;36:mh=00:pi=40;33:so=01;35:do=01;35:bd=40;33;01:cd=40;33;01:or=40;31;01:mi=00:su=37;41:sg=30;43:ca=00:tw=30;42:ow=34;42:st=37;44:ex=01;32:*.tar=01;31:*.tgz=01;31:*.arc=01;31:*.arj=01;31:*.taz=01;31:*.lha=01;31:*.lz4=01;31:*.lzh=01;31:*.lzma=01;31:*.tlz=01;31:*.txz=01;31:*.tzo=01;31:*.t7z=01;31:*.zip=01;31:*.z=01;31:*.dz=01;31:*.gz=01;31:*.lrz=01;31:*.lz=01;31:*.lzo=01;31:*.xz=01;31:*.zst=01;31:*.tzst=01;31:*.bz2=01;31:*.bz=01;31:*.tbz=01;31:*.tbz2=01;31:*.tz=01;31:*.deb=01;31:*.rpm=01;31:*.jar=01;31:*.war=01;31:*.ear=01;31:*.sar=01;31:*.rar=01;31:*.alz=01;31:*.ace=01;31:*.zoo=01;31:*.cpio=01;31:*.7z=01;31:*.rz=01;31:*.cab=01;31:*.wim=01;31:*.swm=01;31:*.dwm=01;31:*.esd=01;31:*.avif=01;35:*.jpg=01;35:*.jpeg=01;35:*.mjpg=01;35:*.mjpeg=01;35:*.gif=01;35:*.bmp=01;35:*.pbm=01;35:*.pgm=01;35:*.ppm=01;35:*.tga=01;35:*.xbm=01;35:*.xpm=01;35:*.tif=01;35:*.tiff=01;35:*.png=01;35:*.svg=01;35:*.svgz=01;35:*.mng=01;35:*.pcx=01;35:*.mov=01;35:*.mpg=01;35:*.mpeg=01;35:*.m2v=01;35:*.mkv=01;35:*.webm=01;35:*.webp=01;35:*.ogm=01;35:*.mp4=01;35:*.m4v=01;35:*.mp4v=01;35:*.vob=01;35:*.qt=01;35:*.nuv=01;35:*.wmv=01;35:*.asf=01;35:*.rm=01;35:*.rmvb=01;35:*.flc=01;35:*.avi=01;35:*.fli=01;35:*.flv=01;35:*.gl=01;35:*.dl=01;35:*.xcf=01;35:*.xwd=01;35:*.yuv=01;35:*.cgm=01;35:*.emf=01;35:*.ogv=01;35:*.ogx=01;35:*.aac=00;36:*.au=00;36:*.flac=00;36:*.m4a=00;36:*.mid=00;36:*.midi=00;36:*.mka=00;36:*.mp3=00;36:*.mpc=00;36:*.ogg=00;36:*.ra=00;36:*.wav=00;36:*.oga=00;36:*.opus=00;36:*.spx=00;36:*.xspf=00;36:*~=00;90:*#=00;90:*.bak=00;90:*.crdownload=00;90:*.dpkg-dist=00;90:*.dpkg-new=00;90:*.dpkg-old=00;90:*.dpkg-tmp=00;90:*.old=00;90:*.orig=00;90:*.part=00;90:*.rej=00;90:*.rpmnew=00;90:*.rpmorig=00;90:*.rpmsave=00;90:*.swp=00;90:*.tmp=00;90:*.ucf-dist=00;90:*.ucf-new=00;90:*.ucf-old=00;90:','XDG_CURRENT_DESKTOP': 'ubuntu:GNOME','MEMORY_PRESSURE_WATCH': '/sys/fs/cgroup/user.slice/user-1000.slice/user@1000.service/app.slice/app-gnome\\x2dsession\\x2dmanager.slice/gnome-session-manager@ubuntu.service/memory.pressure','VTE_VERSION': '7600','GNOME_TERMINAL_SCREEN': '/org/gnome/Terminal/screen/85f068a5_e9bf_491a_aa19_23900fb28a81','NVM_DIR': '/home/paul-kane/.nvm','LESSCLOSE': '/usr/bin/lesspipe %s %s','XDG_SESSION_CLASS': 'user','LESSOPEN': '| /usr/bin/lesspipe %s','USER': 'paul-kane','GNOME_TERMINAL_SERVICE': ':1.472','DISPLAY': ':1','SHLVL': '2','NVM_CD_FLAGS': '','GSM_SKIP_SSH_AGENT_WORKAROUND': 'true','PAGER': 'cat','QT_IM_MODULE': 'ibus','DBUS_STARTER_ADDRESS': 'unix:path=/run/user/1000/bus,guid=daf02d337b8040bf29b16ce469b9b237','XDG_RUNTIME_DIR': '/run/user/1000','GEMINI_CLI': '1','DEBUGINFOD_URLS': 'https://debuginfod.ubuntu.com ','BUN_INSTALL': '/home/paul-kane/.bun','GEMINI_CLI_NO_RELAUNCH': 'true','XDG_DATA_DIRS': '/usr/share/ubuntu:/usr/share/gnome:/home/paul-kane/.local/share/flatpak/exports/share:/var/lib/flatpak/exports/share:/usr/local/share/:/usr/share/','PATH': '/home/paul-kane/.bun/bin:/home/paul-kane/.nvm/versions/node/v20.20.0/bin:/home/paul-kane/.local/bin:/var/www/drupal/vendor/bin:/home/paul-kane/.cargo/bin:/home/paul-kane/.local/bin:/home/paul-kane/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games:/usr/local/games:/snap/bin','GDMSESSION': 'ubuntu','DBUS_SESSION_BUS_ADDRESS': 'unix:path=/run/user/1000/bus,guid=daf02d337b8040bf29b16ce469b9b237','NVM_BIN': '/home/paul-kane/.nvm/versions/node/v20.20.0/bin','OLDPWD': '/media/paul-kane/SteamGames/Games','_': '/usr/bin/python3','PYTHONHASHSEED': '0','NUITKA_PYTHON_EXE_PATH': '/usr/bin/python3','NUITKA_PACKAGE_DIR': '/home/paul-kane/.local/lib/python3.12/site-packages/nuitka','_NUITKA_ONEFILE_CHILD_GRACE_TIME_INT': '5000','_NUITKA_BUILD_DEFINITIONS_CATALOG': '_NUITKA_ONEFILE_CHILD_GRACE_TIME_INT,_NUITKA_BUILD_DEFINITIONS_CATALOG','NUITKA_QUIET': '0'},
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 9** (Hardcoded /var/www path):
  ```
  env={'SHELL': '/bin/bash','SESSION_MANAGER': 'local/HAL9000:@/tmp/.ICE-unix/2522,unix/HAL9000:/tmp/.ICE-unix/2522','QT_ACCESSIBILITY': '1','XDG_CONFIG_DIRS': '/etc/xdg/xdg-ubuntu:/etc/xdg','NVM_INC': '/home/paul-kane/.nvm/versions/node/v20.20.0/include/node','XDG_MENU_PREFIX': 'gnome-','GNOME_DESKTOP_SESSION_ID': 'this-is-deprecated','GNOME_SHELL_SESSION_MODE': 'ubuntu','MEMORY_PRESSURE_WRITE': 'c29tZSAyMDAwMDAgMjAwMDAwMAA=','XMODIFIERS': '@im=ibus','DESKTOP_SESSION': 'ubuntu','GTK_MODULES': 'gail:atk-bridge','DBUS_STARTER_BUS_TYPE': 'session','PWD': '/home/paul-kane/projects/rome-core','XDG_SESSION_DESKTOP': 'ubuntu','LOGNAME': 'paul-kane','XDG_SESSION_TYPE': 'x11','GPG_AGENT_INFO': '/run/user/1000/gnupg/S.gpg-agent:0:1','SYSTEMD_EXEC_PID': '2522','WINDOWPATH': '2','HOME': '/home/paul-kane','USERNAME': 'paul-kane','LANG': 'en_US.UTF-8','LS_COLORS': 'rs=0:di=01;34:ln=01;36:mh=00:pi=40;33:so=01;35:do=01;35:bd=40;33;01:cd=40;33;01:or=40;31;01:mi=00:su=37;41:sg=30;43:ca=00:tw=30;42:ow=34;42:st=37;44:ex=01;32:*.tar=01;31:*.tgz=01;31:*.arc=01;31:*.arj=01;31:*.taz=01;31:*.lha=01;31:*.lz4=01;31:*.lzh=01;31:*.lzma=01;31:*.tlz=01;31:*.txz=01;31:*.tzo=01;31:*.t7z=01;31:*.zip=01;31:*.z=01;31:*.dz=01;31:*.gz=01;31:*.lrz=01;31:*.lz=01;31:*.lzo=01;31:*.xz=01;31:*.zst=01;31:*.tzst=01;31:*.bz2=01;31:*.bz=01;31:*.tbz=01;31:*.tbz2=01;31:*.tz=01;31:*.deb=01;31:*.rpm=01;31:*.jar=01;31:*.war=01;31:*.ear=01;31:*.sar=01;31:*.rar=01;31:*.alz=01;31:*.ace=01;31:*.zoo=01;31:*.cpio=01;31:*.7z=01;31:*.rz=01;31:*.cab=01;31:*.wim=01;31:*.swm=01;31:*.dwm=01;31:*.esd=01;31:*.avif=01;35:*.jpg=01;35:*.jpeg=01;35:*.mjpg=01;35:*.mjpeg=01;35:*.gif=01;35:*.bmp=01;35:*.pbm=01;35:*.pgm=01;35:*.ppm=01;35:*.tga=01;35:*.xbm=01;35:*.xpm=01;35:*.tif=01;35:*.tiff=01;35:*.png=01;35:*.svg=01;35:*.svgz=01;35:*.mng=01;35:*.pcx=01;35:*.mov=01;35:*.mpg=01;35:*.mpeg=01;35:*.m2v=01;35:*.mkv=01;35:*.webm=01;35:*.webp=01;35:*.ogm=01;35:*.mp4=01;35:*.m4v=01;35:*.mp4v=01;35:*.vob=01;35:*.qt=01;35:*.nuv=01;35:*.wmv=01;35:*.asf=01;35:*.rm=01;35:*.rmvb=01;35:*.flc=01;35:*.avi=01;35:*.fli=01;35:*.flv=01;35:*.gl=01;35:*.dl=01;35:*.xcf=01;35:*.xwd=01;35:*.yuv=01;35:*.cgm=01;35:*.emf=01;35:*.ogv=01;35:*.ogx=01;35:*.aac=00;36:*.au=00;36:*.flac=00;36:*.m4a=00;36:*.mid=00;36:*.midi=00;36:*.mka=00;36:*.mp3=00;36:*.mpc=00;36:*.ogg=00;36:*.ra=00;36:*.wav=00;36:*.oga=00;36:*.opus=00;36:*.spx=00;36:*.xspf=00;36:*~=00;90:*#=00;90:*.bak=00;90:*.crdownload=00;90:*.dpkg-dist=00;90:*.dpkg-new=00;90:*.dpkg-old=00;90:*.dpkg-tmp=00;90:*.old=00;90:*.orig=00;90:*.part=00;90:*.rej=00;90:*.rpmnew=00;90:*.rpmorig=00;90:*.rpmsave=00;90:*.swp=00;90:*.tmp=00;90:*.ucf-dist=00;90:*.ucf-new=00;90:*.ucf-old=00;90:','XDG_CURRENT_DESKTOP': 'ubuntu:GNOME','MEMORY_PRESSURE_WATCH': '/sys/fs/cgroup/user.slice/user-1000.slice/user@1000.service/app.slice/app-gnome\\x2dsession\\x2dmanager.slice/gnome-session-manager@ubuntu.service/memory.pressure','VTE_VERSION': '7600','GNOME_TERMINAL_SCREEN': '/org/gnome/Terminal/screen/85f068a5_e9bf_491a_aa19_23900fb28a81','NVM_DIR': '/home/paul-kane/.nvm','LESSCLOSE': '/usr/bin/lesspipe %s %s','XDG_SESSION_CLASS': 'user','LESSOPEN': '| /usr/bin/lesspipe %s','USER': 'paul-kane','GNOME_TERMINAL_SERVICE': ':1.472','DISPLAY': ':1','SHLVL': '2','NVM_CD_FLAGS': '','GSM_SKIP_SSH_AGENT_WORKAROUND': 'true','PAGER': 'cat','QT_IM_MODULE': 'ibus','DBUS_STARTER_ADDRESS': 'unix:path=/run/user/1000/bus,guid=daf02d337b8040bf29b16ce469b9b237','XDG_RUNTIME_DIR': '/run/user/1000','GEMINI_CLI': '1','DEBUGINFOD_URLS': 'https://debuginfod.ubuntu.com ','BUN_INSTALL': '/home/paul-kane/.bun','GEMINI_CLI_NO_RELAUNCH': 'true','XDG_DATA_DIRS': '/usr/share/ubuntu:/usr/share/gnome:/home/paul-kane/.local/share/flatpak/exports/share:/var/lib/flatpak/exports/share:/usr/local/share/:/usr/share/','PATH': '/home/paul-kane/.bun/bin:/home/paul-kane/.nvm/versions/node/v20.20.0/bin:/home/paul-kane/.local/bin:/var/www/drupal/vendor/bin:/home/paul-kane/.cargo/bin:/home/paul-kane/.local/bin:/home/paul-kane/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games:/usr/local/games:/snap/bin','GDMSESSION': 'ubuntu','DBUS_SESSION_BUS_ADDRESS': 'unix:path=/run/user/1000/bus,guid=daf02d337b8040bf29b16ce469b9b237','NVM_BIN': '/home/paul-kane/.nvm/versions/node/v20.20.0/bin','OLDPWD': '/media/paul-kane/SteamGames/Games','_': '/usr/bin/python3','PYTHONHASHSEED': '0','NUITKA_PYTHON_EXE_PATH': '/usr/bin/python3','NUITKA_PACKAGE_DIR': '/home/paul-kane/.local/lib/python3.12/site-packages/nuitka','_NUITKA_ONEFILE_CHILD_GRACE_TIME_INT': '5000','_NUITKA_BUILD_DEFINITIONS_CATALOG': '_NUITKA_ONEFILE_CHILD_GRACE_TIME_INT,_NUITKA_BUILD_DEFINITIONS_CATALOG','NUITKA_QUIET': '0'},
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 9** (Hardcoded NVM path):
  ```
  env={'SHELL': '/bin/bash','SESSION_MANAGER': 'local/HAL9000:@/tmp/.ICE-unix/2522,unix/HAL9000:/tmp/.ICE-unix/2522','QT_ACCESSIBILITY': '1','XDG_CONFIG_DIRS': '/etc/xdg/xdg-ubuntu:/etc/xdg','NVM_INC': '/home/paul-kane/.nvm/versions/node/v20.20.0/include/node','XDG_MENU_PREFIX': 'gnome-','GNOME_DESKTOP_SESSION_ID': 'this-is-deprecated','GNOME_SHELL_SESSION_MODE': 'ubuntu','MEMORY_PRESSURE_WRITE': 'c29tZSAyMDAwMDAgMjAwMDAwMAA=','XMODIFIERS': '@im=ibus','DESKTOP_SESSION': 'ubuntu','GTK_MODULES': 'gail:atk-bridge','DBUS_STARTER_BUS_TYPE': 'session','PWD': '/home/paul-kane/projects/rome-core','XDG_SESSION_DESKTOP': 'ubuntu','LOGNAME': 'paul-kane','XDG_SESSION_TYPE': 'x11','GPG_AGENT_INFO': '/run/user/1000/gnupg/S.gpg-agent:0:1','SYSTEMD_EXEC_PID': '2522','WINDOWPATH': '2','HOME': '/home/paul-kane','USERNAME': 'paul-kane','LANG': 'en_US.UTF-8','LS_COLORS': 'rs=0:di=01;34:ln=01;36:mh=00:pi=40;33:so=01;35:do=01;35:bd=40;33;01:cd=40;33;01:or=40;31;01:mi=00:su=37;41:sg=30;43:ca=00:tw=30;42:ow=34;42:st=37;44:ex=01;32:*.tar=01;31:*.tgz=01;31:*.arc=01;31:*.arj=01;31:*.taz=01;31:*.lha=01;31:*.lz4=01;31:*.lzh=01;31:*.lzma=01;31:*.tlz=01;31:*.txz=01;31:*.tzo=01;31:*.t7z=01;31:*.zip=01;31:*.z=01;31:*.dz=01;31:*.gz=01;31:*.lrz=01;31:*.lz=01;31:*.lzo=01;31:*.xz=01;31:*.zst=01;31:*.tzst=01;31:*.bz2=01;31:*.bz=01;31:*.tbz=01;31:*.tbz2=01;31:*.tz=01;31:*.deb=01;31:*.rpm=01;31:*.jar=01;31:*.war=01;31:*.ear=01;31:*.sar=01;31:*.rar=01;31:*.alz=01;31:*.ace=01;31:*.zoo=01;31:*.cpio=01;31:*.7z=01;31:*.rz=01;31:*.cab=01;31:*.wim=01;31:*.swm=01;31:*.dwm=01;31:*.esd=01;31:*.avif=01;35:*.jpg=01;35:*.jpeg=01;35:*.mjpg=01;35:*.mjpeg=01;35:*.gif=01;35:*.bmp=01;35:*.pbm=01;35:*.pgm=01;35:*.ppm=01;35:*.tga=01;35:*.xbm=01;35:*.xpm=01;35:*.tif=01;35:*.tiff=01;35:*.png=01;35:*.svg=01;35:*.svgz=01;35:*.mng=01;35:*.pcx=01;35:*.mov=01;35:*.mpg=01;35:*.mpeg=01;35:*.m2v=01;35:*.mkv=01;35:*.webm=01;35:*.webp=01;35:*.ogm=01;35:*.mp4=01;35:*.m4v=01;35:*.mp4v=01;35:*.vob=01;35:*.qt=01;35:*.nuv=01;35:*.wmv=01;35:*.asf=01;35:*.rm=01;35:*.rmvb=01;35:*.flc=01;35:*.avi=01;35:*.fli=01;35:*.flv=01;35:*.gl=01;35:*.dl=01;35:*.xcf=01;35:*.xwd=01;35:*.yuv=01;35:*.cgm=01;35:*.emf=01;35:*.ogv=01;35:*.ogx=01;35:*.aac=00;36:*.au=00;36:*.flac=00;36:*.m4a=00;36:*.mid=00;36:*.midi=00;36:*.mka=00;36:*.mp3=00;36:*.mpc=00;36:*.ogg=00;36:*.ra=00;36:*.wav=00;36:*.oga=00;36:*.opus=00;36:*.spx=00;36:*.xspf=00;36:*~=00;90:*#=00;90:*.bak=00;90:*.crdownload=00;90:*.dpkg-dist=00;90:*.dpkg-new=00;90:*.dpkg-old=00;90:*.dpkg-tmp=00;90:*.old=00;90:*.orig=00;90:*.part=00;90:*.rej=00;90:*.rpmnew=00;90:*.rpmorig=00;90:*.rpmsave=00;90:*.swp=00;90:*.tmp=00;90:*.ucf-dist=00;90:*.ucf-new=00;90:*.ucf-old=00;90:','XDG_CURRENT_DESKTOP': 'ubuntu:GNOME','MEMORY_PRESSURE_WATCH': '/sys/fs/cgroup/user.slice/user-1000.slice/user@1000.service/app.slice/app-gnome\\x2dsession\\x2dmanager.slice/gnome-session-manager@ubuntu.service/memory.pressure','VTE_VERSION': '7600','GNOME_TERMINAL_SCREEN': '/org/gnome/Terminal/screen/85f068a5_e9bf_491a_aa19_23900fb28a81','NVM_DIR': '/home/paul-kane/.nvm','LESSCLOSE': '/usr/bin/lesspipe %s %s','XDG_SESSION_CLASS': 'user','LESSOPEN': '| /usr/bin/lesspipe %s','USER': 'paul-kane','GNOME_TERMINAL_SERVICE': ':1.472','DISPLAY': ':1','SHLVL': '2','NVM_CD_FLAGS': '','GSM_SKIP_SSH_AGENT_WORKAROUND': 'true','PAGER': 'cat','QT_IM_MODULE': 'ibus','DBUS_STARTER_ADDRESS': 'unix:path=/run/user/1000/bus,guid=daf02d337b8040bf29b16ce469b9b237','XDG_RUNTIME_DIR': '/run/user/1000','GEMINI_CLI': '1','DEBUGINFOD_URLS': 'https://debuginfod.ubuntu.com ','BUN_INSTALL': '/home/paul-kane/.bun','GEMINI_CLI_NO_RELAUNCH': 'true','XDG_DATA_DIRS': '/usr/share/ubuntu:/usr/share/gnome:/home/paul-kane/.local/share/flatpak/exports/share:/var/lib/flatpak/exports/share:/usr/local/share/:/usr/share/','PATH': '/home/paul-kane/.bun/bin:/home/paul-kane/.nvm/versions/node/v20.20.0/bin:/home/paul-kane/.local/bin:/var/www/drupal/vendor/bin:/home/paul-kane/.cargo/bin:/home/paul-kane/.local/bin:/home/paul-kane/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games:/usr/local/games:/snap/bin','GDMSESSION': 'ubuntu','DBUS_SESSION_BUS_ADDRESS': 'unix:path=/run/user/1000/bus,guid=daf02d337b8040bf29b16ce469b9b237','NVM_BIN': '/home/paul-kane/.nvm/versions/node/v20.20.0/bin','OLDPWD': '/media/paul-kane/SteamGames/Games','_': '/usr/bin/python3','PYTHONHASHSEED': '0','NUITKA_PYTHON_EXE_PATH': '/usr/bin/python3','NUITKA_PACKAGE_DIR': '/home/paul-kane/.local/lib/python3.12/site-packages/nuitka','_NUITKA_ONEFILE_CHILD_GRACE_TIME_INT': '5000','_NUITKA_BUILD_DEFINITIONS_CATALOG': '_NUITKA_ONEFILE_CHILD_GRACE_TIME_INT,_NUITKA_BUILD_DEFINITIONS_CATALOG','NUITKA_QUIET': '0'},
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 9** (Hardcoded Username (paul-kane)):
  ```
  env={'SHELL': '/bin/bash','SESSION_MANAGER': 'local/HAL9000:@/tmp/.ICE-unix/2522,unix/HAL9000:/tmp/.ICE-unix/2522','QT_ACCESSIBILITY': '1','XDG_CONFIG_DIRS': '/etc/xdg/xdg-ubuntu:/etc/xdg','NVM_INC': '/home/paul-kane/.nvm/versions/node/v20.20.0/include/node','XDG_MENU_PREFIX': 'gnome-','GNOME_DESKTOP_SESSION_ID': 'this-is-deprecated','GNOME_SHELL_SESSION_MODE': 'ubuntu','MEMORY_PRESSURE_WRITE': 'c29tZSAyMDAwMDAgMjAwMDAwMAA=','XMODIFIERS': '@im=ibus','DESKTOP_SESSION': 'ubuntu','GTK_MODULES': 'gail:atk-bridge','DBUS_STARTER_BUS_TYPE': 'session','PWD': '/home/paul-kane/projects/rome-core','XDG_SESSION_DESKTOP': 'ubuntu','LOGNAME': 'paul-kane','XDG_SESSION_TYPE': 'x11','GPG_AGENT_INFO': '/run/user/1000/gnupg/S.gpg-agent:0:1','SYSTEMD_EXEC_PID': '2522','WINDOWPATH': '2','HOME': '/home/paul-kane','USERNAME': 'paul-kane','LANG': 'en_US.UTF-8','LS_COLORS': 'rs=0:di=01;34:ln=01;36:mh=00:pi=40;33:so=01;35:do=01;35:bd=40;33;01:cd=40;33;01:or=40;31;01:mi=00:su=37;41:sg=30;43:ca=00:tw=30;42:ow=34;42:st=37;44:ex=01;32:*.tar=01;31:*.tgz=01;31:*.arc=01;31:*.arj=01;31:*.taz=01;31:*.lha=01;31:*.lz4=01;31:*.lzh=01;31:*.lzma=01;31:*.tlz=01;31:*.txz=01;31:*.tzo=01;31:*.t7z=01;31:*.zip=01;31:*.z=01;31:*.dz=01;31:*.gz=01;31:*.lrz=01;31:*.lz=01;31:*.lzo=01;31:*.xz=01;31:*.zst=01;31:*.tzst=01;31:*.bz2=01;31:*.bz=01;31:*.tbz=01;31:*.tbz2=01;31:*.tz=01;31:*.deb=01;31:*.rpm=01;31:*.jar=01;31:*.war=01;31:*.ear=01;31:*.sar=01;31:*.rar=01;31:*.alz=01;31:*.ace=01;31:*.zoo=01;31:*.cpio=01;31:*.7z=01;31:*.rz=01;31:*.cab=01;31:*.wim=01;31:*.swm=01;31:*.dwm=01;31:*.esd=01;31:*.avif=01;35:*.jpg=01;35:*.jpeg=01;35:*.mjpg=01;35:*.mjpeg=01;35:*.gif=01;35:*.bmp=01;35:*.pbm=01;35:*.pgm=01;35:*.ppm=01;35:*.tga=01;35:*.xbm=01;35:*.xpm=01;35:*.tif=01;35:*.tiff=01;35:*.png=01;35:*.svg=01;35:*.svgz=01;35:*.mng=01;35:*.pcx=01;35:*.mov=01;35:*.mpg=01;35:*.mpeg=01;35:*.m2v=01;35:*.mkv=01;35:*.webm=01;35:*.webp=01;35:*.ogm=01;35:*.mp4=01;35:*.m4v=01;35:*.mp4v=01;35:*.vob=01;35:*.qt=01;35:*.nuv=01;35:*.wmv=01;35:*.asf=01;35:*.rm=01;35:*.rmvb=01;35:*.flc=01;35:*.avi=01;35:*.fli=01;35:*.flv=01;35:*.gl=01;35:*.dl=01;35:*.xcf=01;35:*.xwd=01;35:*.yuv=01;35:*.cgm=01;35:*.emf=01;35:*.ogv=01;35:*.ogx=01;35:*.aac=00;36:*.au=00;36:*.flac=00;36:*.m4a=00;36:*.mid=00;36:*.midi=00;36:*.mka=00;36:*.mp3=00;36:*.mpc=00;36:*.ogg=00;36:*.ra=00;36:*.wav=00;36:*.oga=00;36:*.opus=00;36:*.spx=00;36:*.xspf=00;36:*~=00;90:*#=00;90:*.bak=00;90:*.crdownload=00;90:*.dpkg-dist=00;90:*.dpkg-new=00;90:*.dpkg-old=00;90:*.dpkg-tmp=00;90:*.old=00;90:*.orig=00;90:*.part=00;90:*.rej=00;90:*.rpmnew=00;90:*.rpmorig=00;90:*.rpmsave=00;90:*.swp=00;90:*.tmp=00;90:*.ucf-dist=00;90:*.ucf-new=00;90:*.ucf-old=00;90:','XDG_CURRENT_DESKTOP': 'ubuntu:GNOME','MEMORY_PRESSURE_WATCH': '/sys/fs/cgroup/user.slice/user-1000.slice/user@1000.service/app.slice/app-gnome\\x2dsession\\x2dmanager.slice/gnome-session-manager@ubuntu.service/memory.pressure','VTE_VERSION': '7600','GNOME_TERMINAL_SCREEN': '/org/gnome/Terminal/screen/85f068a5_e9bf_491a_aa19_23900fb28a81','NVM_DIR': '/home/paul-kane/.nvm','LESSCLOSE': '/usr/bin/lesspipe %s %s','XDG_SESSION_CLASS': 'user','LESSOPEN': '| /usr/bin/lesspipe %s','USER': 'paul-kane','GNOME_TERMINAL_SERVICE': ':1.472','DISPLAY': ':1','SHLVL': '2','NVM_CD_FLAGS': '','GSM_SKIP_SSH_AGENT_WORKAROUND': 'true','PAGER': 'cat','QT_IM_MODULE': 'ibus','DBUS_STARTER_ADDRESS': 'unix:path=/run/user/1000/bus,guid=daf02d337b8040bf29b16ce469b9b237','XDG_RUNTIME_DIR': '/run/user/1000','GEMINI_CLI': '1','DEBUGINFOD_URLS': 'https://debuginfod.ubuntu.com ','BUN_INSTALL': '/home/paul-kane/.bun','GEMINI_CLI_NO_RELAUNCH': 'true','XDG_DATA_DIRS': '/usr/share/ubuntu:/usr/share/gnome:/home/paul-kane/.local/share/flatpak/exports/share:/var/lib/flatpak/exports/share:/usr/local/share/:/usr/share/','PATH': '/home/paul-kane/.bun/bin:/home/paul-kane/.nvm/versions/node/v20.20.0/bin:/home/paul-kane/.local/bin:/var/www/drupal/vendor/bin:/home/paul-kane/.cargo/bin:/home/paul-kane/.local/bin:/home/paul-kane/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games:/usr/local/games:/snap/bin','GDMSESSION': 'ubuntu','DBUS_SESSION_BUS_ADDRESS': 'unix:path=/run/user/1000/bus,guid=daf02d337b8040bf29b16ce469b9b237','NVM_BIN': '/home/paul-kane/.nvm/versions/node/v20.20.0/bin','OLDPWD': '/media/paul-kane/SteamGames/Games','_': '/usr/bin/python3','PYTHONHASHSEED': '0','NUITKA_PYTHON_EXE_PATH': '/usr/bin/python3','NUITKA_PACKAGE_DIR': '/home/paul-kane/.local/lib/python3.12/site-packages/nuitka','_NUITKA_ONEFILE_CHILD_GRACE_TIME_INT': '5000','_NUITKA_BUILD_DEFINITIONS_CATALOG': '_NUITKA_ONEFILE_CHILD_GRACE_TIME_INT,_NUITKA_BUILD_DEFINITIONS_CATALOG','NUITKA_QUIET': '0'},
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

- **Line 9** (Hardcoded Absolute Path (/opt, /etc, etc.)):
  ```
  env={'SHELL': '/bin/bash','SESSION_MANAGER': 'local/HAL9000:@/tmp/.ICE-unix/2522,unix/HAL9000:/tmp/.ICE-unix/2522','QT_ACCESSIBILITY': '1','XDG_CONFIG_DIRS': '/etc/xdg/xdg-ubuntu:/etc/xdg','NVM_INC': '/home/paul-kane/.nvm/versions/node/v20.20.0/include/node','XDG_MENU_PREFIX': 'gnome-','GNOME_DESKTOP_SESSION_ID': 'this-is-deprecated','GNOME_SHELL_SESSION_MODE': 'ubuntu','MEMORY_PRESSURE_WRITE': 'c29tZSAyMDAwMDAgMjAwMDAwMAA=','XMODIFIERS': '@im=ibus','DESKTOP_SESSION': 'ubuntu','GTK_MODULES': 'gail:atk-bridge','DBUS_STARTER_BUS_TYPE': 'session','PWD': '/home/paul-kane/projects/rome-core','XDG_SESSION_DESKTOP': 'ubuntu','LOGNAME': 'paul-kane','XDG_SESSION_TYPE': 'x11','GPG_AGENT_INFO': '/run/user/1000/gnupg/S.gpg-agent:0:1','SYSTEMD_EXEC_PID': '2522','WINDOWPATH': '2','HOME': '/home/paul-kane','USERNAME': 'paul-kane','LANG': 'en_US.UTF-8','LS_COLORS': 'rs=0:di=01;34:ln=01;36:mh=00:pi=40;33:so=01;35:do=01;35:bd=40;33;01:cd=40;33;01:or=40;31;01:mi=00:su=37;41:sg=30;43:ca=00:tw=30;42:ow=34;42:st=37;44:ex=01;32:*.tar=01;31:*.tgz=01;31:*.arc=01;31:*.arj=01;31:*.taz=01;31:*.lha=01;31:*.lz4=01;31:*.lzh=01;31:*.lzma=01;31:*.tlz=01;31:*.txz=01;31:*.tzo=01;31:*.t7z=01;31:*.zip=01;31:*.z=01;31:*.dz=01;31:*.gz=01;31:*.lrz=01;31:*.lz=01;31:*.lzo=01;31:*.xz=01;31:*.zst=01;31:*.tzst=01;31:*.bz2=01;31:*.bz=01;31:*.tbz=01;31:*.tbz2=01;31:*.tz=01;31:*.deb=01;31:*.rpm=01;31:*.jar=01;31:*.war=01;31:*.ear=01;31:*.sar=01;31:*.rar=01;31:*.alz=01;31:*.ace=01;31:*.zoo=01;31:*.cpio=01;31:*.7z=01;31:*.rz=01;31:*.cab=01;31:*.wim=01;31:*.swm=01;31:*.dwm=01;31:*.esd=01;31:*.avif=01;35:*.jpg=01;35:*.jpeg=01;35:*.mjpg=01;35:*.mjpeg=01;35:*.gif=01;35:*.bmp=01;35:*.pbm=01;35:*.pgm=01;35:*.ppm=01;35:*.tga=01;35:*.xbm=01;35:*.xpm=01;35:*.tif=01;35:*.tiff=01;35:*.png=01;35:*.svg=01;35:*.svgz=01;35:*.mng=01;35:*.pcx=01;35:*.mov=01;35:*.mpg=01;35:*.mpeg=01;35:*.m2v=01;35:*.mkv=01;35:*.webm=01;35:*.webp=01;35:*.ogm=01;35:*.mp4=01;35:*.m4v=01;35:*.mp4v=01;35:*.vob=01;35:*.qt=01;35:*.nuv=01;35:*.wmv=01;35:*.asf=01;35:*.rm=01;35:*.rmvb=01;35:*.flc=01;35:*.avi=01;35:*.fli=01;35:*.flv=01;35:*.gl=01;35:*.dl=01;35:*.xcf=01;35:*.xwd=01;35:*.yuv=01;35:*.cgm=01;35:*.emf=01;35:*.ogv=01;35:*.ogx=01;35:*.aac=00;36:*.au=00;36:*.flac=00;36:*.m4a=00;36:*.mid=00;36:*.midi=00;36:*.mka=00;36:*.mp3=00;36:*.mpc=00;36:*.ogg=00;36:*.ra=00;36:*.wav=00;36:*.oga=00;36:*.opus=00;36:*.spx=00;36:*.xspf=00;36:*~=00;90:*#=00;90:*.bak=00;90:*.crdownload=00;90:*.dpkg-dist=00;90:*.dpkg-new=00;90:*.dpkg-old=00;90:*.dpkg-tmp=00;90:*.old=00;90:*.orig=00;90:*.part=00;90:*.rej=00;90:*.rpmnew=00;90:*.rpmorig=00;90:*.rpmsave=00;90:*.swp=00;90:*.tmp=00;90:*.ucf-dist=00;90:*.ucf-new=00;90:*.ucf-old=00;90:','XDG_CURRENT_DESKTOP': 'ubuntu:GNOME','MEMORY_PRESSURE_WATCH': '/sys/fs/cgroup/user.slice/user-1000.slice/user@1000.service/app.slice/app-gnome\\x2dsession\\x2dmanager.slice/gnome-session-manager@ubuntu.service/memory.pressure','VTE_VERSION': '7600','GNOME_TERMINAL_SCREEN': '/org/gnome/Terminal/screen/85f068a5_e9bf_491a_aa19_23900fb28a81','NVM_DIR': '/home/paul-kane/.nvm','LESSCLOSE': '/usr/bin/lesspipe %s %s','XDG_SESSION_CLASS': 'user','LESSOPEN': '| /usr/bin/lesspipe %s','USER': 'paul-kane','GNOME_TERMINAL_SERVICE': ':1.472','DISPLAY': ':1','SHLVL': '2','NVM_CD_FLAGS': '','GSM_SKIP_SSH_AGENT_WORKAROUND': 'true','PAGER': 'cat','QT_IM_MODULE': 'ibus','DBUS_STARTER_ADDRESS': 'unix:path=/run/user/1000/bus,guid=daf02d337b8040bf29b16ce469b9b237','XDG_RUNTIME_DIR': '/run/user/1000','GEMINI_CLI': '1','DEBUGINFOD_URLS': 'https://debuginfod.ubuntu.com ','BUN_INSTALL': '/home/paul-kane/.bun','GEMINI_CLI_NO_RELAUNCH': 'true','XDG_DATA_DIRS': '/usr/share/ubuntu:/usr/share/gnome:/home/paul-kane/.local/share/flatpak/exports/share:/var/lib/flatpak/exports/share:/usr/local/share/:/usr/share/','PATH': '/home/paul-kane/.bun/bin:/home/paul-kane/.nvm/versions/node/v20.20.0/bin:/home/paul-kane/.local/bin:/var/www/drupal/vendor/bin:/home/paul-kane/.cargo/bin:/home/paul-kane/.local/bin:/home/paul-kane/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games:/usr/local/games:/snap/bin','GDMSESSION': 'ubuntu','DBUS_SESSION_BUS_ADDRESS': 'unix:path=/run/user/1000/bus,guid=daf02d337b8040bf29b16ce469b9b237','NVM_BIN': '/home/paul-kane/.nvm/versions/node/v20.20.0/bin','OLDPWD': '/media/paul-kane/SteamGames/Games','_': '/usr/bin/python3','PYTHONHASHSEED': '0','NUITKA_PYTHON_EXE_PATH': '/usr/bin/python3','NUITKA_PACKAGE_DIR': '/home/paul-kane/.local/lib/python3.12/site-packages/nuitka','_NUITKA_ONEFILE_CHILD_GRACE_TIME_INT': '5000','_NUITKA_BUILD_DEFINITIONS_CATALOG': '_NUITKA_ONEFILE_CHILD_GRACE_TIME_INT,_NUITKA_BUILD_DEFINITIONS_CATALOG','NUITKA_QUIET': '0'},
  ```
  *Recommendation:* Replace with environment variable (e.g., `os.environ.get(...)`) or configuration file value.

