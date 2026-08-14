"""The JSON API, with the use case swapped for a fake.

`create_app()` is called per test rather than importing the module-level `app`, which
keeps `dependency_overrides` from leaking between tests. The `TestClient` is used
*without* `with`, so the lifespan — and therefore the crew warm-up import — never runs:
these tests must not drag in crewai.
"""

from fastapi.testclient import TestClient

from customer_support_crew.api.app import create_app
from customer_support_crew.api.deps import get_resolve_ticket_use_case
from customer_support_crew.core.errors import PipelineError
from customer_support_crew.features.support_triage.application.resolve_ticket import (
    ResolveTicketUseCase,
)
from customer_support_crew.features.support_triage.domain.models import ResolutionStatus
from customer_support_crew.features.support_triage.domain.policy import (
    ESCALATION_THRESHOLD,
)

from tests.conftest import FakeTriagePipeline, InMemoryResolutionStore, make_result


def client_with(pipeline: FakeTriagePipeline) -> TestClient:
    app = create_app()
    use_case = ResolveTicketUseCase(pipeline, InMemoryResolutionStore())
    app.dependency_overrides[get_resolve_ticket_use_case] = lambda: use_case
    return TestClient(app)


def test_post_returns_the_resolution():
    result = make_result(
        ticket_id="CREWAISUP-6",
        frustration_score=9,
        status=ResolutionStatus.ESCALATED_TO_HUMAN,
    )
    response = client_with(FakeTriagePipeline(result)).post(
        "/api/v1/resolutions", json={"ticket_id": "crewaisup-6"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ticket_id"] == "CREWAISUP-6"  # normalized server-side
    assert body["resolution_status"] == "escalated_to_human"
    assert body["escalated"] is True


def test_invalid_key_is_422():
    response = client_with(FakeTriagePipeline()).post(
        "/api/v1/resolutions", json={"ticket_id": "nope"}
    )
    assert response.status_code == 422
    assert "not a Jira issue key" in response.json()["detail"]


def test_pipeline_failure_is_502():
    pipeline = FakeTriagePipeline(raises=PipelineError("unparseable"))
    response = client_with(pipeline).post(
        "/api/v1/resolutions", json={"ticket_id": "CREWAISUP-3"}
    )
    assert response.status_code == 502


def test_get_resolution_404s_then_200s():
    client = client_with(FakeTriagePipeline())
    assert client.get("/api/v1/resolutions/CREWAISUP-3").status_code == 404
    client.post("/api/v1/resolutions", json={"ticket_id": "CREWAISUP-3"})
    assert client.get("/api/v1/resolutions/CREWAISUP-3").status_code == 200


def test_config_exposes_the_single_threshold():
    body = client_with(FakeTriagePipeline()).get("/api/v1/config").json()
    assert body["escalation_threshold"] == ESCALATION_THRESHOLD
    assert body["resolution_statuses"] == ["resolved_draft", "escalated_to_human"]


def test_health():
    assert client_with(FakeTriagePipeline()).get("/health").json()["status"] == "ok"
