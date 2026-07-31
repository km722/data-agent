# [name me]

> An autonomous data-analyst agent built from scratch — no agent frameworks. Point it at a messy CSV; it profiles, cleans, analyzes, and hands back a report plus a reproducible script.

## Results

| System | 20 Nightmares (own eval) | InfiAgent-DABench | Frameworks used |
|---|---|---|---|
| _this agent_ | | | **none** |
| ChatGPT paste-in baseline | | | — |

## Repo map

- `MISSION.md` / `DAY1.md` — plan
- `docs/` — design doc, hand-simulation, decision records
- `agent/` — the loop (the engine)
- `tools/` — tool implementations
- `sandbox/` — untrusted-code execution
- `evals/` — harness + the 20 Nightmares
- `demo/` — CLI entry point
