"""AAAK compress — extract compact facts from legion manifests."""

from __future__ import annotations

import re
import time
from typing import Any


def compress(manifest: dict[str, Any], task_description: str = "") -> dict[str, Any]:
    """Turn a full legion manifest into a compact fact dict.

    Pure Python — no LLM call. Extracts status, key changes, errors,
    and strips logs/raw output/progress.
    """
    status = manifest.get("status", "UNKNOWN")
    usage = manifest.get("usage", {})
    runtime = manifest.get("runtime", {})
    metadata = manifest.get("metadata", {})

    # Extract report content (first artifact)
    report_text = ""
    artifacts = manifest.get("artifacts", [])
    if artifacts:
        artifact_path = artifacts[0].get("path", "")
        if artifact_path:
            try:
                with open(artifact_path, "r", encoding="utf-8") as f:
                    report_text = f.read(8192)  # cap read at 8KB
            except (OSError, IOError):
                pass

    # Extract key changes from report
    key_changes = _extract_changes(report_text)

    # Extract error if failed
    error = None
    if status in ("FAILED", "failed", "error"):
        error = metadata.get("failure_reason") or _extract_error(report_text)

    # Build result summary — first meaningful line of report
    result_summary = _extract_summary(report_text, status)

    # Confidence: SUCCESS with output = high, FAILED = low
    confidence = 0.9 if status == "SUCCESS" and report_text else 0.3
    if status in ("FAILED", "failed", "error"):
        confidence = 0.1

    fact: dict[str, Any] = {
        "type": "fact",
        "task": task_description or manifest.get("task_id", "unknown"),
        "result": result_summary,
        "status": status,
        "key_changes": key_changes,
        "confidence": confidence,
        "ts": time.time(),
        "tokens_used": usage.get("total_tokens", 0),
        "elapsed_s": runtime.get("elapsed_s", 0),
    }
    if error:
        fact["error"] = error

    return fact


def _extract_changes(report: str) -> list[str]:
    """Pull out key changes from report text."""
    changes = []

    # Look for file paths that were modified
    file_patterns = re.findall(r"(?:modified|created|updated|changed|wrote|fixed)\s+[`'\"]?([^\s`'\",:]+\.\w+)", report, re.IGNORECASE)
    changes.extend(f"modified {f}" for f in file_patterns[:5])

    # Look for ROME signals
    for match in re.finditer(r"\[ROME_SIGNAL:\s*(\w+)\]\s*(.*?)(?:\n|$)", report):
        changes.append(f"{match.group(1)}: {match.group(2).strip()}")

    # Look for bullet-point summaries
    for match in re.finditer(r"^[\s]*[-*]\s+(.{10,80})$", report, re.MULTILINE):
        line = match.group(1).strip()
        if any(kw in line.lower() for kw in ("fixed", "added", "removed", "updated", "changed", "created", "refactored")):
            changes.append(line)
            if len(changes) >= 7:
                break

    return changes[:7]


def _extract_error(report: str) -> str | None:
    """Pull the first error-like line from a report."""
    for pattern in [
        r"(?:error|exception|traceback|failed)[:]\s*(.{10,200})",
        r"^(.{10,200}error.{0,100})$",
    ]:
        m = re.search(pattern, report, re.IGNORECASE | re.MULTILINE)
        if m:
            return m.group(1).strip()[:200]
    return None


def _extract_summary(report: str, status: str) -> str:
    """Get a one-line summary from the report."""
    if not report.strip():
        return f"Task {status.lower()}, no output"

    # Look for explicit summary markers
    for marker in ["## Summary", "# Summary", "SUMMARY:", "Result:"]:
        idx = report.find(marker)
        if idx >= 0:
            after = report[idx + len(marker):].strip()
            first_line = after.split("\n")[0].strip()
            if first_line:
                return first_line[:200]

    # First non-empty line
    for line in report.split("\n"):
        line = line.strip()
        if line and len(line) > 5 and not line.startswith(("[", "#", "```", "---")):
            return line[:200]

    return f"Task {status.lower()}"
