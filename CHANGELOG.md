# Changelog

Summarized, human-readable notes on what changed and why. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Newest first.

## [Unreleased]

### Added

- **Web console at `http://127.0.0.1:8000`** (`src/customer_support_crew/web/`) — FastAPI +
  Jinja templates, server-rendered, no build step and no external assets. One field for a
  Jira key, one button, and the resolution rendered as a verdict with a frustration gauge
  that shows where the score landed against the escalation threshold. Runs the crew live on
  submit; nothing is read from cached `output/*.json`.
- **`serve` console script** — `uv run serve` starts uvicorn on port 8000.
- **`src/customer_support_crew/pipeline.py`** — `run_pipeline(ticket_id)` is now the single
  callable both the CLI and the web app use. It loads `.env` before importing `crew.py`
  (whose class-body `LLM(...)` objects read `os.getenv` at import time), validates the Jira
  key shape before spending an LLM call, and owns the three-tier output extraction.
- **`CHANGELOG.md`** and a rule in `CLAUDE.md` requiring an entry per change.
- **`BACKEND_IMPROVEMENTS.md`** — a prioritized backlog of backend defects and improvements,
  written because the pipeline's business rules (the 1–10 frustration scale, the escalation
  threshold, the legal outcome statuses) live entirely in prose with no Python validating
  that the model obeyed them. The audit found this is already producing wrong output: the
  committed `output/*.json` examples contain three different spellings of the drafted status
  (`resolved`, `drafted`, `resolved_draft`) while `main.py` and the web template branch only
  on `escalated_to_human`, so a stray escalation spelling would silently render as a drafted
  reply. Documents fifteen items across `config/schemas.py`, `config/tasks.yaml`,
  `tools/jira_tool.py`, and `pipeline.py`, ordered by severity with a suggested sequencing.
  No code changed — this is analysis only.

### Changed

- **`main.py` accepts a ticket key as its first CLI argument** instead of only using the
  hardcoded `CREWAISUP-10`, which remains the default. Its crew-running and output-parsing
  logic moved to `pipeline.py`; it is now just the CLI presentation layer.
- **Errors surface instead of being swallowed.** `run_pipeline` raises `InvalidTicketKey` or
  `PipelineError`; the bare `except` that printed `[FATAL ERROR]` and returned `None` now
  lives only at the CLI boundary, and the web app renders the failure.
- **Dependencies**: added `fastapi`, `uvicorn`, `jinja2`, `python-multipart`, `python-dotenv`.

### Fixed

- **`resolution_status` is now a closed enum** (`ResolutionStatus` in `config/schemas.py`)
  instead of a free-form `str`. It was a plain string whose only definition of the legal
  values lived in a `Field` description the model was free to ignore — and it did: the
  committed examples held `resolved`, `drafted`, and `escalated_to_human`, three spellings
  for two outcomes. Both consumers (`main.py`, `web/templates/index.html`) tested only
  `== 'escalated_to_human'`, so any other spelling of the escalated case would have fallen
  through to the drafted branch and shown a "Reply drafted" verdict with an empty body for a
  ticket that had actually been escalated to a human. Pydantic now rejects anything outside
  the two values, and the enum constraint reaches the model through the JSON schema that
  `output_json=` already passes it. Supporting changes: `config/tasks.yaml` states both
  literals verbatim and forbids synonyms (the prose is the model's primary signal);
  `pipeline.py` re-exports `ResolutionStatus` so neither consumer hand-types the string, and
  dumps with `mode="json"` to keep the persisted files plain strings; `web/app.py` computes
  the `escalated` flag and passes it to the template, which no longer does the comparison in
  Jinja. The three non-conforming `output/*.json` examples had their status field corrected
  in place — the scores and email bodies were valid and are untouched.
