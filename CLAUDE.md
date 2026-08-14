# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A [crewAI](https://crewai.com) crew that triages Atlassian Jira support tickets: it fetches a ticket, scores customer frustration 1–10, then either drafts a customer reply or escalates to a human. It ships three clients over the same use case — a JSON API, a server-rendered web console, and a CLI. Python `>=3.10,<3.14`, managed with `uv`.

**How it is put together and why → [`ARCHITECTURE.md`](ARCHITECTURE.md). Known defects and the open backlog → [`BACKEND_IMPROVEMENTS.md`](BACKEND_IMPROVEMENTS.md).** Read the first before changing structure; check the second before "fixing" something that is already a tracked item.

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

## Invariants

Break one of these and something goes wrong quietly. Each links to the reasoning.

- **Never type the escalation threshold anywhere but `domain/policy.py`.** It reaches the prompt, the score calibration, the gauge and `/api/v1/config` from there. ([why](ARCHITECTURE.md#the-escalation-threshold-has-one-home))
- **Do not add a Python branch that enforces escalation.** The rule is prose in `tasks.yaml`; the use case logs disagreement and honors the model. ([why](ARCHITECTURE.md#escalation-stays-prompt-encoded))
- **Treat `Field(description=...)` in `domain/models.py` as prompt.** It is the model's only scoring calibration; tune behavior there, with the `ge`/`le` bounds and the closed `ResolutionStatus` enum. ([why](ARCHITECTURE.md#field-descriptions-are-prompt-not-documentation))
- **Keep `agents.yaml`, `tasks.yaml` and `domain/models.py` in sync.** YAML keys must match the `@agent` / `@task` method names. ([why](ARCHITECTURE.md#field-descriptions-are-prompt-not-documentation))
- **Build LLMs inside `@agent` methods, never in a class body.** ([why](ARCHITECTURE.md#settings-are-read-on-call-not-import))
- **`JiraTicketSource.fetch` returns errors as strings; never make it raise.** ([why](ARCHITECTURE.md#ports-and-adapters))
- **The application layer depends on `ports.py`, never on Jira, the filesystem or crewAI.** New integrations are new adapters wired in `api/deps.py`. ([why](ARCHITECTURE.md#ports-and-adapters))
- **Keep `api/dto.py` separate from `domain/models.py`** — do not "simplify" it into a re-export. ([why](ARCHITECTURE.md#the-wire-contract-is-separate-from-the-domain-schema))
- **Keep the crewAI import lazy in `api/deps.py`.** ([why](ARCHITECTURE.md#crewai-is-imported-lazily-and-warmed-in-the-background))
- **API route handlers do not catch**; errors map to status codes in `api.app`. The web router catching `AppError` is the one deliberate exception. ([why](ARCHITECTURE.md#errors-map-to-status-codes-in-one-place))
- **Handlers stay sync `def`.** A ~30s blocking run belongs in FastAPI's threadpool. ([why](ARCHITECTURE.md#json-api))
- **Keep the console no-build**: no CDN, no npm, `static/app.css` is the whole stylesheet, and the console calls the use case directly rather than its own API. ([why](ARCHITECTURE.md#web-console))
- **Write results through `ResolutionStore`, not a relative path.** ([why](ARCHITECTURE.md#persistence-lives-outside-the-crew))
- **Construct `TestClient` without `with`**, or the lifespan drags crewAI into the test run. ([why](ARCHITECTURE.md#testing-strategy))

## Changelog rule

**Every change to this repository gets an entry in `CHANGELOG.md`** — add it as part of the same change, not afterwards.

- Write under `## [Unreleased]`, in the `Added` / `Changed` / `Fixed` / `Removed` subsection that fits ([Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format). Create the subsection if it isn't there.
- Summarize the change and **why** it was made, in prose a teammate can read months later. Name the files or entry points that moved. Do not paste diffs, and do not restate what `git log` already shows.
- One entry per meaningful change, not one per file touched. Trivial edits (a typo, a comment) don't need one.
- Skip it only if the user explicitly says so.
