"""AAAK recall — retrieve relevant facts for the next dispatch."""

from __future__ import annotations

from typing import Any

from aaak.store import FactStore


DEFAULT_MAX_RECALL = 7


def recall(query: str, store: FactStore, limit: int = DEFAULT_MAX_RECALL) -> list[str]:
    """Fetch relevant facts as formatted strings for prompt injection.

    Returns a list of short, human-readable fact strings (max `limit`).
    """
    facts = store.query(query, limit=limit)
    return [_format_fact(f) for f in facts]


def recall_raw(query: str, store: FactStore, limit: int = DEFAULT_MAX_RECALL) -> list[dict[str, Any]]:
    """Fetch relevant facts as raw dicts (for programmatic use)."""
    return store.query(query, limit=limit)


def _format_fact(fact: dict[str, Any]) -> str:
    """Format a fact dict into a concise one-liner for prompt context."""
    task = fact.get("task", "?")
    result = fact.get("result", "")
    status = fact.get("status", "")

    parts = [f"[{status}] {task}"]
    if result:
        parts.append(result[:120])
    if fact.get("error"):
        parts.append(f"Error: {fact['error'][:80]}")
    if fact.get("key_changes"):
        changes = fact["key_changes"][:3]
        parts.append(f"Changes: {', '.join(str(c)[:40] for c in changes)}")

    return " — ".join(parts)
