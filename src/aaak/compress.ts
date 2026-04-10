import type { Fact } from './store.js';

export interface Manifest {
  task_id: string;
  status: string;
  usage?: { total_tokens: number } | null;
  runtime?: { elapsed_s: number };
  metadata?: { failure_reason?: string };
  report?: string;
}

export function compress(manifest: Manifest, taskDescription: string = ""): Fact {
  const status = manifest.status || "UNKNOWN";
  const reportText = manifest.report || "";

  const keyChanges = extractChanges(reportText);
  
  let error: string | undefined;
  let cause = "Unknown cause";

  if (["FAILED", "failed", "error"].includes(status.toUpperCase())) {
    error = manifest.metadata?.failure_reason || extractError(reportText);
    cause = error || "Execution failed";
  } else {
    cause = extractCause(reportText);
  }

  const resultSummary = extractSummary(reportText, status);
  const confidence = (status.toUpperCase() === "SUCCESS" && reportText) ? 0.9 : 0.3;

  return {
    type: "fact",
    task: taskDescription || manifest.task_id || "unknown",
    content: resultSummary,
    result: resultSummary,
    cause: cause,
    status: status,
    key_changes: keyChanges,
    confidence: (["FAILED", "failed", "error"].includes(status.toUpperCase())) ? 0.1 : confidence,
    ts: Date.now() / 1000,
    tokens_used: manifest.usage?.total_tokens || 0,
    elapsed_s: manifest.runtime?.elapsed_s || 0,
    error: error
  };
}

function extractCause(report: string): string {
  const causeRegex = /(?:cause|reason|because|due to)[\s:]+(.{10,150})(?:\n|$)/i;
  const match = report.match(causeRegex);
  if (match) return match[1].trim();

  const resolveRegex = /(?:fixed by|resolved by)[\s:]+(.{10,150})(?:\n|$)/i;
  const match2 = report.match(resolveRegex);
  if (match2) return match2[1].trim();

  return "Task completed successfully";
}

function extractChanges(report: string): string[] {
  const changes: string[] = [];
  
  const fileRegex = /(?:modified|created|updated|changed|wrote|fixed)\s+[`'"]?([^\s`'",:]+\.\w+)/gi;
  let m;
  while ((m = fileRegex.exec(report)) !== null && changes.length < 5) {
    changes.push(`modified ${m[1]}`);
  }

  const signalRegex = /\[ROME_SIGNAL:\s*(\w+)\]\s*(.*?)(?:\n|$)/g;
  while ((m = signalRegex.exec(report)) !== null && changes.length < 7) {
    changes.push(`${m[1]}: ${m[2].trim()}`);
  }

  const bulletRegex = /^[\s]*[-*]\s+(.{10,80})$/gm;
  while ((m = bulletRegex.exec(report)) !== null && changes.length < 7) {
    const line = m[1].trim();
    if (/(fixed|added|removed|updated|changed|created|refactored)/i.test(line)) {
      changes.push(line);
    }
  }

  return changes.slice(0, 7);
}

function extractError(report: string): string | undefined {
  const patterns = [
    /(?:error|exception|traceback|failed)[:]\s*(.{3,200})/i,
    /^(.{3,200}error.{0,100})$/im
  ];
  for (const p of patterns) {
    const m = report.match(p);
    if (m) return m[1].trim();
  }
  return undefined;
}

function extractSummary(report: string, status: string): string {
  if (!report) return status === "SUCCESS" ? "Goal achieved" : "Task failed";
  const lines = report.split('\n').map(l => l.trim()).filter(l => l.length > 5);
  for (const line of lines) {
    if (line.startsWith('#') || line.startsWith('---')) continue;
    return line.slice(0, 200);
  }
  return status === "SUCCESS" ? "Goal achieved" : "Task failed";
}
