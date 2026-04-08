"""AAAK distill — compress prompts to minimal causal footprint."""

from __future__ import annotations

import re
from typing import Any


DEFAULT_THRESHOLD = 800  # tokens (approx 4 chars/token)
CHARS_PER_TOKEN = 4  # rough estimate for English text


def token_estimate(text: str) -> int:
    """Rough token count — 1 token ≈ 4 chars. Good enough for gating."""
    return len(text) // CHARS_PER_TOKEN


class StructuralExtract:
    """Raw mess -> Structured Causal Dict"""
    def run(self, raw_input: str, history: list[dict | str] | None = None) -> dict[str, Any]:
        history = history or []
        
        goal = self._extract_goal(raw_input)
        intent = self._extract_intent(raw_input)
        cause = self._extract_cause(raw_input)
        evidence = self._normalize_evidence(raw_input)
        constraints, context = self._extract_history(history)
        
        return {
            "goal": goal,
            "intent": intent,
            "cause": cause,
            "evidence": evidence,
            "constraints": constraints,
            "context": context,
            "state": "compiled"
        }

    def _extract_goal(self, text: str) -> str:
        # Priority: explicit task/command anywhere in a line
        goal_pattern = re.compile(r"(?i)(?:task|goal|command)[:\s]+(.{3,200})")
        for line in text.split("\n"):
            m = goal_pattern.search(line)
            if m:
                return m.group(1).strip()
        
        # Heuristic: the last paragraph is often the actual command
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if paragraphs:
            last_p = paragraphs[-1]
            if len(last_p) < 200 and not any(x in last_p for x in ("Traceback", "Exception", "Error:")):
                return last_p
                
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        return lines[0][:200] if lines else "Unknown Goal"

    def _extract_intent(self, text: str) -> str:
        # Priority: explicit intent
        intent_pattern = re.compile(r"(?i)intent[:\s]+(.{3,200})")
        for line in text.split("\n"):
            m = intent_pattern.search(line)
            if m:
                return m.group(1).strip()
                
        # Look for explicit success criteria (must, ensure, success, etc)
        for match in re.finditer(r"(?i)(?:must|ensure|success|pass|without)\s+([^\n.]+)", text):
            return match.group(0).strip()
            
        return "Complete goal successfully"

    def _extract_cause(self, text: str) -> str:
        # Look for explicit failure or "because"
        cause_pattern = re.compile(r"(?i)cause[:\s]+(.{3,200})")
        for line in text.split("\n"):
            m = cause_pattern.search(line)
            if m:
                return m.group(1).strip()
                
        # If it contains a traceback, the cause is an error
        if any(x in text for x in ("Traceback", "Exception", "Error:")):
            return "Fixing execution error"
            
        return "Initial dispatch"

    def _normalize_evidence(self, text: str) -> list[str]:
        # Strip stack traces to ExceptionType: Message @ File:Line
        evidence = []
        
        # Python traceback pattern - more robust to indentation
        tb_pattern = re.compile(r'File "([^"]+)", line (\d+).*?\n\s+(?:.*?\n)?\s*([A-Za-z]+Error): (.*)', re.MULTILINE)
        for match in tb_pattern.finditer(text):
            file, line, exc, msg = match.groups()
            file_name = file.split("/")[-1]
            evidence.append(f"{exc}: {msg} @ {file_name}:{line}")
        
        # If the multiline pattern fails, try a line-by-line anchor
        if not evidence:
            for line in text.split("\n"):
                # Matches: File "core.py", line 88
                m = re.search(r'File "([^"]+)", line (\d+)', line)
                if m:
                    file_name = m.group(1).split("/")[-1]
                    # Look for the error message in subsequent lines or same line
                    err_m = re.search(r'([A-Za-z]+Error): (.*)', text[text.find(line):])
                    if err_m:
                        evidence.append(f"{err_m.group(1)}: {err_m.group(2).strip()} @ {file_name}:{m.group(2)}")
                        break
        
        # Generic error pattern as fallback
        if not evidence:
            err_pattern = re.compile(r"(?i)(?:error|exception|failed)[:]\s*(.{10,200})")
            for match in err_pattern.finditer(text):
                evidence.append(match.group(0).strip())
            
        return evidence[:3]  # Keep it tight

    def _extract_history(self, history: list[dict | str]) -> tuple[list[str], list[str]]:
        constraints = []
        context = []
        for past in history:
            if isinstance(past, dict):
                if past.get("status") in ("FAILED", "failed", "error"):
                    cause = past.get("cause") or past.get("error") or "Unknown error"
                    task_desc = past.get("task") or "Previous approach"
                    constraints.append(f"Approach '{task_desc}' failed ({cause}). Do not retry.")
                else:
                    task = past.get("task", "?")
                    result = past.get("result", "")
                    context.append(f"[SUCCESS] {task} — {result}")
            elif isinstance(past, str):
                if "failed" in past.lower() or "error" in past.lower():
                    constraints.append(f"Previous attempt context: {past}")
                else:
                    context.append(past)
        return constraints[:3], context[:7]


class Distiller:
    """Structured Dict -> Minimal Causal Prompt (<800 tokens)"""
    def run(self, structured: dict[str, Any]) -> str:
        sections = []
        
        sections.append(f"GOAL: {structured.get('goal', 'Unknown')}")
        sections.append(f"INTENT: {structured.get('intent', 'Complete successfully')}")
        sections.append(f"CAUSE: {structured.get('cause', 'Initial dispatch')}")
        
        if structured.get("context"):
            sections.append("CONTEXT:")
            for c in structured["context"]:
                sections.append(f"- {c}")

        if structured.get("constraints"):
            sections.append("CONSTRAINTS:")
            for c in structured["constraints"]:
                sections.append(f"- {c}")
                
        if structured.get("evidence"):
            sections.append("EVIDENCE:")
            for e in structured["evidence"]:
                sections.append(f"- {e}")
                
        return "\n".join(sections)


def distill(raw_state: dict[str, Any], goal: str = "") -> str:
    """Compress raw state + goal into a minimal structured prompt."""
    prompt = raw_state.get("prompt", "")
    facts = raw_state.get("facts", [])
    files = raw_state.get("files", [])
    explicit_constraints = raw_state.get("constraints", [])

    # Fast path for very short, already structured prompts
    if token_estimate(prompt) <= DEFAULT_THRESHOLD and not facts and not explicit_constraints and not files:
        if "GOAL:" in prompt and "TASK:" in prompt:
            return prompt

    # Phase 1: Extract Causal Structure
    extractor = StructuralExtract()
    structured = extractor.run(prompt, facts)
    
    # Merge explicit overrides
    if goal:
        structured["goal"] = goal
    if explicit_constraints:
        structured["constraints"].extend(explicit_constraints)

    # Phase 2: Format
    distiller = Distiller()
    base_distilled = distiller.run(structured)
    
    # Phase 3: Files & Fallback TASK attachment
    sections = [base_distilled]
    
    if files:
        sections.append("FILES:")
        for f in files[:10]:
            sections.append(f"- {f}")

    sections.append("TASK:")
    
    # Budget remaining tokens for the raw task
    current_len = len("\n".join(sections))
    task_budget = (DEFAULT_THRESHOLD * CHARS_PER_TOKEN) - current_len
    task_budget = max(200, task_budget)  # always give task at least 200 chars

    if len(prompt) <= task_budget:
        sections.append(prompt)
    else:
        # Extreme compression — take first and last parts
        half = task_budget // 2
        sections.append(prompt[:half])
        if len(prompt) > half * 2:
            sections.append("\n[...truncated...]\n")
            sections.append(prompt[-half:])

    return "\n".join(sections)


def needs_distill(prompt: str, threshold: int = DEFAULT_THRESHOLD) -> bool:
    """Check if a prompt exceeds the token threshold or lacks causal structure."""
    if token_estimate(prompt) > threshold:
        return True
    
    # Check if it has causal chain markers
    has_structure = all(marker in prompt for marker in ["GOAL:", "INTENT:", "CAUSE:"])
    # If it lacks structure, we should force it through the compiler, even if short
    return not has_structure
