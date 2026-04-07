"""AAAK distill — compress prompts to minimal token footprint."""

from __future__ import annotations

from typing import Any


DEFAULT_THRESHOLD = 800  # tokens (approx 4 chars/token)
CHARS_PER_TOKEN = 4  # rough estimate for English text


def token_estimate(text: str) -> int:
    """Rough token count — 1 token ≈ 4 chars. Good enough for gating."""
    return len(text) // CHARS_PER_TOKEN


def distill(raw_state: dict[str, Any], goal: str) -> str:
    """Compress raw state + goal into a minimal structured prompt.

    Template path only (no LLM call). Returns a structured prompt
    under ~500 tokens in GOAL/CONTEXT/CONSTRAINTS/TASK format.
    """
    prompt = raw_state.get("prompt", "")
    facts = raw_state.get("facts", [])
    constraints = raw_state.get("constraints", [])
    files = raw_state.get("files", [])

    # If prompt is already short, return structured but uncompressed
    if token_estimate(prompt) <= DEFAULT_THRESHOLD and not facts:
        return prompt

    sections = []

    # GOAL
    sections.append(f"GOAL: {goal}")

    # CONTEXT — recalled facts
    if facts:
        sections.append("CONTEXT:")
        for fact in facts[:7]:
            sections.append(f"- {fact}")

    # FILES — relevant file paths
    if files:
        sections.append("FILES:")
        for f in files[:10]:
            sections.append(f"- {f}")

    # CONSTRAINTS
    if constraints:
        sections.append("CONSTRAINTS:")
        for c in constraints:
            sections.append(f"- {c}")

    # TASK — the actual prompt, truncated if needed
    sections.append("TASK:")
    task_budget = (DEFAULT_THRESHOLD * CHARS_PER_TOKEN) - len("\n".join(sections))
    if task_budget > 200:
        sections.append(prompt[:task_budget])
    else:
        # Extreme compression — take first and last parts
        half = max(100, task_budget // 2)
        sections.append(prompt[:half])
        if len(prompt) > half * 2:
            sections.append("...")
            sections.append(prompt[-half:])

    result = "\n".join(sections)
    return result


def needs_distill(prompt: str, threshold: int = DEFAULT_THRESHOLD) -> bool:
    """Check if a prompt exceeds the token threshold and needs compression."""
    return token_estimate(prompt) > threshold
