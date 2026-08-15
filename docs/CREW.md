# The crew — agents, tasks, and how to tune them

How the two agents are wired, and where to change their behavior. The structural reasoning
behind these seams is in [ARCHITECTURE.md](ARCHITECTURE.md); this document is the operator's
guide to the prompt surface.

All paths below are relative to
`src/customer_support_crew/features/support_triage/`.

## The two agents

| | `triage_agent` | `technical_resolver` |
| --- | --- | --- |
| Role | Customer Sentiment Specialist | Tier 2 Support Engineer |
| Model | `TRIAGE_MODEL`, temp `0.2` | `RESOLVER_MODEL`, temp `0.5` |
| Tools | `JiraTicketFetcherTool` | none |
| Output schema | `TicketTriageResult` | `TechnicalResolutionResult` |
| Decides | the frustration score | escalate vs. reply |

They run **sequentially**. `resolution_task` declares `context: [triage_task]`, so the
triage output is fed to the resolver.

The temperature split is deliberate: scoring should be repeatable, prose should not be
robotic.

## Where each thing lives

| What | File |
| --- | --- |
| Roles, goals, backstories | `adapters/crewai_pipeline/config/agents.yaml` |
| Task instructions and expected outputs | `adapters/crewai_pipeline/config/tasks.yaml` |
| Agents, tasks and LLMs wired together | `adapters/crewai_pipeline/crew.py` |
| Output schemas — **and the scoring calibration** | `domain/models.py` |
| The escalation number | `domain/policy.py` |
| The Jira tool the triage agent calls | `adapters/crewai_pipeline/tools.py` |
| `CrewOutput` → domain object | `adapters/crewai_pipeline/result_mapper.py` |

Four rules govern edits here, all expanded in [CONVENTIONS.md](CONVENTIONS.md):

1. YAML keys must match the `@agent` / `@task` method names in `crew.py`.
2. Field descriptions in `domain/models.py` **are prompt**, not documentation.
3. The escalation threshold is never typed outside `domain/policy.py`.
4. LLMs are constructed inside `@agent` methods, never in a class body.

## The scoring calibration

This is the part most worth understanding before changing anything.

`domain/models.py` is bound to the tasks via `output_json=`, which means every
`Field(description=...)` string is fed to the model as instructions. The
`frustration_score` description is therefore the **only** signal the model has about what a
4 means versus a 7. It defines four tiers:

| Score | Meaning |
| --- | --- |
| 1–3 | Informational question or feature request; not blocked, neutral tone |
| 4–6 | Blocked or inconvenienced but civil; no anger, first or second contact |
| 7–8 | Explicit anger or sarcasm, a repeated or ignored contact, or stated business impact |
| 9–10 | Threat to churn or escalate legally, refund demand, data loss, security problem, unauthorized charge, or total outage |

…plus the **severity floor**, which is the load-bearing part:

> if the ticket reports data loss, a security or access breach, an unauthorized or duplicate
> charge, or a complete outage, the score is never below the threshold **no matter how calm
> the wording**. Otherwise judge tone, not severity.

That sentence is what catches the polite emergency — the failure mode that motivated the
whole system. It is built as an f-string interpolating `ESCALATION_THRESHOLD`, so the floor
cannot drift away from the number the resolver is told to escalate on.

Two guardrails sit under the prose and are not optional:

- `ge=1, le=10` on both score declarations. The model previously returned values like `85`.
- `ResolutionStatus` as a closed enum. The model previously invented vocabulary —
  `resolved`, `drafted`, `escalated` — that consumers silently misread.

The resolver is told, in three separate places, to **copy** `frustration_score` and
`score_rationale` verbatim and never re-score. It is not the scorer. If you find yourself
loosening that, expect the two agents to disagree about the same ticket.

## The escalation rule

The rule is prose in `resolution_task`:

> If the frustration_score is `{escalation_threshold}` or higher, immediately set
> resolution_status to exactly `'escalated_to_human'` … If lower, set it to exactly
> `'resolved_draft'` …

`{escalation_threshold}` and `{ticket_id}` are interpolated from the `inputs` dict passed to
`kickoff()` in `adapters/crewai_pipeline/pipeline.py`. Never hardcode the number in the YAML.

**No Python branch enforces this.** That is a decision, not an omission — a code-level rule
would remove the model's ability to escalate a calm-but-catastrophic ticket, which is
judgment worth keeping ([why](ARCHITECTURE.md#escalation-stays-prompt-encoded)). What the
code does instead is notice: `application/resolve_ticket.py` logs a warning when the returned
status disagrees with `policy.should_escalate(score)`, naming the ticket, the score, the
threshold and what the model returned. It never overrides.

**Those warnings are the signal that a prompt change went wrong.** Watch the log after
tuning.

## Making changes

| You want to | Change |
| --- | --- |
| Move the escalate/reply cut-off | `ESCALATION_THRESHOLD` in `domain/policy.py`, and nowhere else |
| Change what counts as a 7 | the tier text in `_FRUSTRATION_SCORE_DESCRIPTION` |
| Add or remove a severity-floor trigger | the FLOOR sentence in the same description |
| Change the tone of drafted replies | `resolution_task.description`, and `technical_resolver`'s backstory |
| Change what escalation notes contain | `resolution_task.description` + the `internal_escalation_notes` field description |
| Add a field to the output | `domain/models.py`, then `api/dto.py` if clients need it, then `tasks.yaml` if the task prose must mention it |
| Swap a model | `TRIAGE_MODEL` / `RESOLVER_MODEL` in `.env` — no code change |
| Give an agent a new capability | a new `BaseTool` in `adapters/crewai_pipeline/tools.py`, **delegating to a port**, never calling an SDK directly |

## Adding a tool

Tools wrap ports, they do not wrap SDKs. `JiraTicketFetcherTool` holds a `TicketSource` on a
pydantic `PrivateAttr` and calls it — which is why the tool is testable with a fake and why
swapping Jira for Zendesk touches one adapter and `api/deps.py`.

Tool return values go straight to the agent as text. That is why `TicketSource.fetch`
**returns** its errors as strings instead of raising: an agent that sees `Failed to fetch…`
can say so, whereas an exception aborts the run. It is also a known defect — the error string
is currently indistinguishable from real ticket text (item 5 in
[BACKEND_IMPROVEMENTS.md](BACKEND_IMPROVEMENTS.md)).

## Reading the output

`result_mapper.to_resolution()` turns a `CrewOutput` into a `TechnicalResolutionResult`
through a three-tier fallback, because crewAI does not guarantee which tier is populated:

1. `.pydantic` — already the right object
2. `.json_dict` — validated into the model
3. `.raw` — parsed as JSON, then validated

**Every tier is validated.** An unparseable or out-of-contract output raises `PipelineError`,
which the API surfaces as `502`. That is the failure mode to watch after a prompt change: a
`502` usually means the model drifted off-schema.

## Testing a prompt change

```bash
uv run pytest                    # schema and mapping contracts; no LLM involved
uv run run_crew CREWAISUP-3      # a real run against one ticket
```

`output/final_resolution__<KEY>.json` files are committed as example data precisely so you can
diff scores across a calibration change. Run the same handful of tickets before and after, and
compare. There is no automated evaluation harness — see the documentation gaps in
[README.md](README.md#known-documentation-gaps).
