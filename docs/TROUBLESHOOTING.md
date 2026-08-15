# Troubleshooting

Symptoms, causes, and where to look. Config details are in
[CONFIGURATION.md](CONFIGURATION.md); prompt behavior is in [CREW.md](CREW.md).

## Startup and setup

**The first request after `uv run serve` takes ~10s longer than the rest.**
Expected. Importing crewAI pulls in litellm, chromadb, openai and pyvis. A background thread
starts that import at startup; `GET /health` reports `crew_warm`. A request arriving
mid-import blocks on the same import lock and is no worse off. Not an error.

**`crewai train` / `crewai replay` / `crewai test` fail.**
They are not supported. The console scripts were removed because the `main:train` /
`main:replay` / `main:test` functions they pointed at never existed.

**`No module named pytest`.**
Dev dependencies are in a separate group: `uv sync --group dev`.

**Import errors from `tests/`.**
The suite relies on `pythonpath = ["src"]` in `pyproject.toml`. Run it as `uv run pytest`
from the repository root, not by invoking pytest directly from elsewhere.

## Credentials and configuration

**Authentication errors from the model provider.**
The provider SDKs read `OPENAI_API_KEY` / `GEMINI_API_KEY` from `os.environ`, populated by
`load_dotenv()` in `core/settings.py`. Check that `.env` is at the **repository root** and
that the key matches the provider prefix in your model string — a `gemini/` model needs
`GEMINI_API_KEY`, no matter what else is set.

**A `.env` change had no effect.**
`get_settings()` is cached with `lru_cache(maxsize=1)` and `.env` is parsed once per process.
Restart the server.

**The agent's answer says the ticket could not be fetched.**
Missing or wrong Jira credentials. `JiraTicketSource.fetch` returns
`Error: Missing Jira configuration environment variables.` or `Failed to fetch ticket … ` as
a **string**, deliberately, so the agent can report it rather than the run aborting. Verify
all three of `JIRA_SERVER_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`, and that the token belongs to
the account in `JIRA_EMAIL`.

**Worse: a score and a reply were produced for a ticket that failed to fetch.**
This is the top open defect — the error string is indistinguishable from real ticket text, so
the agent may triage the error message itself. See item 5 in
[BACKEND_IMPROVEMENTS.md](BACKEND_IMPROVEMENTS.md). Until it is fixed, treat a resolution
whose rationale quotes nothing from the actual ticket as suspect.

## Runtime

**`502` from `POST /api/v1/resolutions`.**
`PipelineError` — the crew ran but its output could not be validated, including all three
`CrewOutput` fallback tiers failing. Usually the model drifted off-schema: an out-of-range
`frustration_score`, an invented `resolution_status`, or prose where JSON was expected.
Retrying blindly rarely helps; it is a prompt or calibration problem. See
[CREW.md](CREW.md#reading-the-output).

**`422` on a ticket key.**
`InvalidTicketKey`. Keys must match `^[A-Za-z][A-Za-z0-9]*-\d+$`. Validation runs **before**
any LLM call, so nothing was spent. Case does not matter — keys are normalized.

**`404` from `GET /api/v1/resolutions/{ticket_id}`.**
That endpoint reads stored results only; it never runs the crew. `POST` first.

**A request hangs or the client times out.**
A run is ~30 seconds. Many HTTP clients default to less. Raise the client timeout — the
server is not stuck.

**Log line: "score N implies escalate=X … but the resolver returned Y".**
A policy disagreement. The use case logs it and **honors the model** on purpose. One-off
disagreements are the intended flexibility; a burst of them right after a prompt edit means
the edit went wrong. See [CREW.md](CREW.md#the-escalation-rule).

## Output files

**No `output/` directory appeared where I expected it.**
Results are anchored to the **repository root**, not the current working directory — a
relative `OUTPUT_DIR` resolves against `PROJECT_ROOT`. Look at `<repo>/output/`.

**A previous result vanished.**
Re-running the same ticket key overwrites its file, from any client. There is no history.

**`GET /api/v1/resolutions/{id}` returns 404 although the file exists.**
`FileResolutionStore.load` returns `None` on a missing **or corrupt** file. Check the JSON
parses and matches the current schema — a hand-edited or schema-outdated file reads as
absent.

## Scoring behavior

**Scores drift upward; routine tickets land at 7+.**
Tune the tier text in `_FRUSTRATION_SCORE_DESCRIPTION` in `domain/models.py` — that text is
prompt, and it is the only calibration the model gets. Lowering `TRIAGE_TEMPERATURE` also
helps repeatability.

**A calm ticket reporting an outage scored low.**
The severity floor is not landing. Check the FLOOR sentence in the same description, and
confirm the triage agent is quoting the ticket in `score_rationale` — if it quotes nothing
relevant, the fetch may be the real problem.

**The resolver changed the score.**
It is told three times to copy it verbatim. If it still re-scores, the resolver model is too
weak for the instruction, or `resolution_task.description` was edited in a way that weakened
it.

## Console

**The console shows "Run stopped".**
The web router catches `AppError` itself — the one deliberate exception to the
no-catch rule — because it owes the operator rendered HTML rather than JSON. The underlying
cause is the same as the API status codes above; check the server log for the exception.

**The console shows a stale result.**
It cannot. `POST /resolve` always runs the crew live and never reads cached `output/*.json`.
If you are seeing an old answer, you are looking at a browser-cached page.

## Tests

**Tests take ~10s and hit the network.**
`TestClient` was constructed with `with`, which runs the lifespan and starts the crewAI
warm-up import. Construct it without the context manager
([why](ARCHITECTURE.md#testing-strategy)).

**A test passes alone but fails in the suite.**
Dependency overrides leaking. Build a fresh app with `create_app()` per test and set
`app.dependency_overrides` on that instance.
