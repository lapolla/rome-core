#!/bin/bash
# ROME V4: START PERSISTENT WORKERS
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROME_ROOT="$SCRIPT_DIR"
WS_URL="ws://127.0.0.1:8741/ws"
WS_TOKEN="ROME_V4_SECURE_TOKEN"

# --- Capability Config (from arsenal) ---
GEMINI_CLI="$HOME/projects/gemini-cli/bundle/gemini.js"
GEMINI_ARGS=("$GEMINI_CLI" "--sandbox" "false" "--include-directories" "$ROME_ROOT" "--yolo" "--output-format" "json" "-m" "gemini-3.1-pro-preview" "-p")

CLAUDE_ARGS=("claude" "--dangerously-skip-permissions" "--output-format" "json" "-p")

# --- Launch Helpers ---
start_worker() {
    local cap=$1
    shift
    local args=("$@")
    echo "Starting persistent worker for $cap..."
    export PYTHONPATH="$ROME_ROOT"
    nohup python3 "$ROME_ROOT/legions/legion_wrapper.py" \
        --mode worker \
        --capabilities "$cap" \
        --ws-url "$WS_URL" \
        --ws-token "$WS_TOKEN" \
        "${args[@]}" > "/tmp/rome-worker-$cap.log" 2>&1 &
}

# --- Main ---
pkill -f 'legion_wrapper.py --mode worker' 2>/dev/null
pkill -f 'src/index.ts rome-worker' 2>/dev/null

# Start GEMINI
start_worker "GEMINI" "${GEMINI_ARGS[@]}"

# Start SAFE_SHELL
start_worker "SAFE_SHELL" "python3" "$ROME_ROOT/legions/shell_executor.py"

# Start MISTRAL
start_worker "MISTRAL" "python3" "-m" "vibe.cli.entrypoint" "env:PYTHONPATH=/home/paul-kane/projects/mistral-cli" "--agent" "auto-approve" "--output" "streaming" "-p"

# Start CLAUDE
start_worker "CLAUDE" "${CLAUDE_ARGS[@]}"

echo "ROME workers started (GEMINI, CLAUDE, MISTRAL, SAFE_SHELL)."
