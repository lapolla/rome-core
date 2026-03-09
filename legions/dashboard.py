import sys
import threading
import time

class Dashboard:
    """
    Inline ANSI TUI for ROME campaign progress.
    Renders directly to sys.stdout using cursor control.
    """
    def __init__(self, task_ids: list[str], campaign_id: str):
        self.task_ids = task_ids
        self.campaign_id = campaign_id
        self.lock = threading.Lock()
        self.start_time = time.time()
        
        # Initial print of header and blank rows
        with self.lock:
            sys.stdout.write(f"\n=== ROME CAMPAIGN: {campaign_id} ===\n")
            for tid in task_ids:
                sys.stdout.write(self._format_row(tid, "PENDING", 0, "Waiting...") + "\n")
            sys.stdout.flush()

    def _format_row(self, task_id, status, elapsed_s, message):
        # [ROME:name-padded    ] [████████░░] [STATUS  ] [  1.2s] >> message
        # Limit task_id display length: ROME: (5) + 15 = 20
        display_id = task_id[:15]
        name_padded = f"ROME:{display_id}".ljust(20)
        
        # Progress bar: 10 chars
        # Capped at 90% (9 blocks) until SUCCESS or FAILED
        if status in ["SUCCESS", "FAILED"]:
            progress = 10
        else:
            # Simple progress heuristic: 1 block per 2 seconds, cap at 9
            progress = min(9, int(elapsed_s / 2))
            
        bar = "█" * progress + "░" * (10 - progress)
        
        # ANSI Colors
        COLOR_YELLOW = "\033[33m"
        COLOR_GREEN = "\033[32m"
        COLOR_RED = "\033[31m"
        COLOR_BRIGHT_YELLOW = "\033[93m"
        COLOR_GRAY = "\033[90m"
        COLOR_RESET = "\033[0m"
        
        color = COLOR_RESET
        if status == "RUNNING":
            color = COLOR_YELLOW
        elif status == "SUCCESS":
            color = COLOR_GREEN
        elif status == "FAILED":
            color = COLOR_RED
        elif "RETRY" in status or status == "RETRYING":
            color = COLOR_BRIGHT_YELLOW
        elif status == "PENDING":
            color = COLOR_GRAY
            
        status_str = f"{color}{status.ljust(8)}{COLOR_RESET}"
        # elapsed_str should be 6 chars total, e.g. "  1.2s"
        elapsed_str = f"{elapsed_s:5.1f}s"
        
        # Sanitize message: single line, no trailing newlines
        msg_clean = message.replace('\n', ' ').strip()
        
        return f"[{name_padded}] [{bar}] [{status_str}] [{elapsed_str}] >> {msg_clean}"

    def update(self, task_id: str, status: str, elapsed_s: float, message: str):
        """
        Moves cursor to the specific task row, rewrites it, and moves back.
        """
        with self.lock:
            try:
                idx = self.task_ids.index(task_id)
            except ValueError:
                return
            
            num_rows = len(self.task_ids)
            lines_up = num_rows - idx
            
            # ANSI sequence:
            # \033[<n>A : Move up n lines
            # \033[G    : Move to start of line (column 1)
            # \033[K    : Clear to end of line
            # \033[<n>B : Move down n lines
            
            sys.stdout.write(f"\033[{lines_up}A\033[G")
            sys.stdout.write(self._format_row(task_id, status, elapsed_s, message))
            sys.stdout.write("\033[K")
            sys.stdout.write(f"\033[{lines_up}B\033[G")
            sys.stdout.flush()

    def finish(self, results: dict):
        """
        Prints the final consolidated summary block.
        """
        total_time = time.time() - self.start_time
        succeeded = sum(1 for r in results.values() if r.get('status') == 'SUCCESS')
        failed = sum(1 for r in results.values() if r.get('status') == 'FAILED')
        retried = sum(1 for r in results.values() if "RETRY" in str(r.get('status', '')))
        
        with self.lock:
            sys.stdout.write("\n=== CAESAR'S CONSOLIDATED INTELLIGENCE ===\n")
            sys.stdout.write(f"Campaign: {self.campaign_id}\n")
            status_line = f"Tasks:    {succeeded} succeeded, {failed} failed"
            if retried:
                status_line += f", {retried} retried"
            sys.stdout.write(f"{status_line} | Total: {total_time:.1f}s\n")
            sys.stdout.write("---\n")
            
            for tid in self.task_ids:
                res = results.get(tid, {})
                summary = res.get('summary', 'No summary provided')
                sys.stdout.write(f"[{tid}] >> {summary}\n")
            sys.stdout.flush()

if __name__ == "__main__":
    # Self-test implementation
    test_tasks = ["scout-perimeter", "build-fort", "train-legion"]
    dashboard = Dashboard(test_tasks, "test-vanguard")
    
    # Simulate work
    time.sleep(0.5)
    dashboard.update("scout-perimeter", "RUNNING", 0.5, "Moving into forest...")
    time.sleep(0.5)
    dashboard.update("scout-perimeter", "SUCCESS", 1.0, "Perimeter secure.")
    
    dashboard.update("build-fort", "RUNNING", 0.5, "Laying foundations...")
    time.sleep(0.5)
    dashboard.update("build-fort", "RETRY 1/2", 1.0, "Mudslide detected, clearing...")
    time.sleep(0.5)
    dashboard.update("build-fort", "SUCCESS", 1.5, "Fortification complete.")
    
    dashboard.update("train-legion", "FAILED", 0.8, "Insubordination in ranks.")
    
    test_results = {
        "scout-perimeter": {"status": "SUCCESS", "summary": "Area cleared, no enemies found."},
        "build-fort": {"status": "SUCCESS", "summary": "Walls at 10ft, gates reinforced."},
        "train-legion": {"status": "FAILED", "summary": "Unit morale low, training suspended."}
    }
    
    dashboard.finish(test_results)
