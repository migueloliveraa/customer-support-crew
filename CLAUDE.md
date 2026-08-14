# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A [crewAI](https://crewai.com) crew that triages Atlassian Jira support tickets: it fetches a ticket, scores customer frustration 1–10, then either drafts a customer reply or escalates to a human. It ships three clients over the same use case — a JSON API, a server-rendered web console, and a CLI. Python `>=3.10,<3.14`, managed with `uv`.

## Commands

```bash
crewai install                    # lock + install dependencies (uv under the hood)
uv sync --group dev               # add pytest + httpx for the test suite
uv run serve                      # console + API on http://127.0.0.1:8000
crewai run                        # run the crew from the CLI on the default ticket
uv run run_crew CREWAISUP-3       # CLI run on a specific ticket key
uv run pytest                     # the suite; no network, no API key needed
```

There is no linter and no build step. `crewai train` / `crewai replay` / `crewai test` are not supported — the console scripts they shell out to were removed, because the `main:train` / `main:replay` / `main:test` functions they pointed at never existed.

## Environment

`.env` (gitignored) is read by `core/settings.py`, which is the only module that touches the environment. It defines:

- `TRIAGE_MODEL`, `RESOLVER_MODEL` — LiteLLM-style model strings (defaults `openai/gpt-4o-mini` and `gemini/gemini-2.0-flash`); optional `TRIAGE_TEMPERATURE`, `RESOLVER_TEMPERATURE`
- `OPENAI_API_KEY`, `GEMINI_API_KEY` — whichever the two models need. These are read by the provider SDKs from `os.environ`, which is why `settings.py` calls `load_dotenv()` as well as declaring typed fields
- `JIRA_SERVER_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN` — Atlassian Cloud basic auth
- `OUTPUT_DIR` — optional; relative values resolve against the repository root, not the CWD

Settings are read when `get_settings()` is first *called*, never at import. There is no import-ordering hazard: any module may be imported at module scope, in any order.

## Architecture

One vertical slice, `features/support_triage/`, with a ports-and-adapters interior. Everything outside the slice is either shared plumbing (`core/`) or a client of it (`api/`, `web/`, `cli/`).

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

Request flow, identical for all three clients:

```
POST /api/v1/resolutions  ─┐
POST /resolve (HTML form) ─┼→ ResolveTicketUseCase.execute(ticket_id)
uv run run_crew KEY       ─┘     ├─ normalize_ticket_id      (fails before spending an LLM call)
                                 ├─ CrewAITriagePipeline.run  triage_task → resolution_task
                                 │    └─ to_resolution()      3-tier CrewOutput fallback
                                 ├─ policy disagreement check (logs; never overrides)
                                 └─ FileResolutionStore.save
```

### Rules that matter

**The escalation threshold is written down once**, in `features/support_triage/domain/policy.py`. From there it reaches the prompt (`tasks.yaml` uses a `{escalation_threshold}` placeholder that `CrewAITriagePipeline` fills via `kickoff()` inputs), the severity floor in the `frustration_score` field description, the console gauge, and `GET /api/v1/config`. Never type `7` anywhere else.

**Escalation stays prompt-encoded.** No Python branch enforces it; changing the *rule* means editing the prose in `tasks.yaml`, changing the *number* means editing `policy.py`. The use case logs a warning when the model's `resolution_status` disagrees with the threshold, but deliberately does not override it.

**Field descriptions are prompt, not documentation.** `domain/models.py` binds its models via `output_json=`, so the `Field(description=...)` text is the only calibration signal the LLM gets about what a 4 means versus a 7. Tighten scoring behavior there (and with Pydantic constraints, which are already in place: `ge=1, le=10` and a closed `ResolutionStatus` enum).

**Three files stay in sync when changing behavior**: `adapters/crewai_pipeline/config/agents.yaml` (keyed by `@agent` method name), `config/tasks.yaml` (keyed by `@task` method name), and `domain/models.py`.

**Build LLMs inside `@agent` methods, never in the class body.** That is what makes `crew.py` safe to import at module scope.

**`JiraTicketSource.fetch` returns errors as strings rather than raising**, so the agent sees the failure as tool output and keeps going. Preserve that.

**`api/deps.py` imports crewAI lazily**, inside `get_resolve_ticket_use_case()`. Not for correctness any more — purely so the server binds its port immediately and the ~10s crewai/litellm import happens on the background warm-up thread instead (see `api/app.py:lifespan`, and `/health`'s `crew_warm` flag).

**Errors map to status codes in one place**, `api.app._register_exception_handlers`: `InvalidTicketKey` → 422, `ResolutionNotFound` → 404, `PipelineError` → 502. Route handlers do not catch. The web router is the exception — it catches `AppError` itself because it owes the operator rendered HTML, not JSON.

## Web console

`src/customer_support_crew/web/` — FastAPI, server-rendered Jinja, no build step and **no external assets** (no CDN, no npm); `static/app.css` is the whole stylesheet and the only JavaScript is a dozen inline lines that swap in the "running" state on submit. Keep it that way unless there's a reason not to: it means the console works offline and `uv run serve` is the entire toolchain.

- `POST /resolve` runs the crew **live** on every submit — it never reads cached `output/*.json`. The handler is a **sync** `def` on purpose, so FastAPI runs the ~30s blocking call in its threadpool instead of stalling the event loop. Same for the API handlers.
- The console calls the use case directly, not its own HTTP API. It is a peer of the API, not a layer on top of it.
- The gauge is the one deliberately expressive element; the rest of the page stays quiet. If you add UI, add it quietly.

## JSON API

`/api/v1`, defined in `features/support_triage/api/routes.py`:

| Method | Path | Notes |
| --- | --- | --- |
| `POST` | `/api/v1/resolutions` | `{"ticket_id": "..."}`; runs the crew live, ~30s |
| `GET` | `/api/v1/resolutions/{ticket_id}` | last stored result, 404 if none |
| `GET` | `/api/v1/config` | threshold, score bounds, legal statuses |
| `GET` | `/health` | liveness + `crew_warm` |

`api/dto.py` is a *separate* set of models from `domain/models.py`, on purpose: the domain schemas are prompt and will churn as calibration is tuned, while the wire contract should be able to hold still and be versioned. That separation is what makes it safe to point a future SPA at `/api/v1`.

## Outputs

`output/final_resolution__<TICKET_ID>.json` is written per run by `FileResolutionStore` and is **committed to the repo** as example data. Running the crew on an existing ticket ID overwrites its file, from any client. The path is anchored to the repository root, so it does not matter what directory you run from.

## Tests

`tests/` — pytest, no network and no API key. `tests/conftest.py` holds fakes for the three ports; API and console tests build the app with `create_app()` and swap the use case via `dependency_overrides`. Construct `TestClient` *without* `with`, so the lifespan (and its crewAI warm-up import) does not run.

## Changelog rule

**Every change to this repository gets an entry in `CHANGELOG.md`** — add it as part of the same change, not afterwards.

- Write under `## [Unreleased]`, in the `Added` / `Changed` / `Fixed` / `Removed` subsection that fits ([Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format). Create the subsection if it isn't there.
- Summarize the change and **why** it was made, in prose a teammate can read months later. Name the files or entry points that moved. Do not paste diffs, and do not restate what `git log` already shows.
- One entry per meaningful change, not one per file touched. Trivial edits (a typo, a comment) don't need one.
- Skip it only if the user explicitly says so.
