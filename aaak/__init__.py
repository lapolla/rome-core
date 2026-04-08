"""AAAK — Adaptive Agent Attention Kernel.

3-function interface for token-efficient agent dispatch:
  distill()  — raw state → minimal prompt
  compress() — worker output → compact fact
  recall()   — query → relevant facts for next prompt
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aaak.store import FactStore
from aaak.compress import compress
from aaak.distill import distill, needs_distill, token_estimate
from aaak.recall import recall, recall_raw


# Load config from dictator/config.json
_CFG_PATH = Path(__file__).resolve().parent.parent / "dictator" / "config.json"
_cfg: dict[str, Any] = {}
if _CFG_PATH.exists():
    try:
        with open(_CFG_PATH) as f:
            _cfg = json.load(f)
    except Exception:
        pass

AAAK_ENABLED = _cfg.get("aaak_enabled", False)
AAAK_DISTILL_THRESHOLD = _cfg.get("aaak_distill_threshold", 800)
AAAK_FACT_TTL = _cfg.get("aaak_fact_ttl_seconds", 7200)
AAAK_MAX_RECALL = _cfg.get("aaak_max_recall", 7)

# Skip AAAK for these capabilities — already terse
_SKIP_CAPABILITIES = {"SAFE_SHELL", "NATIVE_SHELL"}


class AAAK:
    """Main AAAK interface. One instance per campaign or dispatch context."""

    def __init__(
        self,
        prefix: str = "default",
        store_dir: str | Path | None = None,
        enabled: bool | None = None,
    ) -> None:
        self.enabled = enabled if enabled is not None else AAAK_ENABLED
        self.store = FactStore(
            store_dir=store_dir,
            prefix=prefix,
            ttl_seconds=AAAK_FACT_TTL,
        )

    def should_process(self, capability: str) -> bool:
        """Check if AAAK should process this dispatch."""
        return self.enabled and capability.upper() not in _SKIP_CAPABILITIES

    def pre_dispatch(self, prompt: str, goal: str, capability: str) -> str:
        """Hook 1: Before dispatch — recall facts and distill prompt.

        Returns the (possibly compressed) prompt to send to the worker.
        """
        if not self.should_process(capability):
            return prompt

        if not needs_distill(prompt, AAAK_DISTILL_THRESHOLD) and not self.store.load_active():
            return prompt

        # Recall relevant facts
        facts = recall(goal or prompt[:200], self.store, limit=AAAK_MAX_RECALL)

        # Distill
        raw_state = {"prompt": prompt, "facts": facts}
        return distill(raw_state, goal or prompt[:100])

    def post_result(
        self,
        manifest: dict[str, Any],
        task_description: str = "",
        broadcast_fn=None,
    ) -> dict[str, Any]:
        """Hook 3: After worker returns — compress and store fact.

        Returns the compressed fact dict, or an empty dict if the task failed.
        """
        fact = compress(manifest, task_description)

        # Do not store failures — only successful outcomes belong in recall context
        if fact.get("status") != "SUCCESS":
            return {}

        self.store.save(fact)

        if broadcast_fn is not None:
            try:
                broadcast_fn({"type": "facts_broadcast", "payload": {"fact": fact}})
            except Exception:
                pass
        return fact

    def guard_prompt(self, prompt: str, goal: str = "") -> str:
        """Hook 2: Safety net — distill if prompt exceeds threshold.

        Called from legion_wrapper as a guard before sending to model.
        No recall (no store access from subprocess).
        """
        if not self.enabled:
            return prompt
        if not needs_distill(prompt, AAAK_DISTILL_THRESHOLD):
            return prompt
        raw_state = {"prompt": prompt}
        return distill(raw_state, goal or prompt[:100])


_instances: dict[str, "AAAK"] = {}
def get_aaak(prefix: str = "default") -> "AAAK":
    if prefix not in _instances:
        _instances[prefix] = AAAK(prefix=prefix)
    return _instances[prefix]
