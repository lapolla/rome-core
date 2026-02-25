#!/usr/bin/env python3
import sys, json, os, subprocess

# --- ROME SENATE: NEURAL BRIDGE (BRAIN SPAWN) ---

def spawn_brain(sector_id, prompt):
    """
    Surgically binds an LLM 'Soul' to a Senate Sector.
    """
    manifesto_path = f"senate/architects/T{sector_id}.md"
    if not os.path.exists(manifesto_path):
        return f"Error: Sector {sector_id} has no manifesto."

    with open(manifesto_path, "r") as f:
        manifesto = f.read()

    # The 'Imperial Prompt' - giving the LLM its architectural context
    imperial_prompt = f"""
    YOU ARE THE ARCHITECT FOR ROME SECTOR {sector_id}.
    YOUR MANIFESTO:
    {manifesto}

    YOUR MISSION:
    {prompt}

    OUTPUT ONLY THE BASH COMMAND TO EXECUTE THE NEXT STRIKE. NO CHITCHAT.
    """

    # Dispatch to the Dictator's GEMINI capability
    # In a real run, this calls 'gemini -p ...'
    cmd = ["gemini", "--yolo", "-p", imperial_prompt]
    
    print(f"EVENT: SECTOR_{sector_id}_SOUL_SPAWNED")
    try:
        # We use check_output to get the 'Strike' command back from the brain
        strike_cmd = subprocess.check_output(cmd, text=True).strip()
        # Remove markdown code blocks if the LLM includes them
        strike_cmd = strike_cmd.replace("```bash", "").replace("```", "").strip()
        return strike_cmd
    except Exception as e:
        return f"Error: Soul Spawn Failed: {str(e)}"

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: brain.py <sector_id> <mission_prompt>")
        sys.exit(1)
    
    sector = sys.argv[1]
    mission = sys.argv[2]
    strike = spawn_brain(sector, mission)
    print(f"BRAIN STRIKE COMMAND: {strike}")
