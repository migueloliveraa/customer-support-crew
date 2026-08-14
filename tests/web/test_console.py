"""The server-rendered console, against a fake use case."""

from fastapi.testclient import TestClient

from customer_support_crew.api.app import create_app
from customer_support_crew.api.deps import get_resolve_ticket_use_case
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


def test_index_renders_the_empty_state():
    body = client_with(FakeTriagePipeline()).get("/").text
    assert "Enter a ticket key to run the crew." in body


def test_drafted_verdict():
    body = client_with(FakeTriagePipeline()).post(
        "/resolve", data={"ticket_id": "CREWAISUP-3"}
    ).text
    assert "Reply drafted" in body
    assert "Draft reply to the customer" in body


def test_escalated_verdict_and_gauge_threshold():
    result = make_result(
        ticket_id="CREWAISUP-6",
        frustration_score=9,
        status=ResolutionStatus.ESCALATED_TO_HUMAN,
    )
    body = client_with(FakeTriagePipeline(result)).post(
        "/resolve", data={"ticket_id": "CREWAISUP-6"}
    ).text

    assert "Escalated to a human" in body
    assert "Handover notes" in body
    # The gauge legend is drawn from the same constant the prompt is given.
    assert f"{ESCALATION_THRESHOLD} and above goes to a human" in body


def test_bad_key_renders_html_not_json():
    response = client_with(FakeTriagePipeline()).post(
        "/resolve", data={"ticket_id": "nope"}
    )
    assert response.status_code == 200
    assert "Run stopped" in response.text
    assert "not a Jira issue key" in response.text
