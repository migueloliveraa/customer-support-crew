# Backend Improvements — Prioritized Backlog

Assessment of `src/customer_support_crew/`. Items are ordered **most critical first**:
everything in P0 is a correctness or safety defect that can produce a wrong decision on a
real ticket. P1 is robustness, P2 is quality and operability.

The recurring theme when this was first written: **the pipeline's business rules lived
entirely in prose, and nothing in Python validated that the model obeyed them.** Every P0
was a variant of that. Most of them are now closed.

> **Paths updated for the vertical-slice layout.** Everything that used to sit flat under
> `src/customer_support_crew/` now lives in one slice. The mapping, once:
>
> | old | new |
> | --- | --- |
> | `config/schemas.py` | `features/support_triage/domain/models.py` |
> | `config/{agents,tasks}.yaml` | `features/support_triage/adapters/crewai_pipeline/config/` |
> | `crew.py` | `features/support_triage/adapters/crewai_pipeline/crew.py` |
> | `tools/jira_tool.py` | `features/support_triage/adapters/jira_ticket_source.py` + `.../crewai_pipeline/tools.py` |
> | `pipeline.py` | `application/resolve_ticket.py`, `.../crewai_pipeline/{pipeline,result_mapper}.py`, `domain/policy.py`, `core/errors.py` |
> | `web/app.py` | `api/app.py` + `web/routes.py` |
>
> Paths below are given relative to `src/customer_support_crew/`, with
> `features/support_triage/` shortened to **`slice/`**. Historical writeups quote the old
> paths where that is what the finding was about at the time.

---

## P0 — Critical (wrong output reaches the user)

### 1. ~~`resolution_status` is a free-form string, and the model is already getting it wrong~~ — DONE

**Where (now):** `slice/domain/models.py`, `slice/adapters/crewai_pipeline/config/tasks.yaml`,
consumed at `web/templates/index.html:58` via the `escalated` flag computed in
`web/routes.py`, and at `cli/console.py` via `result.escalated`.

The field was a plain `str`. Its description named two values (`resolved_draft`,
`escalated_to_human`), but the *task prose* never used the string `resolved_draft` — it only
said "resolve the ticket by drafting…". The committed example outputs showed the model
inventing its own vocabulary:

| Ticket | `resolution_status` returned |
| --- | --- |
| CREWAISUP-1 | `resolved` |
| CREWAISUP-2, -3 | `drafted` |
| CREWAISUP-4…10 | `escalated_to_human` |

Three different values for the same outcome. Nothing rejected them.

**Why it was the top item:** both consumers branched on the escalated value only —
`result.get('resolution_status') == 'escalated_to_human'`. That happened to be stable, so
the bug was *latent*: the moment the model returned `escalate_to_human`, `ESCALATED`, or
`escalated`, the console would render a green "Reply drafted" verdict with an empty body for
a ticket that was actually escalated. A silent false-negative on escalation is the single
worst failure this system can produce.

**Resolved.** `ResolutionStatus` closes the set in `slice/domain/models.py`; `tasks.yaml`
states both literals and forbids synonyms; the three non-conforming example outputs were
corrected. No consumer string-compares any more — `TechnicalResolutionResult.escalated` is a
property on the model, `ResolutionResponse.escalated` mirrors it on the wire, and the
template reads the boolean. `tests/unit/test_result_mapper.py` pins the rejection of
`escalated` and `drafted`.

---

### 2. ~~`frustration_score` has no bounds and no calibration anchors~~ — DONE

**Where (now):** `slice/domain/models.py` — both the triage and the resolution declarations.

`frustration_score: int` with the description "An emotional frustration level scaled integer
from 1 to 10." There was no `ge=1`, no `le=10`. A model returning `0`, `11`, or `85` was
accepted, written to `output/`, and drawn on the gauge — where an out-of-range value renders
as a broken bar.

Worse than the missing bounds was the missing *calibration*. One sentence was the only signal
the model got about what a 4 means versus a 7, and 7 is exactly the escalation threshold.
The committed examples showed **7 of 10 tickets escalating**, with four separate 9–10 scores.

**Resolved.** Both `frustration_score` declarations carry `ge=1, le=10`; the triage field
description holds the tier ladder plus a severity floor (data loss, security breach,
unauthorized charge, total outage never score below the threshold however calm the wording);
`tasks.yaml` points at those tiers instead of duplicating them; `score_rationale` was added
(required at triage, optional on the resolution schema); and the resolver must copy the score
verbatim rather than re-derive it. The `CrewOutput` fallback tiers were also routed through
the schema, without which the bounds would only have applied to tier 1.

Since the restructure, the severity floor is no longer a typed literal: the description is
built from `ESCALATION_THRESHOLD` in `slice/domain/policy.py`, so the floor and the
escalation rule cannot drift apart (see item 3).

**Recalibration measured** (re-ran `CREWAISUP-1` through `-10`, compared against the
pre-calibration run at commit `7360994`):

| | before | after |
|---|---|---|
| escalation rate | 70% (7/10) | **60% (6/10)** |
| mean score | 7.4 | **6.1** |
| scores at 9–10 | 5 | **3** |
| scores in the 1–3 tier | 1 | **2** |

Every score moved down or held; none moved up. One ticket crossed the threshold —
`CREWAISUP-4` went 7 → 4 ("it's getting quite tedious to keep switching browsers", a civil
report with a workaround), which is the 4–6 tier behaving as intended. The anchors are
landing; the ladder does not need another pass.

**Two residual observations, not defects:**

- `CREWAISUP-5` and `-6` both sit at exactly 7 — the threshold — and both rationales justify
  the score by *severity* ("impact on productivity", "It's an endless loop") rather than by
  the tone signals the 7–8 tier actually names. Neither invokes the severity floor, which the
  field description tells the model to state explicitly when the floor is what drove the
  score. These two are the most consequential scores in the set (one point either way changes
  who handles the ticket) resting on the thinnest justification. Watch them across runs.
- The verbatim-copy rule cannot be verified from `output/`: only the resolver's copy is
  persisted, so there is nothing to diff triage against. Confirming it would mean persisting
  the triage output too — see item 13.

---

### 3. ~~Nothing enforces the escalation threshold in code~~ — DONE

**Where (now):** `slice/domain/policy.py`, checked in
`slice/application/resolve_ticket.py:_warn_on_policy_disagreement`.

The rule existed only as prose in `tasks.yaml`, while `pipeline.py` held
`ESCALATION_THRESHOLD = 7` explicitly marked *display only*. The resolver was free to score a
ticket 9 and still return a friendly draft reply, or score it 3 and escalate, and nothing
caught the contradiction. Two representations of one rule, kept in sync by a code comment
asking a human to remember.

Keeping the rule prompt-encoded was and remains a **deliberate design choice** — moving it
into Python would remove the model's ability to escalate a calm-but-catastrophic ticket,
which is real judgment worth keeping.

**Resolved, both halves:**

- *The duplication is gone.* `ESCALATION_THRESHOLD` is written down once, in
  `slice/domain/policy.py`. From there it reaches the prompt (`tasks.yaml` carries an
  `{escalation_threshold}` placeholder that `CrewAITriagePipeline` fills from the `kickoff()`
  inputs dict), the severity floor in the `frustration_score` description, the console gauge,
  and `GET /api/v1/config`. Nothing else may type the number.
- *The post-hoc consistency check exists.* `ResolveTicketUseCase` compares the returned
  `resolution_status` against `policy.should_escalate(frustration_score)` and logs a warning
  on disagreement, naming the ticket, the score, the threshold and what the model returned.

**The policy question the original writeup left open has an answer: log, do not override.**
Overriding to escalation would be the safer default in isolation, but it silently converts a
prompt regression into normal-looking output, and the whole point of keeping the rule in the
prompt is that the model is allowed to disagree. The warning makes the disagreement findable
without taking the judgment away. `tests/unit/test_resolve_ticket.py` pins both the warning
and the non-override.

Still open, if this ever matters operationally: the warning goes to the log only. Surfacing
it in the response — a `policy_agreement` field on `ResolutionResponse` that the console
renders as a warning band — would put it in front of the person reading the verdict.

---

### 4. The payload/status invariant is never checked

**Where:** `slice/domain/models.py` — `email_response_template` and
`internal_escalation_notes` on `TechnicalResolutionResult`.

Both are `Optional`, independently. The schema permits all four combinations, including the
two that are nonsense: escalated with no notes, and drafted with no reply. The template
already anticipates this and prints "The crew escalated without leaving notes" — a UI apology
for a schema that allows an empty result.

**Fix:** a `@model_validator(mode="after")` on `TechnicalResolutionResult` asserting that
`escalated_to_human` requires non-empty `internal_escalation_notes` and null
`email_response_template`, and the inverse for `resolved_draft`. Pydantic then rejects the
malformed output and crewAI can retry, instead of a hollow JSON file reaching
`FileResolutionStore`.

Cheaper to land than it was: the validator sits in the domain model, and
`tests/conftest.py:make_result` already builds both shapes, so the regression tests are two
lines each.

---

### 5. Jira fetch failures are indistinguishable from real ticket content

**Where:** `slice/adapters/jira_ticket_source.py` — the missing-config return and the
`except` return.

The adapter returns errors as strings — correct, and worth preserving, since it lets the
agent see the failure (the contract is spelled out on `TicketSource` in `slice/ports.py`).
But the returned string is plain prose with no marker, so `"Failed to fetch ticket
CREWAISUP-99 from Jira. Error: Issue Does Not Exist"` lands in the agent's context looking
exactly like ticket text. The triage agent's prompt gives it no instruction for this case, so
it will happily categorize the *error message* and assign it a frustration score. The
pipeline then drafts a customer reply about a ticket that does not exist. Nothing downstream
can tell this apart from a successful run.

**This is now the top open defect.** With items 1, 2 and 3 closed, it is the only remaining
path by which a confident, well-formed, entirely fabricated verdict reaches the user.

**Fix:**

- Prefix failures with an unmistakable sentinel (`ERROR: …`) and tell the triage agent in
  `tasks.yaml` what to do when it sees one — set a `fetch_failed: bool` on
  `TicketTriageResult` and stop.
- Have `CrewAITriagePipeline.run` raise `PipelineError` when that flag is set. Both the API
  (502) and the console (rendered "Run stopped") then show a real error instead of a
  fabricated verdict, with no extra handling at either call site.
- Separate the two failure modes: missing config is an operator problem that should fail
  loudly at startup, not per-tool-call; a 404 or auth rejection is a ticket-level problem.
  They currently look identical. `Settings.has_jira_credentials()` already exists for the
  startup half — see item 14.

---

## P1 — Robustness and cost

### 6. A new `JIRA` client is constructed on every fetch

`slice/adapters/jira_ticket_source.py` builds a fresh `JIRA(...)` inside `fetch`. Each
construction performs an authentication round-trip. An agent that retries the fetch pays it
repeatedly, and there is no timeout on the call — a hung Atlassian endpoint blocks a FastAPI
threadpool worker indefinitely, since both `/resolve` and `POST /api/v1/resolutions` are sync
handlers with no time limit of their own.

Cache the client on the adapter instance and pass an explicit `timeout` to the constructor.
The instance is now long-lived — `api/deps.py` builds it once behind an `lru_cache` — so
instance-level caching is enough and no module-scope global is needed.

### 7. No retry, timeout, or budget around the crew run

`slice/adapters/crewai_pipeline/pipeline.py` calls `kickoff()` with no `max_rpm`, no
per-agent `max_iter`, and no overall timeout. A model that loops on tool calls burns tokens
until something else stops it, and the web request hangs for as long as it takes. Set
`max_iter` on both agents and `max_rpm` on the `Crew` in
`slice/adapters/crewai_pipeline/crew.py`, and give the pipeline a wall-clock ceiling that
surfaces as a `PipelineError`.

### 8. `to_resolution` can return a result missing every field it promises — PARTLY DONE

**Update:** the validation half landed with item 2 and moved to
`slice/adapters/crewai_pipeline/result_mapper.py`. Tiers 2 and 3 now go through
`TechnicalResolutionResult` and raise `PipelineError` on failure, which also covers the
non-dict case below; `tests/unit/test_result_mapper.py` covers all three tiers plus
unparseable raw text and out-of-contract values. What remains is deciding whether a partial
result is ever worth rendering degraded, and whether the `PipelineError` message — currently
the raw pydantic `ValidationError` — is the right thing to put in a 502 body.

The original finding: the fallback fell back to `json.loads(crew_output.raw)`, which succeeds
for *any* valid JSON — including `{}` or a JSON array. The result was handed to the CLI and
the template, which called `.get()` on it and rendered blanks.

### 9. Ticket-key validation is looser than the output path assumes

`TICKET_KEY_PATTERN` in `slice/domain/ticket_key.py` allows any length, and the normalized key
is interpolated into `final_resolution__{ticket_id}.json` by
`slice/adapters/file_resolution_store.py`. A pathological but pattern-matching key produces an
unwieldy filename. Cap the project prefix and issue-number length in the regex. (Path
traversal is already blocked by the regex's anchors — this is a hygiene item, not an exploit.)

### 10. Concurrent runs on the same ticket race on the output file

Two submits for the same key write the same path simultaneously, and the write is not atomic,
so a reader — including `GET /api/v1/resolutions/{ticket_id}`, which did not exist when this
was first written — can observe a truncated file. `FileResolutionStore.load` already degrades
a corrupt file to `None` rather than crashing, but that turns the race into a silent 404
rather than fixing it.

Cheaper to land than it was: the write is ours now (`FileResolutionStore.save`) rather than
crewAI's `output_file=`, so it is a two-line change to write to a temp file in the same
directory and `os.replace()` onto the target.

---

## P2 — Quality, observability, testing

### 11. ~~There is no test suite at all~~ — DONE

`tests/` now has 40 tests and none of them touches the network or an API key. The Protocols in
`slice/ports.py` are what made that possible: `tests/conftest.py` provides `FakeTriagePipeline`,
`InMemoryResolutionStore` and `FakeTicketSource`, and the API and console tests build the app
with `create_app()` and swap the use case through `dependency_overrides`.

Covered: `normalize_ticket_id` accept/reject table; `to_resolution` across all three tiers
plus the malformed cases from item 8; the closed `ResolutionStatus` enum and the `ge/le`
bounds rejecting the exact values item 1 found in the wild; the policy-disagreement warning
and non-override from item 3; `FileResolutionStore` round-trip and corrupt-file handling; the
status-code mapping (422/404/502) and both console verdict branches.

Not covered, and worth adding: `JiraTicketSource.fetch` against a mocked `JIRA` for the
missing-config, 404 and success paths — the natural companion to item 5.

### 12. ~~Broken console scripts declared in `pyproject.toml`~~ — DONE

`train`, `replay` and `test` pointed at `main:train` / `main:replay` / `main:test`, which do
not exist, so `crewai train|replay|test` failed at the entry point. Deleted rather than
stubbed — a declared entry point that crashes is worse than an absent one.

The observation that survives: `crewai test` would have been a natural home for the
score-calibration regression run described in item 2. That run is still manual. With a test
suite now in place (item 11), the right home is a `pytest` marker that is excluded by default
and runs the ten sample tickets on demand.

### 13. No structured logging or run metadata

Nothing records which models ran, how long the run took, token counts, or the timestamp. The
output JSON has no provenance, so a score can never be traced back to the model version that
produced it — which matters precisely because scoring behavior is prompt-defined and will
drift as models are swapped via `TRIAGE_MODEL` / `RESOLVER_MODEL`.

Add a `run_metadata` block to the persisted output (models, temperatures, UTC timestamp,
duration). `slice/application/resolve_ticket.py` is the place: it already brackets the
pipeline call, and `get_settings()` has the model strings.

Partly started: the use case uses the `logging` module for the policy warning, and `api/app.py`
logs pipeline failures. `cli/console.py` still prints. Persisting the triage output alongside
the resolution — the missing piece from item 2's second residual observation — belongs here
too: `ResolutionStore` is the seam, and it would take a second `save`.

### 14. Env-var validation happens too late and too quietly — PARTLY DONE

**Update:** every environment variable is now declared in one typed place,
`core/settings.py`, read on first `get_settings()` call, with `has_jira_credentials()` as a
ready-made precondition. That closes the "scattered and untyped" half.

What remains is the *timing*. Missing `OPENAI_API_KEY` still surfaces as a model exception
mid-run, after the Jira fetch has already been paid for; missing Jira config still surfaces as
a string the agent may reason about (item 5). Add a `validate_environment()` to
`core/settings.py`, called from `api/deps.py` when the use case is built and from
`cli/console.py` at startup, raising a clear list of what is missing. Note the provider keys
are not currently `Settings` fields at all — they are read straight from `os.environ` by the
LiteLLM providers — so this would mean declaring them, per model provider.

### 15. Agent prose gives no guidance on the hard cases

`slice/adapters/crewai_pipeline/config/agents.yaml` describes both agents in one sentence
each, with no instruction for: non-English tickets, empty descriptions
(`jira_ticket_source.py` substitutes "No description provided." and the agent scores that),
tickets that are clearly spam, or tickets where the customer is calm but the *impact* is
catastrophic.

The last case is partly handled — the severity floor added in item 2 forces data loss,
security breaches, unauthorized charges and total outages to the threshold regardless of tone.
But that is a floor bolted onto a sentiment scale, not a separate measurement. Consider
splitting `frustration_score` from a `business_impact` score and escalating on either; that
would also give `policy.should_escalate` something more honest to compute than a single
number.

---

## Suggested sequencing

1. ~~Items 1, 2, 4 together~~ — 1 and 2 are done; **item 4** is now a standalone half-hour in
   `slice/domain/models.py` plus two tests.
2. ~~Item 3~~ — done. **Item 5 is the top open defect**: with the schema locked down, a
   fabricated verdict from a failed fetch is the only remaining route to confidently wrong
   output. Do it next, with the mocked-`JIRA` tests noted in item 11.
3. ~~Item 11~~ — done. Keep it that way: every item below should land with tests, which is now
   cheap.
4. P1 as capacity allows; items 6 and 7 first if the API or console is ever exposed beyond
   localhost — more so now that `/api/v1` exists and is scriptable.
