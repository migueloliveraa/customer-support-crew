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

### Changed

- **`main.py` accepts a ticket key as its first CLI argument** instead of only using the
  hardcoded `CREWAISUP-10`, which remains the default. Its crew-running and output-parsing
  logic moved to `pipeline.py`; it is now just the CLI presentation layer.
- **Errors surface instead of being swallowed.** `run_pipeline` raises `InvalidTicketKey` or
  `PipelineError`; the bare `except` that printed `[FATAL ERROR]` and returned `None` now
  lives only at the CLI boundary, and the web app renders the failure.
- **Dependencies**: added `fastapi`, `uvicorn`, `jinja2`, `python-multipart`, `python-dotenv`.
