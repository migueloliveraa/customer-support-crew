# Backend Improvements — Prioritized Backlog

Assessment of `src/customer_support_crew/` as of the `frontend-fastapi` branch. Items are
ordered **most critical first**: everything in P0 is a correctness or safety defect that can
produce a wrong decision on a real ticket. P1 is robustness, P2 is quality and operability.

The recurring theme: **the pipeline's business rules live entirely in prose, and nothing in
Python validates that the model obeyed them.** Every P0 below is a variant of that.

---

## P0 — Critical (wrong output reaches the user)

### 1. ~~`resolution_status` is a free-form string, and the model is already getting it wrong~~ — DONE

**Where:** `config/schemas.py:15`, `config/tasks.yaml:8-15`, consumed at
`web/templates/index.html:56` and `main.py:33`.

The field is a plain `str`. Its description names two values (`resolved_draft`,
`escalated_to_human`), but the *task prose* never uses the string `resolved_draft` — it only
says "resolve the ticket by drafting…". The committed example outputs show the model
inventing its own vocabulary:

| Ticket | `resolution_status` returned |
| --- | --- |
| CREWAISUP-1 | `resolved` |
| CREWAISUP-2, -3 | `drafted` |
| CREWAISUP-4…10 | `escalated_to_human` |

Three different values for the same outcome. Nothing rejects them.

**Why it's the top item:** both consumers branch on the escalated value only —
`result.get('resolution_status') == 'escalated_to_human'`. That happens to be stable today,
so the bug is *latent*: the moment the model returns `escalate_to_human`, `ESCALATED`, or
`escalated`, the console renders a green "Reply drafted" verdict with an empty body for a
ticket that was actually escalated. A silent false-negative on escalation is the single worst
failure this system can produce.

**Resolved.** `ResolutionStatus` now closes the set in `config/schemas.py`; `tasks.yaml`
states both literals and forbids synonyms; `pipeline.py` re-exports the enum for `main.py`
and `web/app.py`, which computes `escalated` in Python so the template no longer compares
strings in Jinja; the three non-conforming example outputs were corrected. Original writeup
kept below for the record.

**Fix:** make it a closed enum in `config/schemas.py`, so Pydantic rejects anything else:

```python
from enum import Enum

class ResolutionStatus(str, Enum):
    RESOLVED_DRAFT = "resolved_draft"
    ESCALATED_TO_HUMAN = "escalated_to_human"
```

Then use the literal strings verbatim in the `resolution_task` description in `tasks.yaml`,
and have the template/CLI compare against `ResolutionStatus.ESCALATED_TO_HUMAN.value` rather
than a hand-typed string. Also **regenerate the committed `output/*.json` examples** — they
currently document the broken vocabulary as if it were the contract.

---

### 2. ~~`frustration_score` has no bounds and no calibration anchors~~ — DONE (recalibration run still pending)

**Where:** `config/schemas.py:8` (triage), `:14` (carried through resolution).

`frustration_score: int` with the description "An emotional frustration level scaled integer
from 1 to 10." There is no `ge=1`, no `le=10`. A model returning `0`, `11`, or `85` is
accepted, written to `output/`, and drawn on the gauge — where an out-of-range value renders
as a broken bar.

Worse than the missing bounds is the missing *calibration*. One sentence is the only signal
the model gets about what a 4 means versus a 7, and 7 is exactly the escalation threshold.
The committed examples show **7 of 10 tickets escalating**, with four separate 9–10 scores.
Either the sample is unusually angry or the scale is compressed toward the top — which is
what you'd expect when a model is asked for a 1–10 emotion rating with no anchors. At a 70%
escalation rate the triage step is not buying much: it's a slightly expensive pass-through to
a human.

**Resolved,** except for step 4. Both `frustration_score` declarations carry `ge=1, le=10`; the
triage field description holds the tier ladder plus a severity floor (data loss, security
breach, unauthorized charge, total outage never score below 7 however calm the wording);
`tasks.yaml` points at those tiers instead of duplicating them; `score_rationale` was added
(required at triage, optional on the resolution schema); and the resolver must now copy the
score verbatim rather than re-derive it. `extract_result`'s fallback tiers were also routed
through the schema, without which the bounds would only have applied to tier 1.

**Still open — step 4, the recalibration measurement.** The anchors are expected to pull scores
down, but that has not been measured: it needs live credentials and ten crew runs. Re-run
`CREWAISUP-1` through `-10` and compare against the current **70% escalation rate (7/10, four
at 9–10)**. If the rate has not moved, the ladder wording needs another pass — the threshold is
the wrong dial to reach for. Record the new rate here when you have it.

**Fix, in order of effort:**

1. Add hard bounds — one line, stops the invalid-value class outright:
   ```python
   frustration_score: int = Field(..., ge=1, le=10, description=...)
   ```
2. Put per-tier anchors in the `Field` description, since that description is what the LLM
   actually reads. Roughly: 1–3 neutral/informational request; 4–6 blocked but civil, no
   threat language; 7–8 explicit anger, repeat contact, or business impact stated; 9–10
   churn threat, legal/refund demand, or data loss. Anchors are the highest-leverage change
   in this whole document for output quality.
3. Add a `score_rationale: str` field to `TicketTriageResult` requiring the model to quote
   the ticket text that justified the score. It makes miscalibration auditable instead of
   invisible, and forcing the justification tends to pull scores back toward the middle.
4. Once anchored, re-run the ten sample tickets and check whether the escalation rate is
   defensible. If it isn't, the threshold is the wrong dial to touch — the scale is.

---

### 3. Nothing enforces the escalation threshold in code

**Where:** the rule exists only as prose in `config/tasks.yaml:12-13`; `pipeline.py:17`
holds `ESCALATION_THRESHOLD = 7` and is explicitly marked *display only*.

The resolver model is free to score a ticket 9 and still return a friendly draft reply, or
score it 3 and escalate. Nothing catches the contradiction. The two representations of the
same rule are kept in sync by a code comment asking a human to remember.

Note this is a **deliberate design choice**, documented in `CLAUDE.md` ("The escalation
threshold is prompt-encoded, not code-encoded"). The recommendation is not to move the rule
into Python — that would remove the model's ability to escalate a calm-but-catastrophic
ticket, which is real judgment worth keeping. The recommendation is to add a **post-hoc
consistency check**:

```python
# pipeline.py, after extract_result()
if result["frustration_score"] >= ESCALATION_THRESHOLD and result["resolution_status"] != "escalated_to_human":
    # model contradicted the documented rule — flag it, don't silently ship the draft
```

Decide the policy: either override to escalation (safe default — a needless escalation costs
an agent's time, a missed one costs a customer), or attach a `rule_violation` field the
console renders as a warning band. Either way, `ESCALATION_THRESHOLD` stops being decorative
and becomes the single source of truth the prose is checked against.

---

### 4. The payload/status invariant is never checked

**Where:** `config/schemas.py:16-17`.

`email_response_template` and `internal_escalation_notes` are both `Optional`, independently.
The schema permits all four combinations, including the two that are nonsense: escalated with
no notes, and drafted with no reply. The template already anticipates this and prints "The
crew escalated without leaving notes" — a UI apology for a schema that allows an empty
result.

**Fix:** a `@model_validator(mode="after")` on `TechnicalResolutionResult` asserting that
`escalated_to_human` requires non-empty `internal_escalation_notes` and null
`email_response_template`, and the inverse for `resolved_draft`. Pydantic then rejects the
malformed output and crewAI can retry, instead of writing a hollow JSON file to `output/`.

---

### 5. Jira fetch failures are indistinguishable from real ticket content

**Where:** `tools/jira_tool.py:23`, `:35`.

The tool returns errors as strings — correct, and worth preserving, since it lets the agent
see the failure. But the returned string is plain prose with no marker, so `"Failed to fetch
ticket CREWAISUP-99 from Jira. Error: Issue Does Not Exist"` lands in the agent's context
looking exactly like ticket text. The triage agent's prompt gives it no instruction for this
case, so it will happily categorize the *error message* and assign it a frustration score.
The pipeline then drafts a customer reply about a ticket that does not exist. Nothing
downstream can tell this apart from a successful run.

**Fix:**

- Prefix failures with an unmistakable sentinel (`ERROR: …`) and tell the triage agent in
  `tasks.yaml` what to do when it sees one — set a `fetch_failed: bool` on
  `TicketTriageResult` and stop.
- Have `pipeline.run_pipeline()` raise `PipelineError` when that flag is set, so the CLI and
  console show a real error instead of a fabricated verdict.
- Separate the two failure modes: missing config (`:23`) is an operator problem that should
  fail loudly at startup, not per-tool-call; a 404 or auth rejection is a ticket-level
  problem. They currently look identical.

---

## P1 — Robustness and cost

### 6. A new `JIRA` client is constructed on every tool call

`tools/jira_tool.py:27` builds a fresh `JIRA(...)` inside `_run`. Each construction performs
an authentication round-trip. An agent that retries the fetch pays it repeatedly, and there
is no timeout on the call — a hung Atlassian endpoint blocks a FastAPI threadpool worker
indefinitely, since `/resolve` is a sync handler with no time limit of its own. Cache the
client at module scope (or on the tool instance) and pass an explicit `timeout` to the
constructor.

### 7. No retry, timeout, or budget around the crew run

`pipeline.run_pipeline()` calls `kickoff()` with no `max_rpm`, no per-agent `max_iter`, and
no overall timeout. A model that loops on tool calls burns tokens until something else stops
it, and the web request hangs for as long as it takes. Set `max_iter` on both agents and
`max_rpm` on the `Crew`, and give the web path a wall-clock ceiling that surfaces as a
`PipelineError`.

### 8. `extract_result` can return a dict missing every field it promises — PARTLY DONE

**Update:** the validation half landed with item 2 — tiers 2 and 3 now go through
`TechnicalResolutionResult` and raise `PipelineError` on failure, which also covers the
non-dict case below. What remains of this item is the surrounding hardening (clearer error
text, deciding whether a partial result is ever worth rendering degraded).


`pipeline.py:53-66` falls back to `json.loads(crew_output.raw)`, which succeeds for *any*
valid JSON — including `{}` or a JSON array. The result is handed to `main.py` and the
template, which call `.get()` on it and render blanks. Validate the fallback dict through
`TechnicalResolutionResult` before returning; if it doesn't validate, raise `PipelineError`.
That also fixes tier 3 returning a non-dict (a JSON array) that `.get()` would crash on.

### 9. Ticket-key validation is looser than the output path assumes

`TICKET_KEY_PATTERN` (`pipeline.py:13`) allows any length, and the normalized key is
interpolated straight into `output/final_resolution__{ticket_id}.json` via crewAI's
`output_file`. A pathological but pattern-matching key produces an unwieldy filename. Cap the
project prefix and issue-number length in the regex. (Path traversal is already blocked by
the regex's anchors — this is a hygiene item, not an exploit.)

### 10. Concurrent runs on the same ticket race on the output file

Two console submits for the same key write the same path simultaneously. crewAI's
`output_file` write is not atomic, so a reader can observe a truncated JSON file. Write to a
temp file and `os.replace()`, or make the filename unique per run and keep the stable name as
a pointer to the latest.

---

## P2 — Quality, observability, testing

### 11. There is no test suite at all

`tests/` is empty. Every item above is a behavior that could be pinned with a cheap test that
never calls an LLM:

- `normalize_ticket_id` accept/reject table.
- `extract_result` across all three tiers plus the malformed cases in item 8.
- Schema validators from items 1, 2, and 4 — feed them the actual committed `output/*.json`
  files and watch the current ones fail, which is the proof that item 1 is real.
- `JiraTicketFetcherTool._run` with a mocked `JIRA` for the missing-config, 404, and success
  paths.

This is the highest-value P2 because it converts the P0 fixes from "believed done" to
"verified done".

### 12. Broken console scripts declared in `pyproject.toml`

`train`, `replay`, and `test` point at `main:train` / `main:replay` / `main:test`, which do
not exist. `crewai train`, `crewai replay`, and `crewai test` shell out to these and fail.
Either implement them or delete the entries — a declared entry point that crashes is worse
than an absent one. Note that `crewai test` in particular would be a natural home for the
score-calibration regression run described in item 2.

### 13. No structured logging or run metadata

Nothing records which models ran, how long the run took, token counts, or the timestamp. The
output JSON has no provenance, so a score can never be traced back to the model version that
produced it — which matters precisely because scoring behavior is prompt-defined and will
drift as models are swapped via `TRIAGE_MODEL` / `RESOLVER_MODEL`. Add a `run_metadata` block
to the persisted output (models, temperatures, UTC timestamp, duration) and replace the
`print` statements in `main.py` with the `logging` module.

### 14. Env-var validation happens too late and too quietly

Missing `OPENAI_API_KEY` surfaces as a model exception mid-run, after the Jira fetch has
already been paid for; missing Jira config surfaces as a string the agent may reason about
(item 5). Add a `validate_environment()` in `pipeline.py`, called at the top of
`run_pipeline()` — before `os.makedirs` and before the lazy crew import — that raises a clear
list of what's missing. Cheap, and it turns three confusing failure modes into one readable
message.

### 15. Agent prose gives no guidance on the hard cases

`config/agents.yaml` describes both agents in one sentence each, with no instruction for:
non-English tickets, empty descriptions (`jira_tool.py:31` substitutes "No description
provided." and the agent scores that), tickets that are clearly spam, or tickets where the
customer is calm but the *impact* is catastrophic (data loss with no angry language — which
should escalate, and which a pure sentiment read will miss). Sentiment and severity are being
collapsed into one number; consider splitting `frustration_score` from a `business_impact`
score and escalating on either.

---

## Suggested sequencing

1. **Items 1, 2, 4** together — all three are edits to `config/schemas.py` plus matching
   wording in `tasks.yaml`, they share a regeneration of the `output/` examples, and they
   remove the largest share of the risk.
2. **Item 5**, then **item 3** — fetch integrity first, since a consistency check on
   fabricated input is meaningless.
3. **Item 11** for whatever landed above, before moving on.
4. P1 as capacity allows; items 6 and 7 first if the console is ever exposed beyond
   localhost.
