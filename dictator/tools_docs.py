"""ROME Protocol v3 — Project documentation tools (CHANGELOG.md, STATUS.md)."""
import re
from pathlib import Path
from datetime import datetime
from dictator.core import mcp, ROME_ROOT

@mcp.tool()
def update_project_docs(project_path: str, features: list[dict], verification: list[str]) -> str:
    """
    Updates project documentation (CHANGELOG.md and STATUS.md).
    Reads recent manifest.json files from legions/TASK_*/ for ROME_META changed/reason entries.
    features: list of {name, status, notes} dicts.
    verification: list of checklist strings.
    """
    proj_dir = Path(project_path)
    proj_dir.mkdir(parents=True, exist_ok=True)

    changelog_path = proj_dir / "CHANGELOG.md"
    status_path = proj_dir / "STATUS.md"

    legions_dir = ROME_ROOT / "legions"
    meta_entries = []

    if legions_dir.exists() and legions_dir.is_dir():
        for manifest_path in legions_dir.glob("TASK_*/manifest.json"):
            try:
                content = manifest_path.read_text(encoding="utf-8")
                changes = re.findall(r'\[ROME_META:\s*changed=([^\]]+)\]', content)
                reasons = re.findall(r'\[ROME_META:\s*reason=([^\]]+)\]', content)
                for c, r in zip(changes, reasons):
                    meta_entries.append(f"- **Changed:** {c.strip()} | **Reason:** {r.strip()}")
            except Exception:
                pass

    meta_entries = list(dict.fromkeys(meta_entries))

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # CHANGELOG.md (append)
    changelog_append = f"\n## Update: {now_str}\n\n"
    if meta_entries:
        changelog_append += "### Automated ROME Protocol Changes\n"
        changelog_append += "\n".join(meta_entries) + "\n\n"
    changelog_append += "### Features Updated\n"
    for feat in features:
        name = feat.get('name', 'Unknown')
        status = feat.get('status', 'Unknown')
        notes = feat.get('notes', '')
        changelog_append += f"- **{name}** ({status}): {notes}\n"
    changelog_append += "\n### Verification\n"
    for v in verification:
        changelog_append += f"- [x] {v}\n"

    with open(changelog_path, "a", encoding="utf-8") as f:
        f.write(changelog_append)

    # STATUS.md (overwrite)
    status_content = f"# Project Status\n*Last Updated: {now_str}*\n\n## Features\n"
    for feat in features:
        name = feat.get('name', 'Unknown')
        status = feat.get('status', 'Unknown')
        notes = feat.get('notes', '')
        status_content += f"- **{name}** [{status}]: {notes}\n"
    status_content += "\n## Verification Checklist\n"
    for v in verification:
        status_content += f"- [ ] {v}\n"

    with open(status_path, "w", encoding="utf-8") as f:
        f.write(status_content)

    return f"Updated CHANGELOG.md and STATUS.md in {project_path}. {len(meta_entries)} ROME_META entries found."
