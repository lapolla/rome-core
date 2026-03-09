● Headless Orchestrator — How It Works                                                                                                                                                        
                                                                                                                                                                                            
  Architecture                                                                                                                                                                                
                                                                                                                                                                                              
  ┌─────────────────────────────────────────────────────────────┐                                                                                                                             
  │ User's Task (file or stdin)                                 │                                                                                                                             
  └────────────────────┬────────────────────────────────────────┘                                                                                                                             
                       │                                                                                                                                                                      
                       ▼                                                                                                                                                                      
  ┌─────────────────────────────────────────────────────────────┐                                                                                                                             
  │ Haiku/Flash Model (via Anthropic API or Gemini API)         │                                                                                                                             
  │ Role: Orchestrator — decides HOW to solve the problem       │                                                                                                                             
  │                                                             │                                                                                                                             
  │ Input: "Fix the bug in main.py and run tests"               │
  │ Output: JSON array of subtasks with capabilities            │
  │                                                             │
  │ Example:                                                    │
  │ [                                                           │
  │   {"capability": "SAFE_SHELL", "prompt": "grep for bug"},   │
  │   {"capability": "GEMINI", "prompt": "analyze and fix"},    │
  │   {"capability": "SAFE_SHELL", "prompt": "npm test", ...}   │
  │ ]                                                           │
  └────────────────────┬────────────────────────────────────────┘
                       │
                       ▼
  ┌─────────────────────────────────────────────────────────────┐
  │ ROME Daemon (localhost:8741)                                │
  │ WebSocket Server — runs the actual work                     │
  │                                                             │
  │ Each subtask dispatched via WS:                             │
  │ {"type": "dispatch", "payload": {                           │
  │   "task_id": "abc123",                                      │
  │   "capability": "GEMINI",                                   │
  │   "prompt": "fix the bug",                                  │
  │   "fire_and_forget": false                                  │
  │ }}                                                          │
  │                                                             │
  │ Daemon runs the legion task, streams back events:           │
  │ - dispatch_start                                            │
  │ - progress (0%, 50%, 100%)                                  │
  │ - complete (SUCCESS/FAILED)                                 │
  └────────────────────┬────────────────────────────────────────┘
                       │
                       ▼
  ┌─────────────────────────────────────────────────────────────┐
  │ orchestrator.py (CLI)                                       │
  │ Listens to WS events, streams JSONL to stdout               │
  │                                                             │
  │ {"type": "dispatch_start", "task_id": "abc123", ...}        │
  │ {"type": "progress", "percent": 50, "message": "..."}       │
  │ {"type": "complete", "status": "SUCCESS", "report": "..."}  │
  └─────────────────────────────────────────────────────────────┘

  Flow — Step by Step

  1. Initialization

  # User starts ROME daemon
  python3 dictator/daemon.py

  # User runs orchestrator with a task
  echo "Analyze logs and find errors" | python3 client/orchestrator.py -

  2. Task Breakdown (Haiku/Flash)

  The orchestrator.py sends the task to Haiku via Anthropic API:

  # System prompt tells Haiku it's an orchestrator
  SYSTEM_PROMPT = """
  You are a headless orchestrator. Break the task into subtasks.
  Available capabilities: GEMINI, CODEX, SAFE_SHELL, OPENCODE.
  Output ONLY a JSON array of subtasks.
  """

  # User's task
  task_description = "Analyze logs and find errors"

  # Haiku decides:
  subtasks = [
    {"capability": "SAFE_SHELL", "prompt": "find /var/log -name '*.log' -mtime -1", "fire_and_forget": false},
    {"capability": "GEMINI", "prompt": "Analyze these logs and summarize errors", "fire_and_forget": false}
  ]

  Cost: ~$0.0002 (Haiku is cheap — it just decides the strategy, doesn't do the work)

  3. Dispatch to ROME Daemon

  orchestrator.py connects to the daemon via WS and sends each subtask:

  async with websockets.connect("ws://localhost:8741/ws") as ws:
      for subtask in subtasks:
          task_id = str(uuid.uuid4())
          cmd = {
              "type": "dispatch",
              "payload": {
                  "task_id": task_id,
                  "capability": subtask["capability"],
                  "prompt": subtask["prompt"],
                  "fire_and_forget": subtask.get("fire_and_forget", False)
              }
          }
          await ws.send(json.dumps(cmd))

          # Wait for this subtask to complete before next one
          # (unless fire_and_forget=True, then run in parallel)

  4. ROME Daemon Executes

  The daemon receives the dispatch command and:

  1. Creates a legion task
  2. Spawns the appropriate worker (GEMINI, CODEX, SAFE_SHELL, etc.)
  3. Streams back WS events:

  {"type": "dispatch_start", "task_id": "abc123", "capability": "GEMINI"}
  {"type": "progress", "task_id": "abc123", "percent": 25, "message": "Reading logs..."}
  {"type": "progress", "task_id": "abc123", "percent": 75, "message": "Analyzing errors..."}
  {"type": "complete", "task_id": "abc123", "status": "SUCCESS", "report": "/path/to/report.txt"}

  5. Output Streaming

  orchestrator.py listens to WS events and streams them to stdout as JSONL:

  {"type": "dispatch_start", "task_id": "abc123", "capability": "GEMINI"}
  {"type": "progress", "task_id": "abc123", "percent": 75, "message": "Analyzing errors..."}
  {"type": "complete", "task_id": "abc123", "status": "SUCCESS"}

  The user (or another system) can:
  - Pipe to jq to filter events
  - Parse JSONL for monitoring dashboards
  - Check exit code for automation (0 = all SUCCESS, 1 = any FAILED)

  ---
  Why This Solves "Make the Throne Cheap"

  ┌─────────────────┬─────────────────────────┬───────────────────────────┬───────────────────────────────┐
  │    Component    │          Model          │       Cost Per Task       │             Role              │
  ├─────────────────┼─────────────────────────┼───────────────────────────┼───────────────────────────────┤
  │ Orchestrator    │ Haiku                   │ $0.0002                   │ Decides strategy (1 API call) │
  ├─────────────────┼─────────────────────────┼───────────────────────────┼───────────────────────────────┤
  │ Workers         │ GEMINI/CODEX/SAFE_SHELL │ $0.001-0.10               │ Do the actual work            │
  ├─────────────────┼─────────────────────────┼───────────────────────────┼───────────────────────────────┤
  │ vs. Claude Code │ Opus                    │ $0.015 (idle) + work cost │ Expensive even when waiting   │
  └─────────────────┴─────────────────────────┴───────────────────────────┴───────────────────────────────┘

  Example: 10 tasks per session
  - Headless: $0.002 (orchestrator) + $0.050 (workers) = $0.052 total
  - Claude Code: $0.15 (Opus idle) + $0.050 (workers) = $0.20 total (3.8x more expensive)

  The breakthrough: Opus is no longer the bottleneck. You can now:
  - Run ROME from any CLI (no Claude Code required)
  - Use Haiku to orchestrate (50x cheaper than Opus)
  - Scale to 100 tasks without expensive model sitting idle
  - Chain multiple cheap models (Haiku → GEMINI → SAFE_SHELL)

  ---
  Usage Example

  Task file (my_task.txt):
  Review the changes in dictator/tools_legion.py since last commit.
  Identify any bugs or security issues. If found, create a patch.

  Run:
  python3 client/orchestrator.py my_task.txt

  Haiku breaks it down:
  [
    {"capability": "SAFE_SHELL", "prompt": "git diff dictator/tools_legion.py", "fire_and_forget": false},
    {"capability": "GEMINI", "prompt": "Review the diff for bugs/security issues", "fire_and_forget": false},
    {"capability": "CODEX", "prompt": "If issues found, create a patch", "fire_and_forget": false}
  ]

  Output:
  {"type": "dispatch_start", "task_id": "task1", "capability": "SAFE_SHELL"}
  {"type": "progress", "task_id": "task1", "percent": 100}
  {"type": "complete", "task_id": "task1", "status": "SUCCESS"}
  {"type": "dispatch_start", "task_id": "task2", "capability": "GEMINI"}
  ...
  {"type": "complete", "task_id": "task3", "status": "SUCCESS", "report": "/path/to/patch.diff"}

  Exit code: 0 (all tasks succeeded)
