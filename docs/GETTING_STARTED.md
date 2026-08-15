# CustomerSupportCrew Crew

Welcome to the CustomerSupportCrew Crew project, powered by [crewAI](https://crewai.com). This template is designed to help you set up a multi-agent AI system with ease, leveraging the powerful and flexible framework provided by crewAI. Our goal is to enable your agents to collaborate effectively on complex tasks, maximizing their collective intelligence and capabilities.

## Installation

Ensure you have Python >=3.10 <3.14 installed on your system. This project uses [UV](https://docs.astral.sh/uv/) for dependency management and package handling, offering a seamless setup and execution experience.

First, if you haven't already, install uv:

```bash
pip install uv
```

Next, navigate to your project directory and install the dependencies:

(Optional) Lock the dependencies and install them by using the CLI command:
```bash
crewai install
```
### Customizing

**Put your model and Jira credentials in `.env`** — see the Environment section of
[`CLAUDE.md`](CLAUDE.md) for the full list. Everything is read through
`src/customer_support_crew/core/settings.py`.

The crew lives in one vertical slice, `src/customer_support_crew/features/support_triage/`.
[`ARCHITECTURE.md`](ARCHITECTURE.md) explains how the pieces fit and why; the files you are
most likely to want are:

- `adapters/crewai_pipeline/config/agents.yaml` — agent roles, goals and backstories
- `adapters/crewai_pipeline/config/tasks.yaml` — task descriptions and expected outputs
- `adapters/crewai_pipeline/crew.py` — LLMs, tools and output schemas wired together
- `domain/models.py` — the structured output schemas (their field descriptions are prompt)
- `domain/policy.py` — the escalation threshold, defined once and used everywhere

## Running the Project

```bash
uv run serve                  # web console + JSON API on http://127.0.0.1:8000
uv run run_crew CREWAISUP-3   # one ticket from the CLI
crewai run                    # same, on the default ticket
uv run pytest                 # the test suite (no network, no API key)
```

Each run writes `output/final_resolution__<TICKET_ID>.json` at the repository root,
whatever directory you started from.

## Understanding Your Crew

Two agents run sequentially. The triage agent fetches the Jira ticket and scores customer
frustration 1–10 against the calibration tiers in its output schema; the Tier-2 resolver
either drafts a customer reply or, at or above the escalation threshold, writes internal
handover notes. Escalation is prompt-encoded — the rule is prose in `tasks.yaml`, and the
number it uses comes from `domain/policy.py`.

The JSON API (`POST /api/v1/resolutions`), the web console and the CLI are three clients of
the same use case, `features/support_triage/application/resolve_ticket.py`.

## Support

For support, questions, or feedback regarding the CustomerSupportCrew Crew or crewAI.
- Visit our [documentation](https://docs.crewai.com)
- Reach out to us through our [GitHub repository](https://github.com/joaomdmoura/crewai)
- [Join our Discord](https://discord.com/invite/X4JWnZnxPb)
- [Chat with our docs](https://chatg.pt/DWjSBZn)

Let's create wonders together with the power and simplicity of crewAI.
