# ROME Senate

The Senate is the mind of the Empire. We architect the path so the Legions can strike.

## Architecture

- **`brain.py`** — Neural bridge that binds an LLM "Soul" to a Senate Sector. Takes a sector ID and mission prompt, loads the sector manifesto, and dispatches to the LLM for a surgical strike command.
- **`architects/`** — 64 sector manifestos (`T0.md`–`T63.md`). Each manifesto defines the architectural context for its sector, consumed by `brain.py` during soul spawning.

## Usage

```bash
python3 senate/brain.py <sector_id> "<mission_prompt>"
```

The brain resolves the sector manifesto, constructs an Imperial Prompt, and returns a single executable strike command.

## Usage

Query the Senate by reading `architects/` manifestos directly, or dispatch `senate/brain.py` with a sector index to get context for a GEMINI legion.
