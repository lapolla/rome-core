# Manifesto: Operation Monty Python
**Role:** Imperial Python Developer (ROME Legionary)
**Objective:** Rewrite the Node.js Dictator in pure Python.

## 1. Primary Objective
Create `dictator/dictator.py`, a Python-based MCP server that replicates all tools currently in `dictator/index.mjs`.

## 2. Target Toolset
You MUST port the following functional areas:
*   **Core ROME:** `execute_legion` (dispatching to legion_wrapper.py).
*   **System Ops:** `shell_exec`, `list_directory`, `read_anywhere`, `write_anywhere`.
*   **Version Control:** `git_status`, `git_commit`, `git_push`, `git_diff`.
*   **Entertainment:** `music_play`, `music_stop`, `music_status` (using subprocess for mpv/yt-dlp).
*   **Skyrim Intelligence:** `skyrim_read_state`, `skyrim_console`, `skyrim_face_actor`, `skyrim_follow_actor`.
*   **Desktop Automation:** `desktop_screenshot`, `desktop_click`, `desktop_type_text`, `desktop_press_key`.

## 3. Implementation Requirements
*   **Protocol:** Use the `mcp` Python library if available, or implement a clean stdio JSON parser/dispatcher.
*   **Structure:** Class-based architecture for tool management.
*   **Dependencies:** List all required Python packages (e.g., `requests`, `numpy`, `xdotool` wrapper).
*   **Root Authority:** Maintain the same paths and environment variables as the original Dictator.

## 4. Constraint
*   **NO NODE.JS:** The output must be 100% Python.
*   **Full Capability:** Do not leave any tool behind.

---
**"And now for something completely different: A Dictator that doesn't need npm."**
🕶️🗡️🏛️🔥🌑 Gemini CLI | Feb 22, 2026
