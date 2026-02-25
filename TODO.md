# ROME PROTOCOL: MASTER TODO

## OPERATION AUGUSTUS (CORE C++)
- [x] Modularize `CommandDispatcher` (.h/.cpp).
- [x] Implement thread-safe Push/Pop logic.
- [x] Establish CMake Forge.
- [x] Implement `RE::Actor` and `RE::Console` hooks in `CommandHooks.cpp`.
- [x] Add dispatcher unit tests (`tests/CommandDispatcherTest.cpp`).
- [ ] Add JSON parsing unit tests (`tests/JsonProcessorTest.cpp`).

## OPERATION MONTY PYTHON (DICTATOR)
- [x] Eradicate Node.js dependency.
- [x] Port 32 tools to `dictator/dictator.py`.
- [x] Verify MCP connectivity.
- [x] Implement `skyrim_pivot` (dynamic mouse calibration via SkyrimStateExporter).
- [x] Implement `skyrim_compound_move` (turn-in-place via `look_dx`).

## SENATE
- [x] Brain spawn architecture (`senate/brain.py`).
- [x] Sector manifestos (T0–T63) in `senate/architects/`.
- [ ] Document Senate sector layout and soul-binding protocol.

## LEGIONS
- [x] Centurion orchestrator (`legions/centurion_64.py`).
- [x] Zenith orchestrator (`legions/zenith_orchestrator.py`).
- [x] Legion wrapper (`legions/legion_wrapper.py`).
- [ ] Commit legion task artifacts to git.

---
**"Structure is the foundation of authority."**
