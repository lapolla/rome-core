import re
import sys

file_path = "/home/paul-kane/projects/rome-core/dictator/ws_server.py"
with open(file_path, "r") as f:
    content = f.read()

old_code = """    async def on_progress(line):
        m = re.search(r"(\\d+)%\\s+.\\s+\\[([\\d.]+)s\\]\\s+(.*)", line)
        if m:
            try:
                p, msg = int(m.group(1)), m.group(3).strip()
                task_registry.update_progress(task_id, p, msg)
                await emit_progress(event_bus, task_id, p, msg)
            except Exception as e: logger.debug("Swallowed exception: %s", e)"""

new_code = """    def on_progress(line):
        m = re.search(r"(\\d+)%\\s+.\\s+\\[([\\d.]+)s\\]\\s+(.*)", line)
        if m:
            try:
                p, msg = int(m.group(1)), m.group(3).strip()
                task_registry.update_progress(task_id, p, msg)
                asyncio.create_task(emit_progress(event_bus, task_id, p, msg))
            except Exception as e: logger.debug("Swallowed exception: %s", e)"""

if old_code in content:
    content = content.replace(old_code, new_code)
    with open(file_path, "w") as f:
        f.write(content)
    print("Successfully replaced in ws_server.py")
else:
    print("Could not find the exact old code in ws_server.py.")
    sys.exit(1)
