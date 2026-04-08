"""AAAK FactStore — JSONL-backed fact persistence with TTL expiry."""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any


DEFAULT_TTL = 7200  # 2 hours
DEFAULT_MAX_RECALL = 7


class FactStore:
    """Append-only JSONL fact store with TTL-based expiry.

    Per-campaign isolation: pass a campaign/task prefix to get a separate store file.
    Thread-safe via threading.Lock (matches existing ROME patterns).
    """

    def __init__(
        self,
        store_dir: str | Path | None = None,
        prefix: str = "default",
        ttl_seconds: int = DEFAULT_TTL,
    ) -> None:
        if store_dir is None:
            store_dir = Path(__file__).parent / ".facts"
        self._store_dir = Path(store_dir)
        self._store_dir.mkdir(parents=True, exist_ok=True)
        self._path = self._store_dir / f"{prefix}.jsonl"
        self._ttl = ttl_seconds
        self._lock = threading.Lock()
        self._save_count = 0

    def save(self, fact: dict[str, Any]) -> None:
        """Append a fact to the store. Adds timestamp if missing."""
        if "ts" not in fact:
            fact["ts"] = time.time()
        line = json.dumps(fact, ensure_ascii=False, separators=(",", ":"))
        with self._lock:
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
                f.flush()
        self._save_count += 1
        if self._save_count % 50 == 0:
            self.compact()

    def load_active(self) -> list[dict[str, Any]]:
        """Load all non-expired facts."""
        cutoff = time.time() - self._ttl
        facts = []
        with self._lock:
            if not self._path.exists():
                return facts
            with open(self._path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        fact = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if fact.get("ts", 0) >= cutoff:
                        facts.append(fact)
        return facts

    def query(self, text: str, limit: int = DEFAULT_MAX_RECALL) -> list[dict[str, Any]]:
        """Retrieve facts matching query text, ranked by keyword overlap.

        Simple keyword matching — no external dependencies.
        """
        query_tokens = _tokenize(text)
        if not query_tokens:
            return []

        facts = self.load_active()
        scored: list[tuple[float, dict[str, Any]]] = []
        for fact in facts:
            fact_text = _fact_to_text(fact)
            fact_tokens = _tokenize(fact_text)
            if not fact_tokens:
                continue
            overlap = len(query_tokens & fact_tokens)
            if overlap == 0:
                continue
            # Score: Jaccard similarity + recency bonus
            jaccard = overlap / len(query_tokens | fact_tokens)
            recency = min(1.0, (fact.get("ts", 0) - (time.time() - self._ttl)) / self._ttl)
            score = jaccard * 0.7 + recency * 0.3
            scored.append((score, fact))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [f for _, f in scored[:limit]]

    def compact(self) -> int:
        """Remove expired facts from the store file. Returns count of facts kept."""
        cutoff = time.time() - self._ttl
        with self._lock:
            if not self._path.exists():
                return 0
            lines = self._path.read_text(encoding="utf-8").splitlines()
            active = []
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    fact = json.loads(line)
                    if fact.get("ts", 0) >= cutoff:
                        active.append(line)
                except json.JSONDecodeError:
                    continue
            with open(self._path, "w", encoding="utf-8") as f:
                for line in active:
                    f.write(line + "\n")
                f.flush()
            return len(active)

    def clear(self) -> None:
        """Delete all facts."""
        with self._lock:
            if self._path.exists():
                self._path.unlink()


def _tokenize(text: str) -> set[str]:
    """Split text into lowercase tokens, drop short ones."""
    return {w for w in text.lower().split() if len(w) >= 2}


def _fact_to_text(fact: dict[str, Any]) -> str:
    """Flatten a fact dict into searchable text."""
    parts = []
    for key in ("task", "result", "error"):
        if key in fact:
            parts.append(str(fact[key]))
    if "key_changes" in fact and isinstance(fact["key_changes"], list):
        parts.extend(str(c) for c in fact["key_changes"])
    return " ".join(parts)
