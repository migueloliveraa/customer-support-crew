# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A [crewAI](https://crewai.com) crew that triages Atlassian Jira support tickets: it fetches a ticket, scores customer frustration 1–10, then either drafts a customer reply or escalates to a human. Python `>=3.10,<3.14`, managed with `uv`.

## Commands

```bash
crewai install                    # lock + install dependencies (uv under the hood)
uv run serve                      # web console on http://127.0.0.1:8000
crewai run                        # run the crew from the CLI on the default ticket
uv run run_crew CREWAISUP-3       # CLI run on a specific ticket key
```

Run everything **from the repository root**: `output_file` in `crew.py` is a relative path, so the CWD decides where results land.

There is no test suite (`tests/` is empty), no linter, and no build step. Note that `pyproject.toml` declares `train`, `replay`, and `test` console scripts pointing at `main:train`/`main:replay`/`main:test`, but **those functions do not exist in `main.py`** — those scripts (and `crewai train` / `crewai replay` / `crewai test`, which shell out to them) will fail until they are written.

## Environment

`.env` (gitignored) must define:

- `TRIAGE_MODEL`, `RESOLVER_MODEL` — LiteLLM-style model strings (defaults `openai/gpt-4o-mini` and `gemini/gemini-2.0-flash`)
- `OPENAI_API_KEY`, `GEMINI_API_KEY` — whichever the two models above need
- `JIRA_SERVER_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN` — Atlassian Cloud basic auth for the fetcher tool

The two `LLM(...)` objects in `crew.py` are **class-body attributes**, so `os.getenv` runs at import time. Env vars must be present before `SupportOrchestrationCrew` is imported. `pipeline.py` handles this for every caller: it calls `load_dotenv()` at module scope and imports `crew.py` *lazily inside* `run_pipeline()`. **Never add a top-level `from customer_support_crew.crew import ...` to `pipeline.py` or the web app** — that reintroduces the race, and it fails only when `.env` is the sole source of the keys.

## Architecture

Sequential two-agent pipeline (`Process.sequential`), assembled by the `@CrewBase`-decorated `SupportOrchestrationCrew` in `src/customer_support_crew/crew.py`. Agent/task prose lives in YAML; Python only wires LLMs, tools, and output schemas.

```
pipeline.run_pipeline(ticket_id)      ← CLI (main.py) and web (web/app.py) both call this
  └─ triage_task     → triage_agent (triage_llm, JiraTicketFetcherTool)
                       output_json = TicketTriageResult
       └─ resolution_task → technical_resolver (resolver_llm)
                       context = [triage_task]
                       output_json = TechnicalResolutionResult
                       output_file = output/final_resolution__{ticket_id}.json
```

Three files must stay in sync when changing behavior:

1. **`config/agents.yaml`** — role/goal/backstory, keyed by the method name of each `@agent` in `crew.py`.
2. **`config/tasks.yaml`** — description/expected_output, keyed by each `@task` method name. Task descriptions interpolate `{ticket_id}` from the `inputs` dict passed to `kickoff()`. `resolution_task` declares `context: [triage_task]`, which is how triage output reaches the resolver.
3. **`config/schemas.py`** — Pydantic models bound via `output_json=`, which force structured output.

**The escalation threshold is prompt-encoded, not code-encoded.** `frustration_score >= 7` → `escalated_to_human` is stated only in the `resolution_task` description in `tasks.yaml`; no Python branch enforces it. Changing the threshold means editing that prose, not adding an `if`.

Scoring itself is likewise unconstrained: `TicketTriageResult.frustration_score` is a plain `int` whose `Field(description=...)` just says "scaled integer from 1 to 10" — there are no `ge`/`le` bounds and no per-tier calibration anchors, so the model is free to return out-of-range values. Field descriptions are the only calibration signal the LLM gets, so tightening scoring behavior is done there (and/or with Pydantic constraints), in `config/schemas.py`.

**Model split is deliberate**: a cheap fast model for triage (`temperature=0.2`), a stronger reasoning model for resolution (`temperature=0.5`).

`tools/jira_tool.py` is a `BaseTool` subclass with a Pydantic `args_schema`. It returns errors as *strings* rather than raising, so the agent sees the failure as tool output and keeps going — preserve that behavior when editing.

`pipeline.extract_result()` has a three-tier fallback (`crew_output.pydantic` → `.json_dict` → `json.loads(.raw)`) because crewAI does not consistently populate the parsed fields. It returns a plain `dict`, which is what both the CLI and the templates consume.

`knowledge/user_preference.txt` is unused scaffolding from the crewAI project template.

## Web console

`src/customer_support_crew/web/` — FastAPI, server-rendered Jinja, no build step and **no external assets** (no CDN, no npm); `static/app.css` is the whole stylesheet and the only JavaScript is a dozen inline lines that swap in the "running" state on submit. Keep it that way unless there's a reason not to: it means the console works offline and `uv run serve` is the entire toolchain.

- `POST /resolve` runs the crew **live** on every submit — it never reads cached `output/*.json`. The handler is a **sync** `def` on purpose, so FastAPI runs the ~30s blocking call in its threadpool instead of stalling the event loop.
- `ESCALATION_THRESHOLD` in `pipeline.py` is **display only** — it draws the threshold on the gauge. The rule that actually escalates is prose in `tasks.yaml`. Change one, change the other.
- The gauge is the one deliberately expressive element; the rest of the page stays quiet. If you add UI, add it quietly.

## Outputs

`output/final_resolution__<TICKET_ID>.json` is written per run and is **committed to the repo** as example data. Running the crew on an existing ticket ID overwrites its file, from the CLI or the web console alike.

## Changelog rule

**Every change to this repository gets an entry in `CHANGELOG.md`** — add it as part of the same change, not afterwards.

- Write under `## [Unreleased]`, in the `Added` / `Changed` / `Fixed` / `Removed` subsection that fits ([Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format). Create the subsection if it isn't there.
- Summarize the change and **why** it was made, in prose a teammate can read months later. Name the files or entry points that moved. Do not paste diffs, and do not restate what `git log` already shows.
- One entry per meaningful change, not one per file touched. Trivial edits (a typo, a comment) don't need one.
- Skip it only if the user explicitly says so.
