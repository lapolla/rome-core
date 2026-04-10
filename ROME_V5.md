# ROME v5 — Distributed Agent Mesh

> **v4 has a broker. v5 has a mesh.**

## The Problem with v4

v4 is a hub-and-spoke model. Every dispatch flows through the daemon on port 8741. This is fine for one machine, but it creates:

- **Single point of failure** — daemon dies, everything stops
- **Single point of bottleneck** — all token traffic passes through one process
- **Topological rigidity** — Claude Code, Gemini, CODEX all speak to one broker, never directly to each other

## v5 Core Idea

Every agent IS a WS server, not just a WS client. Agents speak the ROME protocol directly to each other.

```
Claude Code ◀──WS──▶ Gemini CLI
     ▲                    ▲
     └────WS────┬──────WS─┘
                │
              CODEX
```

No central broker required. Any agent can dispatch to any other agent directly.

## Architecture Changes

### What stays the same
- WS message shapes: `dispatch`, `complete`, `progress`, `agent_hello`, `worker_ack` — unchanged
- Legion capabilities and the arsenal — unchanged
- AAAK fact store — each peer runs its own instance
- `legion_wrapper.py` — unchanged, still handles execution

### What changes

**Each agent runs a peer server** (small addition to existing client code):

| Component | v4 | v5 |
|-----------|----|----|
| Claude Code | WS client only | WS client + peer server |
| Gemini CLI | WS client + worker | WS client + worker + peer server |
| Daemon | Central broker | Optional peer (registry + dashboard) |
| CODEX/MISTRAL | Subprocess | Can be persistent peer |

**Peer discovery** — static config or simple broadcast:
```json
{
  "peers": [
    "ws://127.0.0.1:8741",
    "ws://127.0.0.1:8742",
    "ws://gemini-host:8743"
  ]
}
```

Peers announce themselves with `agent_hello` on connect. No central registry required.

## AAAK in v5

This is the key design question. In v4, AAAK fact store is per-daemon-process. In v5, facts need to flow across peers.

### Approach: `facts_broadcast` event type

Add one new WS event type — `facts_broadcast`:

```json
{
  "type": "event",
  "event": {
    "type": "facts_broadcast",
    "task_id": "task_abc",
    "payload": {
      "fact": {
        "type": "fact",
        "task": "auth fix",
        "result": "fixed JWT TTL",
        "key_changes": ["adjusted expiry check"],
        "confidence": 0.9,
        "ts": 1744000000.0
      }
    }
  }
}
```

Each peer, on `post_result`, broadcasts the compressed fact to all connected peers. Peers save it to their local fact store. No shared database, no coordination overhead — eventual consistency is fine for prompt context.

**Implementation in `aaak/__init__.py`:**

```python
def post_result(self, manifest, task_description="", broadcast_fn=None):
    fact = compress(manifest, task_description)
    self.store.save(fact)
    if broadcast_fn:
        broadcast_fn({"type": "facts_broadcast", "payload": {"fact": fact}})
    return fact
```

The `broadcast_fn` is injected by the daemon/peer server — zero coupling.

### Fact store isolation strategy

| Scope | Store prefix | Use case |
|-------|-------------|----------|
| Campaign | `campaign_{id}` | Facts from one centurion campaign |
| Session | `session_{ts}` | All facts from a daemon session |
| Global | `global` | Long-lived cross-campaign facts (opt-in) |

Peers choose which scopes to share. Campaign scope is the default and safest.

## Daemon in v5

The daemon doesn't go away — it becomes optional infrastructure:

- **TaskRegistry** — still useful as a centralized state store for dashboard
- **Dashboard** — still runs on the daemon
- **EventBus** — still useful for fan-out to multiple listeners
- **WS broadcast** — still the easiest way to relay events

But agents no longer REQUIRE it. Two agents can talk directly without a daemon in the path.

## Migration Path

v4 → v5 is additive. No breaking changes.

1. **Phase 1** (now): AAAK `facts_broadcast` event — daemon broadcasts facts to all peers that subscribe. Peers accumulate cross-task context passively. (1 event type, ~50 lines)

2. **Phase 2**: Each agent starts a peer server on a configurable port. Peer discovery via `config.json` `peers` list.

3. **Phase 3**: Direct agent-to-agent dispatch — `rome_dispatch(capability="GEMINI", peer="ws://...")`. Falls back to daemon routing if peer unreachable.

4. **Phase 4** (optional): Daemon becomes just another peer. TaskRegistry moved to a dedicated lightweight state service.

## AAAK Recall Backend — ChromaDB?

**Short answer: not yet.**

Keyword/TF-IDF recall (V1) is good enough when:
- Facts are campaign-scoped (< 200 facts per store)
- Queries are task descriptions (~20 words)
- Recall happens < 50ms

ChromaDB adds value when:
- Facts accumulate across many campaigns (> 500 facts)
- Queries are semantically distant from stored task descriptions (e.g., "debug login" should recall "JWT TTL fix")
- You're running long-horizon multi-day campaigns

**When to add it:** wire ChromaDB as an optional backend in `store.py` behind a config flag (`aaak_recall_backend: "chroma"`). Keep keyword as default. No dependency for base install.

```python
# store.py — future
class FactStore:
    def __init__(self, ..., backend="keyword"):
        if backend == "chroma":
            self._backend = ChromaBackend(...)
        else:
            self._backend = KeywordBackend(...)
```

Don't add it until keyword search demonstrably misses relevant facts in a real campaign.

## What to Build Next

Priority order:

1. ✅ `facts_broadcast` event in daemon + peer handler in ws_server (Phase 1) — done in commit 63911e7
2. ✅ Peer server stub in `rome_native.py` — done (auth, ping, dispatch skeleton). **Dispatch returns `ok: False` — not yet wired to legion_wrapper.**
3. ⬜ Wire `PeerServer.handle_connection` dispatch to spawn a legion_wrapper subprocess — this makes Phase 3 (A2A dispatch) actually functional
4. ⬜ ChromaDB backend (optional, behind flag) — skip until keyword search demonstrably misses facts
