/**
 * ROME Decomposer (v1) — pure planning layer.
 * Input: Task → Output: Plan (DAG of steps).
 * DOES NOT spawn, route, execute, or retry. Pure transform.
 */
import type { DecompTask, DecompStep, Plan } from './rome_types.js';

const SYSTEM = `You are ROME Decomposer v1. Transform a task into an executable DAG plan.
Output ONLY valid JSON. No explanation, no markdown fences.

Schema:
{
  "taskId": "<string>",
  "steps": [{
    "id": "<string>",
    "dependsOn": ["<step-id>"],
    "payload": {
      "role": "GEMINI|CLAUDE|GEMMA|MISTRAL|SAFE_SHELL|NATIVE_SHELL",
      "mode": "native_ws|cli|fallback",
      "input": "<complete self-contained prompt>"
    }
  }]
}

Role selection:
- SAFE_SHELL  → bash, git, file ops, build commands
- NATIVE_SHELL → daemon-native sub-ms shell
- GEMINI      → code analysis, search, file edits
- GEMMA       → quick local inference, simple transforms
- CLAUDE      → complex reasoning, architecture, long context
- MISTRAL     → secondary LLM, creative, summarisation

Mode selection:
- native_ws  → persistent registered worker exists
- cli        → CLI subprocess per task
- fallback   → daemon in-process (no worker registered)

Hard rules:
- dependsOn must reference earlier step ids only
- input must be complete and self-contained (no references to other steps)
- single-step tasks are valid plans`;

function buildPrompt(task: DecompTask): string {
  return `${SYSTEM}\n\nTASK:\nid: ${task.id}\nprompt: ${task.prompt}${task.context ? `\ncontext: ${JSON.stringify(task.context)}` : ''}`;
}

function extract(raw: string): Plan {
  const m = raw.match(/\{[\s\S]*\}/);
  if (!m) throw new Error('Decomposer: no JSON in LLM response');
  const plan: Plan = JSON.parse(m[0]);
  if (!plan.taskId || !Array.isArray(plan.steps) || plan.steps.length === 0) {
    throw new Error('Decomposer: invalid plan schema');
  }
  for (const s of plan.steps) {
    if (!s.id || !s.payload?.role || !s.payload?.mode || !s.payload?.input) {
      throw new Error(`Decomposer: invalid step: ${JSON.stringify(s)}`);
    }
  }
  return plan;
}

export async function decompose(
  task: DecompTask,
  llmCall: (prompt: string) => Promise<string>
): Promise<Plan> {
  const raw = await llmCall(buildPrompt(task));
  return extract(raw);
}

export type { DecompTask, DecompStep, Plan };
