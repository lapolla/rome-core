#!/usr/bin/env python3
import json
import time
import sys
import os
import subprocess
from pathlib import Path

# --- DOVAHKIIN OPS: TACTICAL DASHBOARD (SONIC SENSES) ---

STATE_FILE = Path("/media/paul-kane/SteamGames/steamapps/compatdata/489830/pfx/drive_c/tmp/skyrim_state.json")
AUDIO_TOOL = Path("/home/paul-kane/projects/rome-core/intelligence/audio_monitor.py")
REFRESH_RATE = 0.5

class TacticalDashboard:
    def __init__(self):
        self.last_timestamp = 0
        self.audio_level = 0.0
        
    def clear_screen(self):
        sys.stderr.write("\033[2J\033[H")

    def get_audio(self):
        try:
            res = subprocess.check_output([str(AUDIO_TOOL)], text=True)
            data = json.loads(res)
            return data.get("peak", 0.0)
        except:
            return 0.0

    def draw_bar(self, label, current, max_val, color_code="\033[92m"):
        width = 30
        if max_val <= 0: max_val = 1
        percent = min(1.0, max(0.0, current / max_val))
        filled = int(width * percent)
        bar = "█" * filled + "░" * (width - filled)
        return f"{label:<10} {color_code}|{bar}| \033[0m {int(current)}/{int(max_val)}"

    def render(self, data):
        self.clear_screen()
        self.audio_level = self.get_audio()
        
        print(f"\033[1;36m=== ROME COMMAND CENTER: DOVAHKIIN OPS ===\033[0m")
        print(f"Time: {data.get('timestamp', 0):.2f} | Cell: {data.get('position', {}).get('cell', 'Unknown')}\n")

        # 1. Vitals
        v = data.get("vitals", {})
        print(self.draw_bar("HEALTH", v.get("health", 0), v.get("healthMax", 1), "\033[91m"))
        print(self.draw_bar("MAGICKA", v.get("magicka", 0), v.get("magickaMax", 1), "\033[94m"))
        print(self.draw_bar("STAMINA", v.get("stamina", 0), v.get("staminaMax", 1), "\033[92m"))
        
        # 2. Audio Pulse
        audio_color = "\033[93m" if self.audio_level > 0.01 else "\033[90m"
        print(self.draw_bar("AUDIO", self.audio_level * 100, 100, audio_color))

        # 3. Threats
        actors = data.get("nearbyActors", [])
        hostiles = [a for a in actors if a.get("hostile")]
        print(f"\n\033[1;31m--- THREAT RADAR [{len(hostiles)}] ---\033[0m")
        if not actors:
            print("No signatures detected.")
        else:
            actors.sort(key=lambda x: x.get("distance", 9999))
            for a in actors[:5]:
                color = "\033[91m" if a.get("hostile") else "\033[97m"
                print(f"{color}{a.get('distance'):<5}m {a.get('name'):<25} {a.get('healthPct')}% HP\033[0m")

    def run(self):
        while True:
            try:
                if not STATE_FILE.exists():
                    time.sleep(1)
                    continue
                with open(STATE_FILE, "r") as f:
                    data = json.load(f)
                ts = data.get("timestamp", 0)
                if ts != self.last_timestamp:
                    self.render(data)
                    self.last_timestamp = ts
                time.sleep(REFRESH_RATE)
            except KeyboardInterrupt:
                break
            except:
                time.sleep(1)

if __name__ == "__main__":
    TacticalDashboard().run()
