# Conventions

The rules to follow while editing this repository. Break one and something goes wrong
quietly — each links to the section of [ARCHITECTURE.md](ARCHITECTURE.md) that explains why
it exists.

## Invariants

### Domain and policy

- **Never type the escalation threshold anywhere but `domain/policy.py`.** It reaches the
  prompt, the score calibration, the console gauge and `/api/v1/config` from there.
  ([why](ARCHITECTURE.md#the-escalation-threshold-has-one-home))
- **Do not add a Python branch that enforces escalation.** The rule is prose in `tasks.yaml`;
  the use case logs disagreement and honors the model.
  ([why](ARCHITECTURE.md#escalation-stays-prompt-encoded))
- **Treat `Field(description=...)` in `domain/models.py` as prompt.** It is the model's only
  scoring calibration; tune behavior there, together with the `ge`/`le` bounds and the closed
  `ResolutionStatus` enum.
  ([why](ARCHITECTURE.md#field-descriptions-are-prompt-not-documentation))
- **Keep `agents.yaml`, `tasks.yaml` and `domain/models.py` in sync.** YAML keys must match
  the `@agent` / `@task` method names.
  ([why](ARCHITECTURE.md#field-descriptions-are-prompt-not-documentation))

### Boundaries

- **The application layer depends on `ports.py`, never on Jira, the filesystem or crewAI.**
  New integrations are new adapters wired in `api/deps.py`.
  ([why](ARCHITECTURE.md#ports-and-adapters))
- **`JiraTicketSource.fetch` returns errors as strings; never make it raise.**
  ([why](ARCHITECTURE.md#ports-and-adapters))
- **Keep `api/dto.py` separate from `domain/models.py`** — do not "simplify" it into a
  re-export. ([why](ARCHITECTURE.md#the-wire-contract-is-separate-from-the-domain-schema))
- **Write results through `ResolutionStore`, not a relative path.**
  ([why](ARCHITECTURE.md#persistence-lives-outside-the-crew))
- **Slices do not import each other.** Anything genuinely shared moves down into `core/`.
  ([why](ARCHITECTURE.md#one-slice-not-two))

### Configuration and startup

- **Build LLMs inside `@agent` methods, never in a class body.**
  ([why](ARCHITECTURE.md#settings-are-read-on-call-not-import))
- **Read the environment only in `core/settings.py`.** See
  [CONFIGURATION.md](CONFIGURATION.md#adding-a-setting).
- **Keep the crewAI import lazy in `api/deps.py`.**
  ([why](ARCHITECTURE.md#crewai-is-imported-lazily-and-warmed-in-the-background))

### HTTP

- **API route handlers do not catch**; errors map to status codes in `api.app`. The web
  router catching `AppError` is the one deliberate exception.
  ([why](ARCHITECTURE.md#errors-map-to-status-codes-in-one-place))
- **Handlers stay sync `def`.** A ~30s blocking run belongs in FastAPI's threadpool.
  ([why](ARCHITECTURE.md#json-api))
- **Keep the console no-build**: no CDN, no npm, `static/app.css` is the whole stylesheet,
  and the console calls the use case directly rather than its own API.
  ([why](ARCHITECTURE.md#web-console))

### Tests

- **Construct `TestClient` without `with`**, or the lifespan drags crewAI into the test run.
  ([why](ARCHITECTURE.md#testing-strategy))
- **Swap dependencies through `create_app()` + `app.dependency_overrides`**, one app per
  test, so overrides cannot leak between tests.
- **Tests stay offline and keyless.** If a change makes the suite need a network call or an
  API key, the seam is in the wrong place.

## Changelog rule

**Every change to this repository gets an entry in [CHANGELOG.md](CHANGELOG.md)** — added as
part of the same change, not afterwards.

- Write under `## [Unreleased]`, in the `Added` / `Changed` / `Fixed` / `Removed` subsection
  that fits ([Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format). Create the
  subsection if it isn't there.
- Summarize the change and **why** it was made, in prose a teammate can read months later.
  Name the files or entry points that moved. Do not paste diffs, and do not restate what
  `git log` already shows.
- One entry per meaningful change, not one per file touched. Trivial edits (a typo, a
  comment) don't need one.
- Skip it only if the change's author explicitly says so.

## Documentation rule

Documentation lives in `docs/`. When a change alters behavior a document describes, update
that document in the same change:

| You changed | Also update |
| --- | --- |
| A structural seam, or the reasoning behind one | [ARCHITECTURE.md](ARCHITECTURE.md) |
| An environment variable | [CONFIGURATION.md](CONFIGURATION.md) |
| An endpoint or a wire shape | [API.md](API.md) |
| Prompts, schemas, or scoring calibration | [CREW.md](CREW.md) |
| A rule others must follow | this file |
| A defect you fixed or found | [BACKEND_IMPROVEMENTS.md](BACKEND_IMPROVEMENTS.md) |

Do not duplicate prose between documents. Link instead — a fact stated twice will be updated
once.

## Code style

There is no linter and no formatter configured, so match the surrounding code:

- Absolute imports from `customer_support_crew.*`.
- Module docstrings explain *why* the module exists, not what each function does. Several
  existing docstrings carry contracts you would otherwise have to infer — the errors-as-
  strings rule in `ports.py`, the sync-handler rule in `routes.py`. Keep that habit.
- Type hints on public functions.
- Comments explain a decision, not a mechanism.
