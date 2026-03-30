#!/usr/bin/env python3
import sys
import os
import json
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dictator.rome_log import log_event

def main():
    if len(sys.argv) < 4:
        print("Usage: report_usage.py <tool_name> <total_tokens> <cost_usd> [message]")
        sys.exit(1)
    
    tool = sys.argv[1]
    tokens = int(sys.argv[2])
    cost = float(sys.argv[3])
    msg = sys.argv[4] if len(sys.argv) > 4 else ""
    
    log_event(
        tool=tool,
        status="usage",
        message=msg,
        usage={
            "total_tokens": tokens,
            "cost_usd": cost
        }
    )
    print(f"Logged {tokens} tokens for {tool}")

if __name__ == "__main__":
    main()
