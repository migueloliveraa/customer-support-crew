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

- **crewAI's anonymous telemetry is now off by default.** Every crew run POSTed
  OpenTelemetry spans to `telemetry.crewai.com:4319`; when a firewall or antivirus blocks
  that connection the exporter retries with backoff and floods the logs with
  `Transient error ... retrying in 6.46s` / `Failed to export span batch`, which is noise
  in the CLI and in the web console's server output. `pipeline.py` sets
  `CREWAI_DISABLE_TELEMETRY` right after `load_dotenv()` — before the lazy `crew.py` import,
  since crewAI reads the flag when it builds its `Telemetry` singleton — using `setdefault`
  so an explicit value in `.env` or the shell still wins for anyone who wants the traces.

- **`frustration_score` is now bounded and calibrated.** It is the number the whole pipeline
  turns on — `>= 7` sends a ticket to a human — and it was a plain `int` whose only guidance
  was the phrase "scaled integer from 1 to 10". Nothing stopped a model returning `0`, `85`,
  or `-3`, and one adjective was the entire basis for deciding what a 4 means versus a 7. The
  committed examples showed 7 of 10 tickets escalating, four at 9–10, which is the ceiling
  compression an unanchored 1–10 rating produces. Both declarations in `config/schemas.py`
  now carry `ge=1, le=10`, and the triage field description carries an explicit tier ladder
  (1–3 informational, 4–6 blocked but civil, 7–8 anger or stated business impact, 9–10 churn
  or legal threat) plus a severity floor: data loss, a security breach, an unauthorized
  charge, or a total outage never scores below 7 regardless of how politely it is written,
  which closes the calm-but-catastrophic blind spot. `config/tasks.yaml` points the agent at
  those tiers rather than restating them, so there is one copy to keep current.
- **The score is now copied rather than re-derived.** `TechnicalResolutionResult` re-stated
  `frustration_score` with no instruction to preserve it, and the escalation decision is made
  on the resolver's copy while triage's is discarded — so a resolver silently re-scoring a 9
  down to a 5 would produce an auto-draft with no record that the number moved. The field
  description and `resolution_task` prose now require a verbatim copy.
- **New `score_rationale` field** — required at triage (quote the phrase that drove the score),
  optional on the resolution schema so it carries through to `output/*.json` without
  invalidating the existing examples. Miscalibration was previously invisible after the fact.
- **`extract_result` now validates its fallback tiers.** Only tier 1 (`crew_output.pydantic`)
  went through Pydantic; tiers 2 (`json_dict`) and 3 (`json.loads(.raw)`) returned raw dicts,
  so the new bounds and the status enum would not have applied to anything arriving by those
  paths. Both now go through `TechnicalResolutionResult` and raise `PipelineError` on failure.
  **Behavior change:** degraded output that previously rendered as blanks now surfaces as a
  visible error in the CLI and the console's "Run stopped" panel. This also closes the
  validation half of backlog item 8.
- **Gauge tolerates a bad score.** `web/templates/index.html` only marks cells for a score
  within 1–10, so a stray value degrades to an empty bar instead of a misleadingly full one.

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
