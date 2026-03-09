# ROME Headless Orchestrator Client

Run ROME tasks using a cheap model (Haiku/Flash) without Claude Code or Opus.

## Usage

```bash
python3 orchestrator.py <task_file>
```

Or via stdin:

```bash
echo "fix the bug in main.py" | python3 orchestrator.py -
```

## Setup

1. Start the ROME daemon:
```bash
python3 dictator/daemon.py
```

2. Set API key:
```bash
export ANTHROPIC_API_KEY="sk-ant-..."  # For Haiku
# OR
export GEMINI_API_KEY="..."  # For Gemini Flash
```

3. Run orchestrator:
```bash
python3 client/orchestrator.py my_task.txt
```

## Output

The orchestrator streams events as JSONL (one JSON object per line):

```json
{"type": "dispatch_start", "task_id": "...", "capability": "GEMINI"}
{"type": "progress", "task_id": "...", "percent": 50, "message": "..."}
{"type": "complete", "task_id": "...", "status": "SUCCESS"}
{"type": "error", "message": "Connection failed"}
```

## How It Works

1. **Orchestration**: Task description is sent to Haiku/Flash, which breaks it into subtasks and decides which capability (SAFE_SHELL, GEMINI, CODEX, etc.) to use
2. **Dispatch**: Subtasks are dispatched via WS to the ROME daemon
3. **Progress**: Listens to WS events and streams them as JSONL
4. **Fire-and-Forget**: Long tasks use `fire_and_forget=true` to prevent blocking

## Example Task File

```
Analyze /home/paul-kane/projects/rome-core/dictator/tools_legion.py
and identify any potential memory leaks. Then run the test suite
to verify the fixes work.
```

## Cost Breakdown

- **Haiku orchestrator**: ~$0.0001-0.0005 per task (deciding how to break it down)
- **Worker tasks**: Pay only for the actual work (GEMINI, CODEX, SAFE_SHELL)
- **vs. Opus in Claude Code**: Opus costs 15x more just to sit idle between task completions

This is the "make the throne cheap" endgame — decouple the orchestrator from expensive models.
