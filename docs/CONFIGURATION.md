# Configuration

Everything this application reads from the environment, and how it resolves.

`.env` at the repository root (gitignored) is read by
`src/customer_support_crew/core/settings.py`, **the only module that touches the
environment**. Nothing else calls `os.getenv`.

## Variables

### Models

| Variable | Default | Notes |
| --- | --- | --- |
| `TRIAGE_MODEL` | `openai/gpt-4o-mini` | LiteLLM-style `provider/model` string for the triage agent |
| `TRIAGE_TEMPERATURE` | `0.2` | Low on purpose — scoring should be repeatable |
| `RESOLVER_MODEL` | `gemini/gemini-2.0-flash` | LiteLLM-style string for the Tier-2 resolver |
| `RESOLVER_TEMPERATURE` | `0.5` | Higher — this agent is writing prose |

The split is deliberate: a cheap fast model for scoring, a stronger one for the reply. Both
can point at the same model if you prefer.

### API keys

| Variable | Needed when |
| --- | --- |
| `OPENAI_API_KEY` | either model string starts with `openai/` |
| `GEMINI_API_KEY` | either model string starts with `gemini/` |

These are read by the provider SDKs directly from `os.environ`, not through the `Settings`
object. That is why `settings.py` calls `load_dotenv()` **as well as** declaring typed
fields — pydantic-settings' `env_file` support populates `Settings` without ever touching
`os.environ`, so both mechanisms are required.

If you switch to a different provider, set whatever key that provider's SDK expects; LiteLLM
handles the rest.

### Jira

| Variable | Notes |
| --- | --- |
| `JIRA_SERVER_URL` | e.g. `https://your-org.atlassian.net` |
| `JIRA_EMAIL` | the account the API token belongs to |
| `JIRA_API_TOKEN` | Atlassian Cloud API token; held as a `SecretStr` |

All three are optional so the app still boots — and the test suite still runs — without them.
When they are missing, `JiraTicketSource.fetch` **returns** a message saying so rather than
raising, and the agent sees that string as tool output. See
[ARCHITECTURE.md](ARCHITECTURE.md#ports-and-adapters) for why, and item 5 in
[BACKEND_IMPROVEMENTS.md](BACKEND_IMPROVEMENTS.md) for the open defect this contract creates.

### Output

| Variable | Default | Notes |
| --- | --- | --- |
| `OUTPUT_DIR` | `output` | Where `final_resolution__<KEY>.json` files land |

**A relative value resolves against the repository root, not the current working directory.**
`Settings.resolved_output_dir` anchors it to `PROJECT_ROOT`, so results go to the same place
regardless of where you started the process. Absolute paths are used as given.

## How settings are loaded

`get_settings()` returns a process-wide `Settings` instance cached with `lru_cache(maxsize=1)`,
so `.env` is parsed exactly once — **when first called, never at import time**.

This matters more than it looks. It means:

- Any module may be imported at module scope, in any order, with no import-ordering hazard.
- LLM objects must be built **inside** `@agent` methods (via `core/llm.py:build_llm`), never
  as class-body attributes — a class body evaluates at import, which is precisely the race
  this design removed. See
  [ARCHITECTURE.md](ARCHITECTURE.md#settings-are-read-on-call-not-import).
- Changing `.env` requires a process restart. There is no reload.

## Precedence

Standard pydantic-settings order — highest wins:

1. Real environment variables (e.g. `TRIAGE_MODEL=... uv run serve`)
2. `.env` at the repository root
3. The defaults in `Settings`

Unknown keys in `.env` are ignored (`extra="ignore"`), so unrelated variables are harmless.

## Adding a setting

Add a typed field to `Settings` in `core/settings.py` — that is the whole change. Do not read
the environment anywhere else, and do not add a module-level constant that captures a value at
import time. Configuration shared by every future slice belongs here too.
