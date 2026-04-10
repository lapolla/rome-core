import type { Fact } from './store.js';

export const DEFAULT_THRESHOLD = 800; // tokens
const CHARS_PER_TOKEN = 4;

export function tokenEstimate(text: string): number {
  return Math.floor(text.length / CHARS_PER_TOKEN);
}

export function needsDistill(prompt: string, threshold: number = DEFAULT_THRESHOLD): boolean {
  return tokenEstimate(prompt) > threshold;
}

export function distill(rawState: { prompt: string; facts: Fact[]; files?: string[]; explicit_constraints?: string[] }, goal: string = ""): string {
  const { prompt, facts, files, explicit_constraints } = rawState;

  const extractedGoal = goal || extractGoal(prompt);
  const intent = extractIntent(prompt);
  const cause = extractCause(prompt);
  
  const sections: string[] = [];
  sections.push(`GOAL: ${extractedGoal}`);
  sections.push(`INTENT: ${intent}`);
  sections.push(`CAUSE: ${cause}`);

  if (facts && facts.length > 0) {
    sections.push("MEMORY:");
    for (const f of facts) {
      sections.push(`- ${f.content}`);
    }
  }

  if (explicit_constraints && explicit_constraints.length > 0) {
    sections.push("CONSTRAINTS:");
    for (const c of explicit_constraints) {
      sections.push(`- ${c}`);
    }
  }

  if (files && files.length > 0) {
    sections.push("FILES:");
    for (const f of files.slice(0, 10)) {
      sections.push(`- ${f}`);
    }
  }

  sections.push("TASK:");
  
  const currentLen = sections.join('\n').length;
  const budget = (DEFAULT_THRESHOLD * CHARS_PER_TOKEN) - currentLen;
  const taskBudget = Math.max(200, budget);

  if (prompt.length <= taskBudget) {
    sections.push(prompt);
  } else {
    const half = Math.floor(taskBudget / 2);
    sections.push(prompt.slice(0, half));
    sections.push("\n[...truncated...]\n");
    sections.push(prompt.slice(-half));
  }

  return sections.join('\n');
}

function extractGoal(text: string): string {
  const m = text.match(/(?:task|goal|command)[:\s]+(.{3,200})/i);
  if (m) return m[1].trim();
  
  const paras = text.split('\n\n').filter(p => p.trim());
  if (paras.length > 0) {
    const last = paras[paras.length - 1].trim();
    if (last.length < 200 && !/Traceback|Exception|Error:/i.test(last)) return last;
  }
  
  return text.split('\n')[0].slice(0, 200) || "Unknown Goal";
}

function extractIntent(text: string): string {
  const m = text.match(/intent[:\s]+(.{3,200})/i);
  if (m) return m[1].trim();
  
  const mustMatch = text.match(/(?:must|ensure|success|pass|without)\s+([^\n.]+)/i);
  if (mustMatch) return mustMatch[0].trim();
  
  return "Complete goal successfully";
}

function extractCause(text: string): string {
  const m = text.match(/cause[:\s]+(.{3,200})/i);
  if (m) return m[1].trim();
  
  if (/Traceback|Exception|Error:/i.test(text)) return "Fixing execution error";
  
  return "Initial dispatch";
}
