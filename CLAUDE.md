# CLAUDE.md

Guidance for Claude Code (claude.ai/code) working in this repository.

All project documentation lives in [`docs/`](docs/README.md). This file holds only what an
agent needs that a human reader does not — it deliberately duplicates none of it.

## Before you edit

Read [`docs/CONVENTIONS.md`](docs/CONVENTIONS.md). It lists the invariants; breaking one
fails quietly rather than loudly, and each links to the reasoning in
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

Check [`docs/BACKEND_IMPROVEMENTS.md`](docs/BACKEND_IMPROVEMENTS.md) before "fixing" anything
that looks wrong — it may already be a tracked item with a decided approach.

## Where to look

| Question | Document |
| --- | --- |
| What is this, what does it solve, what do the terms mean | [`docs/README.md`](docs/README.md) |
| How do I install and run it | [`docs/GETTING_STARTED.md`](docs/GETTING_STARTED.md) |
| What goes in `.env` | [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md) |
| How is it structured, and why | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) |
| How do I change agent behavior or scoring | [`docs/CREW.md`](docs/CREW.md) |
| What does the API expose | [`docs/API.md`](docs/API.md) |
| What rules must I follow | [`docs/CONVENTIONS.md`](docs/CONVENTIONS.md) |
| Something is broken | [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md) |
| What is already known to be wrong | [`docs/BACKEND_IMPROVEMENTS.md`](docs/BACKEND_IMPROVEMENTS.md) |

## Commands

```bash
uv sync --group dev               # dev dependencies, needed before pytest
uv run pytest                     # the suite; no network, no API key needed
uv run serve                      # console + API on http://127.0.0.1:8000
uv run run_crew CREWAISUP-3       # one ticket from the CLI
```

`uv run pytest` is the check to run after a change. There is no linter, no formatter and no
build step, so there is nothing else to run.

Do not run `uv run serve` or `uv run run_crew` casually: both spend real LLM tokens and both
block for ~30 seconds per ticket. Prefer the test suite, and ask before making a live run.

`crewai train` / `crewai replay` / `crewai test` do not work here — the entry points they
need never existed.

## Every change gets a CHANGELOG entry

Add it to [`docs/CHANGELOG.md`](docs/CHANGELOG.md) as part of the same change, under
`## [Unreleased]`. The full rule — including what to write and when to skip it — is in
[`docs/CONVENTIONS.md`](docs/CONVENTIONS.md#changelog-rule).

If a change alters behavior a document describes, update that document in the same change too;
the mapping is in [`docs/CONVENTIONS.md`](docs/CONVENTIONS.md#documentation-rule).
