# Getting started

From a clean checkout to a triaged ticket. For what the system *is*, start at
[README.md](README.md).

## Requirements

- Python `>=3.10,<3.14`
- [`uv`](https://docs.astral.sh/uv/) — dependency management and the console scripts
- An API key for each model you use (OpenAI and Google by default)
- Atlassian Jira Cloud credentials, if you want to fetch real tickets

## Install

```bash
pip install uv          # if you do not have it
crewai install          # lock + install dependencies (uv under the hood)
uv sync --group dev     # pytest + httpx, for the test suite
```

## Configure

Create a `.env` at the repository root:

```ini
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=...

JIRA_SERVER_URL=https://your-org.atlassian.net
JIRA_EMAIL=you@your-org.com
JIRA_API_TOKEN=...
```

That is the minimum. Every variable, including the optional ones, is documented in
[CONFIGURATION.md](CONFIGURATION.md).

`.env` is gitignored. Never commit it.

## Run

```bash
uv run serve                  # web console + JSON API on http://127.0.0.1:8000
uv run run_crew CREWAISUP-3   # one ticket from the CLI
crewai run                    # same, on the default ticket
uv run pytest                 # the test suite (no network, no API key)
```

A run takes **roughly 30 seconds** — two sequential LLM calls plus a Jira fetch.

The first request after `uv run serve` may be slower still: importing crewAI pulls in
litellm, chromadb, openai and pyvis. A background thread starts that import at startup, and
`GET /health` reports `crew_warm` so you can tell whether it has finished.

## Verify it works

With the server running:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/api/v1/config
curl -X POST http://127.0.0.1:8000/api/v1/resolutions \
     -H 'Content-Type: application/json' \
     -d '{"ticket_id":"CREWAISUP-3"}'
```

Or open <http://127.0.0.1:8000> and submit a ticket key in the console.

Interactive API docs are at <http://127.0.0.1:8000/docs>.

## Where results go

Each run writes `output/final_resolution__<TICKET_ID>.json`, **anchored to the repository
root** regardless of which directory you started from. Re-running the same ticket key
overwrites its file, from any client.

Those files are committed to the repo on purpose — they are the example data used to judge
whether a change to scoring calibration made things better or worse.

## Not supported

`crewai train`, `crewai replay` and `crewai test` do not work here. The console scripts they
shell out to were removed, because the `main:train` / `main:replay` / `main:test` functions
they pointed at never existed.

There is no linter and no build step.

## What to read next

- [CREW.md](CREW.md) — change what the agents do: prompts, scoring calibration, models
- [CONVENTIONS.md](CONVENTIONS.md) — the rules to follow before editing code
- [ARCHITECTURE.md](ARCHITECTURE.md) — how the pieces fit, and why
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — when something misbehaves

## crewAI support

- [crewAI documentation](https://docs.crewai.com)
- [GitHub repository](https://github.com/joaomdmoura/crewai)
- [Discord](https://discord.com/invite/X4JWnZnxPb)
