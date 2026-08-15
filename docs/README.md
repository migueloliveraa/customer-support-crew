# Customer Support Crew — Documentation

Start here. This page explains what the system is, what it does, and where every other
document lives.

---

## What this application is

A [crewAI](https://crewai.com) multi-agent application that **triages Atlassian Jira support
tickets**. Given a Jira issue key, it fetches the ticket, scores how frustrated the customer
is on a 1–10 scale, and then either drafts a reply to send them or writes internal handover
notes for a human engineer.

It ships **three clients over one use case** — a JSON API, a server-rendered web console, and
a CLI — so the same triage logic can be driven from a browser, a script, or another service.

Python `>=3.10,<3.14`, managed with [`uv`](https://docs.astral.sh/uv/). No build step, no
database, no queue.

## The problem it solves

Support queues are triaged by hand, and the expensive failure is not a slow reply — it is a
**missed escalation**. A ticket reporting data loss in polite language reads as routine and
gets a templated answer; an angry customer threatening to churn sits behind twenty
low-priority tickets. Both are judgment calls that a human makes inconsistently at volume,
and neither is visible until the customer is already gone.

This crew makes that first judgment call explicitly and uniformly:

- Every ticket gets a **frustration score with a written rationale** that quotes the phrase
  which drove it — so the decision is auditable rather than a vibe.
- Scoring is calibrated against **fixed tiers plus a severity floor**, so an emergency
  reported calmly still clears the escalation bar.
- The escalation cut-off is **one number in one file**, not a convention spread across prompts
  and code, so tuning it is a one-line change that moves every surface at once.
- Below the bar, the customer gets a **drafted reply** immediately instead of waiting in a
  queue.

## Main capabilities

| Capability | Where it lives |
| --- | --- |
| Fetch a ticket from Jira Cloud by issue key | `adapters/jira_ticket_source.py` |
| Score customer frustration 1–10 with a quoted rationale | `triage_agent`, calibrated in `domain/models.py` |
| Decide escalate-vs-reply against a single threshold | `resolution_task` prose + `domain/policy.py` |
| Draft a customer reply, or write internal handover notes | `technical_resolver` |
| Validate the model's output against a closed schema | `domain/models.py`, `result_mapper.py` |
| Flag when the model's verdict disagrees with the threshold | `application/resolve_ticket.py` |
| Persist and re-read results as JSON | `adapters/file_resolution_store.py` |
| Serve it as a versioned JSON API | `features/support_triage/api/routes.py` |
| Serve it as a zero-build web console | `web/routes.py` |
| Run it from a terminal | `cli/console.py` |

## High-level architecture

One **vertical slice** — `features/support_triage/` — holds the entire capability, with a
ports-and-adapters interior. Outside it there is only shared plumbing (`core/`) and three
clients, all entering through the same use case.

```
        JSON API            Web console              CLI
   POST /api/v1/resolutions  POST /resolve     uv run run_crew KEY
            │                     │                   │
            └─────────────────────┼───────────────────┘
                                  ▼
                      ResolveTicketUseCase.execute()
                                  │
         ┌────────────────────────┼────────────────────────┐
         ▼                        ▼                        ▼
   normalize key           TriagePipeline            ResolutionStore
                        (crewAI, 2 agents)          (output/*.json)
                                  │
                             TicketSource
                             (Jira Cloud)
```

The three arrows out of the use case are **ports** — `typing.Protocol` declarations in
`features/support_triage/ports.py`. The application layer depends only on those, never on
Jira, the filesystem, or crewAI itself. That seam is why the whole test suite runs with no
network and no API key.

Full reasoning, the directory tree, and every design decision with its *why*:
**[ARCHITECTURE.md](ARCHITECTURE.md)**.

## Main technologies

| | |
| --- | --- |
| **crewAI** | Agent orchestration. Two agents run sequentially via `@CrewBase`, with structured output bound through `output_json=`. |
| **LiteLLM** (via crewAI) | Provider-agnostic model strings. Triage and resolution can run on different models — the defaults are `openai/gpt-4o-mini` and `gemini/gemini-2.0-flash`. |
| **Pydantic v2** | The agents' output schemas. Field descriptions are prompt; `ge`/`le` bounds and a closed enum are the guardrails. |
| **pydantic-settings** | Typed configuration, read on first call rather than at import. |
| **FastAPI** | Both the JSON API and the console. App factory + dependency injection. |
| **Jinja2** | The server-rendered console. No CDN, no npm, no bundler. |
| **Atlassian Jira Cloud REST** | The ticket source, over basic auth. |
| **pytest** | The suite — offline, keyless, driven by fakes swapped in through `dependency_overrides`. |
| **uv / hatchling** | Dependency management, locking, and the console-script entry points. |

## Documentation map

| Document | Read it when |
| --- | --- |
| **[GETTING_STARTED.md](GETTING_STARTED.md)** | You want it installed and running. |
| **[CONFIGURATION.md](CONFIGURATION.md)** | You need to know what goes in `.env` and how settings resolve. |
| **[ARCHITECTURE.md](ARCHITECTURE.md)** | You want to understand how it is put together, and why each seam exists. |
| **[CREW.md](CREW.md)** | You want to change the agents' behavior — prompts, scoring calibration, the escalation rule, models. |
| **[API.md](API.md)** | You are writing a client against `/api/v1`. |
| **[CONVENTIONS.md](CONVENTIONS.md)** | You are about to edit the code. The invariants live here. |
| **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** | Something is failing or behaving oddly. |
| **[BACKEND_IMPROVEMENTS.md](BACKEND_IMPROVEMENTS.md)** | You are picking up work, or about to "fix" something that may already be tracked. |
| **[CHANGELOG.md](CHANGELOG.md)** | You want to know what changed and why. |
| **[../CLAUDE.md](../CLAUDE.md)** | You are Claude Code, or configuring it. |

## Terminology

Terms that mean something specific here, and are easy to misread otherwise.

**Slice** — a vertical feature module owning its whole stack: domain, ports, application,
adapters, and API router. There is exactly one, `support_triage`. Slices never import each
other.

**Port** — a `Protocol` in `ports.py` describing something the application needs from the
outside world: `TicketSource`, `TriagePipeline`, `ResolutionStore`.

**Adapter** — a concrete implementation of a port. Jira, the filesystem and the crewAI crew
are all adapters. Swapping one is a change to `api/deps.py` and nothing else.

**Use case** — `ResolveTicketUseCase.execute()`. The single entry point every client calls.
If a behavior should apply to all three clients, it belongs here.

**Composition root** — `api/deps.py`. The only module that knows which adapter is the real
one.

**Frustration score** — an integer 1–10 produced by the triage agent, calibrated against the
tiers in the `frustration_score` field description. Judged on *tone*, except where the
severity floor overrides it.

**Severity floor** — the rule that data loss, a security or access breach, an unauthorized or
duplicate charge, or a total outage scores at or above the escalation threshold **no matter
how calmly it is worded**. This is what catches the polite emergency.

**Escalation threshold** — `ESCALATION_THRESHOLD` in `domain/policy.py`, currently `7`. Scores
at or above it should escalate. Written down exactly once; everything else reads it.

**Prompt-encoded** — a rule the model is *told* rather than one Python enforces. Escalation is
prompt-encoded on purpose: see
[ARCHITECTURE.md](ARCHITECTURE.md#escalation-stays-prompt-encoded).

**Policy disagreement** — the model returned a `resolution_status` that does not match what
the threshold implies. The use case logs a warning and **honors the model** rather than
overriding it.

**Resolution status** — a closed two-value enum: `resolved_draft` or `escalated_to_human`.
Clients should read the `escalated` boolean instead of string-comparing it.

**Three-tier fallback** — how a `CrewOutput` becomes a domain object in `result_mapper.py`:
try `.pydantic`, then `.json_dict`, then parse `.raw`. Every tier is validated; an unusable
output raises `PipelineError`.

**Warm-up** — the background thread started at server startup that pays the ~10s crewAI
import cost before the first request needs it. `GET /health` reports `crew_warm`.

## Known documentation gaps

Honest list of what is *not* written down. Some are deliberate, some are simply not done yet.

- **No root `README.md`.** All documentation now lives in `docs/`, so a repository host such
  as GitHub will render no landing page for this project. Add a short pointer file at the root
  if that matters for how the repo is shared.
- **No deployment or operations guide.** There is no Dockerfile, no CI configuration, no
  process-manager or reverse-proxy guidance, and no notes on running more than one instance.
  Everything documented here assumes `uv run serve` on a workstation.
- **No security model is written down.** The API and the console are **unauthenticated** —
  anyone who can reach the port can spend LLM tokens and read stored resolutions. Jira
  credential scope, rate limits, and PII handling for ticket text pulled into `output/*.json`
  are all undocumented.
- **No cost or latency figures.** A run is described as "roughly 30 seconds" and nothing
  records per-run token cost, so there is no basis for capacity or budget planning.
- **Failure semantics for ticket fetching are documented as a defect, not a contract.**
  `TicketSource.fetch` returns errors as strings that the agent cannot distinguish from real
  ticket text — see item 5 in [BACKEND_IMPROVEMENTS.md](BACKEND_IMPROVEMENTS.md), the top open
  issue.
- **No evaluation methodology.** `output/*.json` is committed as example data for judging
  score calibration by eye, but there is no labelled set, no regression harness, and no
  agreed metric for "the scoring got better".
- **The SPA migration path is asserted, not specified.** `ARCHITECTURE.md` explains why the
  DTO/domain split makes a future SPA safe; no document describes CORS, auth, build tooling,
  or how the console would be retired.
- **Design decisions carry no dates or supersession history.** `ARCHITECTURE.md` records the
  current reasoning as prose. There is no ADR log, so a decision that gets reversed leaves no
  trace of when or why.
