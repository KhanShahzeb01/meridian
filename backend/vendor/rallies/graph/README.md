# rallies.graph (Phase 0–5)

Foundation for LangGraph-based memory and agent orchestration.

**Phase 2:** optional SqliteSaver checkpoints after each LLM turn when
`RALLIES_GRAPH_CHECKPOINTS=1`. Default behavior is unchanged when the flag is off.

**Phase 3:** optional LangGraph `/research` subgraph when `RALLIES_GRAPH_RESEARCH=1`.
Falls back to `ResearchLoop.run` on error or when flag is off.

**Phase 4:** structured session memory digest + tool dual-write when
`RALLIES_GRAPH_MEMORY=1` (auto-on with graph research unless set to `0`).

**Phase 5:** optional LangGraph planner subgraph for free-text prompts when
`RALLIES_GRAPH_PLANNER=1`. Falls back to legacy orchestrator on error or when flag is off.

## Modules

| File | Role |
|------|------|
| `state.py` | Typed `RalliesState` buckets |
| `defaults.py` | Empty state factories |
| `reducers.py` | Append/merge helpers for future graph reducers |
| `serializers.py` | JSON round-trip for checkpoints and debug dumps |
| `context.py` | `build_llm_context` — delegates to `thread_memory` today |
| `checkpoint.py` | `~/.rallies/checkpoints/` path helpers |
| `checkpoint_store.py` | SqliteSaver singleton |
| `checkpoint_runtime.py` | `save_turn_checkpoint` / `load_checkpoint_rallies_state` |
| `shadow_graph.py` | Minimal ingest → persist graph |
| `hooks.py` | `maybe_save_turn_checkpoint` (Manager hook) |
| `flags.py` | `RALLIES_GRAPH_CHECKPOINTS` env flag |
| `commands.py` | `/graph-status` handler |
| `bridge.py` | `state_from_manager` / `state_from_turn` read-only snapshots |
| `memory/` | `memory_digest`, section formatters (Phase 4) |
| `research/messages.py` | Inject memory digest into `/research` LLM context |
| `research/state_slice.py` | Hydrate memory from manager + REPL conversation |
| `research/tool_callback.py` | Tool dual-write into `memory.*` |
| `research/nodes/` | `research_decide`, `research_tools`, `research_done` |

## Design rules

- Existing formulas, slash handlers, and `Manager` flow stay untouched until a later phase enables a feature flag.
- Graph nodes in future phases should **call** existing functions, not reimplement them.
- `build_llm_context` must stay aligned with `thread_memory.new_turn_workspace`.

## Enable checkpoints (Phase 2)

```bash
pip install -e ".[agent]"
export RALLIES_GRAPH_CHECKPOINTS=1
rallies
```

Debug: `/graph-status` shows thread id, tickers, last node, and DB path.

Override DB location (tests): `RALLIES_CHECKPOINT_DB=/path/to/test.db`

## Enable graph /research (Phase 3)

```bash
export RALLIES_GRAPH_RESEARCH=1
# optional per-iteration checkpoints (thread id: {session}:research)
export RALLIES_GRAPH_CHECKPOINTS=1
```

Shared iteration logic lives in `rallies.research.loop_steps` (used by both paths).

## Enable structured memory (Phase 4)

```bash
export RALLIES_GRAPH_MEMORY=1
# or rely on RALLIES_GRAPH_RESEARCH=1 (memory on by default)
# export RALLIES_GRAPH_MEMORY=0   # force off
```

Digest is injected in graph `/research` LLM calls; tool results dual-write to
`memory.tool_results` and `memory.market_snapshots` (summaries only).

## Enable graph planner (Phase 5)

```bash
export RALLIES_GRAPH_PLANNER=1
# optional memory digest in planner LLM calls (default on unless MEMORY=0)
export RALLIES_GRAPH_MEMORY=1
```

Shared step logic lives in `rallies.graph.planner.steps` (used by legacy + graph paths).
Checkpoint thread id: `{session}:planner`.

| Module | Role |
|--------|------|
| `planner/dispatch.py` | Route to graph or legacy orchestrator |
| `planner/legacy_orchestrator.py` | Default Rich planning UI loop |
| `planner/nodes/plan.py` | `agent.run` with optional memory digest |
| `planner/nodes/execute.py` | Parallel gather + synthesis + summarize |
| `planner/nodes/answer.py` | `_stream_final_answer` |
| `planner/memory_write.py` | `memory.plans` + tool dual-write |
