# Architecture

How this system is put together and why. Part of the documentation set — start at
[`README.md`](README.md) if you want the overview first.

If you are looking for the rules to follow while editing it, those are condensed in
[`CONVENTIONS.md`](CONVENTIONS.md); each one links back to the section here that explains it.
Prompt and scoring changes are covered in [`CREW.md`](CREW.md). Open backlog items live in
[`BACKEND_IMPROVEMENTS.md`](BACKEND_IMPROVEMENTS.md).

## Overview

A [crewAI](https://crewai.com) crew that triages Atlassian Jira support tickets. Two agents
run sequentially: the **triage agent** fetches the ticket and scores customer frustration
1–10 against calibration tiers, and the **Tier-2 resolver** either drafts a customer reply or,
at or above the escalation threshold, writes internal handover notes for a human.

Everything about that capability lives in **one vertical slice**,
`features/support_triage/`, with a ports-and-adapters interior. Outside the slice there is
only shared plumbing (`core/`) and three clients of it — a JSON API, a server-rendered web
console, and a CLI — all entering through the same use case.

## Layout

```
src/customer_support_crew/
├── core/                    settings, error vocabulary, LLM factory — no crewAI, no domain
├── features/support_triage/
│   ├── domain/              models.py (pydantic output schemas), policy.py, ticket_key.py
│   ├── ports.py             TicketSource, TriagePipeline, ResolutionStore (Protocols)
│   ├── application/         resolve_ticket.py — the use case every client calls
│   ├── adapters/
│   │   ├── jira_ticket_source.py       TicketSource over Jira Cloud
│   │   ├── file_resolution_store.py    ResolutionStore over output/*.json
│   │   └── crewai_pipeline/            TriagePipeline via the crew
│   │       ├── crew.py, tools.py, pipeline.py, result_mapper.py
│   │       └── config/{agents,tasks}.yaml
│   └── api/                 dto.py (wire contract), routes.py (/api/v1)
├── api/                     app.py (factory, lifespan, error→status mapping), deps.py (composition root)
├── web/                     routes.py + templates/ + static/ — the Jinja console
└── cli/                     console.py
```

Dependencies point inward. `domain/` imports nothing but pydantic; `application/` imports
`domain/` and `ports.py`; `adapters/` implement the ports; `api/deps.py` is the only module
that knows which implementations are the real ones.

## Request flow

Identical for all three clients:

```
POST /api/v1/resolutions  ─┐
POST /resolve (HTML form) ─┼→ ResolveTicketUseCase.execute(ticket_id)
uv run run_crew KEY       ─┘     ├─ normalize_ticket_id      (fails before spending an LLM call)
                                 ├─ CrewAITriagePipeline.run  triage_task → resolution_task
                                 │    └─ to_resolution()      3-tier CrewOutput fallback
                                 ├─ policy disagreement check (logs; never overrides)
                                 └─ FileResolutionStore.save
```

---

## Design decisions

### One slice, not two

`support_triage` is a single slice rather than separate `triage/` and `resolution/` slices.
Scoring a ticket and answering it are one business capability — they share a schema, a
threshold, and a single sequential run — and a two-agent crew does not earn the ceremony of a
boundary between them.

The layout is chosen so a *second* slice is purely additive: a new folder under `features/`,
a router registered in `api/app.py`, and nothing else edited. Slices do not import each
other; anything genuinely shared moves down into `core/`.

### Ports and adapters

`features/support_triage/ports.py` declares three Protocols — `TicketSource`,
`TriagePipeline`, `ResolutionStore`. The application layer depends only on these, never on
Jira, the filesystem, or crewAI.

What that buys is concrete: the entire use case, the JSON API and the rendered console are
exercised in tests with no network and no API key. Without the seam, none of that is
testable without either mocking crewAI internals or spending real LLM calls.

`TicketSource` carries one unusual contract, spelled out in its docstring: **implementations
report failure as a returned string, not an exception.** The crewAI tool that wraps it hands
the return value straight to the agent, and an agent that sees `Failed to fetch…` as tool
output can say so in its answer. Raising would abort the run instead. (This is also the
subject of an open defect — see item 5 in `BACKEND_IMPROVEMENTS.md`: the error string is
currently indistinguishable from real ticket text.)

### Settings are read on call, not import

`core/settings.py` is the only module that touches the environment. It exposes a
pydantic-settings `Settings` object behind `get_settings()`, cached with `lru_cache`, so
`.env` is parsed once — **when first called, never at import time**.

This replaced a real hazard. The crew used to build its `LLM(...)` objects as *class-body
attributes*, so `os.getenv` ran when `crew.py` was imported. Correctness then depended on an
import-ordering taboo maintained by hand — never import the crew at module scope, or the
models would be constructed before `.env` was loaded — and it failed only when `.env` was the
sole source of the keys, which is exactly the case that is hard to notice.

The LLMs are now built by `core/llm.py:build_llm` inside the `@agent` methods, so the
environment is read when a crew is *constructed*. Any module may be imported at module scope,
in any order.

`settings.py` also calls `load_dotenv()`. That is deliberate and not redundant: the provider
SDKs underneath LiteLLM read `OPENAI_API_KEY` / `GEMINI_API_KEY` straight from `os.environ`,
while pydantic-settings' `env_file` support populates the `Settings` object without touching
`os.environ`. Both mechanisms are needed.

### The escalation threshold has one home

`ESCALATION_THRESHOLD` is written down exactly once, in
`features/support_triage/domain/policy.py`. From there it reaches four places:

- **the prompt** — `adapters/crewai_pipeline/config/tasks.yaml` carries an
  `{escalation_threshold}` placeholder that `CrewAITriagePipeline` fills from the `kickoff()`
  inputs dict;
- **the score calibration** — `domain/models.py` builds the severity-floor sentence of the
  `frustration_score` field description from the same constant;
- **the console gauge** — `web/routes.py` passes it into the template;
- **`GET /api/v1/config`** — so a client can render a verdict consistently with the backend.

It used to be typed in three of those independently, kept in sync by a comment asking a human
to remember. Never type the number anywhere else.

### Escalation stays prompt-encoded

No Python branch enforces the threshold. The rule is prose in the `resolution_task`
description; changing the *rule* means editing that prose, changing the *number* means editing
`policy.py`.

This is a choice, not an omission. A code-level rule would remove the model's ability to
escalate a calm-but-catastrophic ticket — a data-loss report written politely — which is
judgment worth keeping.

What the code does instead is *notice*: `ResolveTicketUseCase._warn_on_policy_disagreement`
compares the returned `resolution_status` against `policy.should_escalate(frustration_score)`
and logs a warning when they disagree, naming the ticket, the score, the threshold and what
the model returned. It deliberately does not override. A silent false-negative on escalation
is the worst output this system can produce, and a log line is the cheapest way to find out
it happened without taking the judgment away.

### Field descriptions are prompt, not documentation

`domain/models.py` binds `TicketTriageResult` and `TechnicalResolutionResult` to the tasks via
`output_json=`. That means every `Field(description=...)` string is fed to the model as part
of its instructions — the tier ladder in `frustration_score` is the only signal the LLM gets
about what a 4 means versus a 7.

So scoring behavior is tuned *there*, alongside the Pydantic constraints that bound it:
`ge=1, le=10` on both score declarations and a closed `ResolutionStatus` enum. Both exist
because the model was previously free to return `85`, or to invent status vocabulary —
`resolved`, `drafted`, `escalated` — that the consumers silently misread.

Three files move together when behavior changes, all under
`adapters/crewai_pipeline/config/` except the last: `agents.yaml` (keyed by `@agent` method
name), `tasks.yaml` (keyed by `@task` method name), and `domain/models.py`.

### The wire contract is separate from the domain schema

`features/support_triage/api/dto.py` defines its own models rather than re-exporting the
domain ones.

The reason is the previous section: the domain schemas *are prompt*, and they will keep
changing as calibration is tuned. An API contract that is literally the same object changes
with them, and every client breaks on a prompt-engineering tweak. Keeping them separate lets
`/api/v1` hold still and be versioned on its own schedule. That is the seam that makes it safe
to point a future SPA at the API.

`ResolutionResponse` also exposes `escalated` as a boolean mirror of `resolution_status`, so
no client ever string-compares the status itself.

### Persistence lives outside the crew

Results are written by `adapters/file_resolution_store.py`, not by the crewAI task's
`output_file=` parameter.

`output_file=` took a *relative* path, which meant results landed wherever the process
happened to be started — hence a former instruction to always run from the repository root.
`FileResolutionStore` takes its directory from `Settings.resolved_output_dir`, which anchors
relative values to the repository root. Same filenames, same JSON, no CWD coupling.

It also puts the write behind a port, which is what makes `InMemoryResolutionStore` possible
in tests and what makes `GET /api/v1/resolutions/{ticket_id}` a two-line handler.

### crewAI is imported lazily, and warmed in the background

`api/deps.py` imports `CrewAITriagePipeline` *inside* `get_resolve_ticket_use_case()` rather
than at module scope.

This is a latency decision, not a correctness one — the import race described above is gone.
Importing the crew pulls in crewai → litellm, chromadb, openai and pyvis: roughly ten seconds
of module loading, against well under a tenth of a second to actually build the crew object.
Doing that at import time would delay the server binding its port.

Instead `api/app.py:lifespan` starts a daemon thread that performs the import while the
operator is still typing, and `/health` reports `crew_warm` so a slow first request is
explainable rather than mysterious. A submit arriving mid-import simply blocks on the same
import lock and is no worse off.

The CLI is unaffected: every `uv run run_crew` is a fresh process with no warm state to prime.

### Errors map to status codes in one place

`core/errors.py` defines the vocabulary — `AppError` and its subclasses `InvalidTicketKey`,
`PipelineError`, `ResolutionNotFound` — and `api.app._register_exception_handlers` maps them
once:

| Exception | Status |
| --- | --- |
| `InvalidTicketKey` | 422 |
| `ResolutionNotFound` | 404 |
| `PipelineError` | 502 |

API route handlers therefore contain no `try`/`except` at all. The web router is the
deliberate exception: it catches `AppError` itself, because it owes the operator rendered HTML
rather than JSON.

---

## Client surfaces

### JSON API

`/api/v1`, defined in `features/support_triage/api/routes.py`:

| Method | Path | Notes |
| --- | --- | --- |
| `POST` | `/api/v1/resolutions` | `{"ticket_id": "..."}`; runs the crew live, ~30s |
| `GET` | `/api/v1/resolutions/{ticket_id}` | last stored result, 404 if none |
| `GET` | `/api/v1/config` | threshold, score bounds, legal statuses |
| `GET` | `/health` | liveness + `crew_warm` |

Handlers are sync `def`. That is load-bearing: FastAPI runs sync handlers in its threadpool,
so the ~30s blocking crew run does not stall the event loop or other requests.

### Web console

`src/customer_support_crew/web/` — FastAPI with server-rendered Jinja. No build step and **no
external assets**: no CDN, no npm, `static/app.css` is the whole stylesheet, and the only
JavaScript is a dozen inline lines that swap in the "running" state on submit. That is worth
preserving — it means the console works offline and `uv run serve` is the entire toolchain.

- `POST /resolve` runs the crew **live** on every submit; it never reads cached
  `output/*.json`.
- The console calls the use case directly, not its own HTTP API. It is a peer of the API, not
  a layer on top of it — so it keeps working if the API is ever unmounted, and there is no
  self-request round-trip.
- The frustration gauge is the one deliberately expressive element; the rest of the page stays
  quiet. If you add UI, add it quietly.

### CLI

`cli/console.py`, exposed as `run_crew` / `customer_support_crew`. `main.py` remains as a
one-line shim so `crewai run` keeps working.

## Outputs

`output/final_resolution__<TICKET_ID>.json` is written per run by `FileResolutionStore` and is
**committed to the repo** as example data — it is how score calibration is measured across
changes (see item 2 in `BACKEND_IMPROVEMENTS.md`). Running the crew on an existing ticket ID
overwrites its file, from any client. The path is anchored to the repository root, so the
working directory does not matter.

## Testing strategy

`tests/` — pytest, no network and no API key, which is a direct consequence of `ports.py`.

- `tests/conftest.py` holds the fakes: `FakeTriagePipeline`, `InMemoryResolutionStore`,
  `FakeTicketSource`, plus a `make_result` builder for both verdict shapes.
- API and console tests build the app with `create_app()` per test and swap the use case
  through `app.dependency_overrides[get_resolve_ticket_use_case]`, so overrides cannot leak
  between tests.
- `TestClient` is constructed **without** `with`. Using the context manager runs the lifespan,
  which starts the crewAI warm-up import — ten seconds, and a dependency these tests exist to
  avoid.

Coverage is aimed at the things that decide whether a human sees a ticket: the three-tier
`CrewOutput` fallback including its validation-failure path, key normalization, the
policy-disagreement warning, the store round-trip, the status-code mapping, and both console
verdict branches.

## Extending it

| You want to add | Put it in |
| --- | --- |
| A new API endpoint for triage | `features/support_triage/api/routes.py`, with its shapes in `dto.py` |
| A new agent tool | `adapters/crewai_pipeline/tools.py`, delegating to a port — not calling an SDK directly |
| A different ticket source (Zendesk, a CSV) | A new class implementing `TicketSource`, wired in `api/deps.py`; nothing else changes |
| A different store (Postgres, S3) | A new class implementing `ResolutionStore`, wired in `api/deps.py` |
| A change to scoring behavior | `domain/models.py` field descriptions, and `adapters/crewai_pipeline/config/tasks.yaml` if the task prose refers to them |
| A change to the escalation number | `domain/policy.py`, and nowhere else |
| Config shared by every slice | `core/settings.py` |
| A second business capability | A new folder under `features/`, plus one `include_router` call in `api/app.py` |
