# ROME Dashboard — Feature Roadmap

## HIGH VALUE (saves real tokens/time)
- [ ] 1. **Headless orchestrator mode** — External client (Haiku/Flash) orchestrates via WS dispatch command. The "make the throne cheap" endgame.
- [ ] 2. **Cost on dashboard** — Show cumulative session cost. rome_costs data exists, just needs a cost_update event listener + display widget.
- [ ] 3. **Failed task retry button** — "Retry" button on FAILED task cards, sends WS dispatch command to re-run the task.

## MEDIUM VALUE (operational visibility)
- [ ] 4. **Campaign fan-out view** — Group child tasks under their parent campaign. Show campaign progress as aggregate.
- [ ] 5. **Task output viewer** — Click task card to view report file contents inline via WS read_report command.
- [ ] 6. **Historical view / persistence** — Hydrate TaskRegistry from rome.jsonl on startup so history survives restarts.

## LOW VALUE (polish)
- [ ] 7. **Filter/search tasks** by status, capability, date
- [ ] 8. **Mobile responsive** layout
- [ ] 9. **Sound/notification** on task failure

## BUGS (blocking)
- [ ] **GEMINI empty report bug (AGAIN)** — report file gets overwritten with previous task's OK string. output_path relies on agent writing (impossible for GEMINI CLI). Fix: copy report file to output_path after completion.
- [x] **Codex rate limited** — quota exhausted until Mar 10 2:44 PM (not a code bug)
