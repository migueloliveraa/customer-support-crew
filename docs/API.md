# JSON API reference

`/api/v1`, defined in `src/customer_support_crew/features/support_triage/api/routes.py`.
Wire shapes are in `api/dto.py` — deliberately separate models from the domain schemas, so
the contract can hold still while prompts are tuned
([why](ARCHITECTURE.md#the-wire-contract-is-separate-from-the-domain-schema)).

Interactive docs are served at `/docs` when the app is running.

**There is no authentication.** Anyone who can reach the port can spend LLM tokens and read
stored resolutions. Do not expose this beyond localhost or a trusted network without putting
something in front of it.

## Endpoints

| Method | Path | Runs the crew? |
| --- | --- | --- |
| `POST` | `/api/v1/resolutions` | Yes — ~30s |
| `GET` | `/api/v1/resolutions/{ticket_id}` | No — reads stored JSON |
| `GET` | `/api/v1/config` | No |
| `GET` | `/health` | No |

---

### `POST /api/v1/resolutions`

Runs the full triage on one ticket, saves the result, and returns it. **Blocking, roughly 30
seconds** — two sequential LLM calls plus a Jira fetch. Set your client timeout accordingly.

Handlers are sync `def` so FastAPI runs them in its threadpool; a long run does not stall
other requests.

**Request**

```json
{ "ticket_id": "CREWAISUP-10" }
```

`ticket_id` is case-insensitive and normalized server-side. It must match
`^[A-Za-z][A-Za-z0-9]*-\d+$` — validated before any LLM call is spent.

**Response `200`**

```json
{
  "ticket_id": "CREWAISUP-10",
  "frustration_score": 9,
  "score_rationale": "Customer wrote 'we are cancelling our contract'.",
  "resolution_status": "escalated_to_human",
  "escalated": true,
  "email_response_template": null,
  "internal_escalation_notes": "Account is on the enterprise plan; ..."
}
```

Re-running an existing ticket key overwrites its stored result.

---

### `GET /api/v1/resolutions/{ticket_id}`

The last stored resolution for a ticket. Does **not** run the crew — it reads
`output/final_resolution__<KEY>.json` through `ResolutionStore`. Returns `404` if the ticket
has never been run.

Response body is identical to the `POST`.

---

### `GET /api/v1/config`

The policy constants a client needs to render a verdict consistently with the backend. Read
these rather than hardcoding them — the threshold has exactly one home, and this endpoint is
one of its four consumers.

```json
{
  "escalation_threshold": 7,
  "score_min": 1,
  "score_max": 10,
  "resolution_statuses": ["resolved_draft", "escalated_to_human"]
}
```

---

### `GET /health`

Liveness, plus whether the background crewAI import has finished.

```json
{ "status": "ok", "crew_warm": true }
```

`crew_warm: false` means the first `POST /api/v1/resolutions` will additionally wait on the
import (~10s). It is not an error state.

## Field notes

**`escalated`** is a boolean mirror of `resolution_status`. Use it. No client should
string-compare the status itself.

**`resolution_status`** is a closed enum — `resolved_draft` or `escalated_to_human`, and
nothing else. Treat any other value as a bug, not as something to handle.

**`frustration_score`** is always `1..10` inclusive; the bounds are enforced by the schema, so
an out-of-range model output fails validation rather than reaching you.

**`email_response_template`** and **`internal_escalation_notes`** are mutually exclusive in
practice: a `resolved_draft` fills the first, an `escalated_to_human` fills the second. Both
are nullable, so do not assume the pairing holds for a malformed run.

## Status codes

Exceptions are mapped once, in `api.app._register_exception_handlers`. Route handlers contain
no `try`/`except` ([why](ARCHITECTURE.md#errors-map-to-status-codes-in-one-place)).

| Status | Exception | Means |
| --- | --- | --- |
| `422` | `InvalidTicketKey` | The ticket key is malformed. Nothing was spent. |
| `422` | pydantic validation | The request body is the wrong shape. |
| `404` | `ResolutionNotFound` | No stored result for that ticket. |
| `502` | `PipelineError` | The crew ran but produced output that could not be validated into the schema — including all three `CrewOutput` fallback tiers failing. |

A `502` is worth surfacing rather than retrying blindly: it usually means the model drifted
off-schema, which is a prompt or calibration problem.

## Versioning

`/api/v1` is versioned so that prompt-engineering churn in `domain/models.py` cannot break
clients. If a change would alter an existing response shape, add `/api/v2` rather than
editing `v1` in place.

## Client example

```python
import httpx

base = "http://127.0.0.1:8000"
cfg = httpx.get(f"{base}/api/v1/config").json()

r = httpx.post(
    f"{base}/api/v1/resolutions",
    json={"ticket_id": "CREWAISUP-10"},
    timeout=120,          # the run is slow; do not use the default
).json()

if r["escalated"]:
    print("Escalate:", r["internal_escalation_notes"])
else:
    print("Reply:", r["email_response_template"])
```
