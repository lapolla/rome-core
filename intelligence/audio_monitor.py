#!/usr/bin/env python3
import subprocess
import numpy as np
import json
import sys
import time

# --- ROME INTELLIGENCE: AUDIO MONITOR (THE EARS) ---

def get_default_monitor():
    try:
        sink = subprocess.check_output(["pactl", "get-default-sink"], text=True).strip()
        return f"{sink}.monitor"
    except:
        return None

def get_peak_level(duration=0.5):
    monitor = get_default_monitor()
    if not monitor:
        return {"status": "ERROR", "error": "No default monitor found"}

    # Record short slice of raw S16LE audio
    # 44100Hz * 2 channels * 2 bytes (S16) * duration
    bytes_to_read = int(44100 * 2 * 2 * duration)
    
    try:
        cmd = [
            "pacat", "--record", 
            "-d", monitor, 
            "--format=s16le", 
            "--channels=2", 
            "--rate=44100"
        ]
        
        # Capture raw bytes
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        raw_data = process.stdout.read(bytes_to_read)
        process.terminate()

        if not raw_data:
            return {"status": "SILENCE", "peak": 0.0, "rms": 0.0}

        # Convert to numpy array
        audio_data = np.frombuffer(raw_data, dtype=np.int16)
        
        # Normalize to 0.0 - 1.0
        peak = np.max(np.abs(audio_data)) / 32768.0
        rms = np.sqrt(np.mean(audio_data.astype(float)**2)) / 32768.0

        return {
            "status": "ACTIVE" if peak > 0.01 else "SILENCE",
            "peak": round(float(peak), 4),
            "rms": round(float(rms), 4),
            "device": monitor
        }
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}

if __name__ == "__main__":
    # Task ID is usually first arg in Legion mode, but we can run solo
    result = get_peak_level()
    print(json.dumps(result, indent=2))
