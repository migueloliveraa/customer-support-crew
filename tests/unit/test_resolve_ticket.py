import logging

import pytest

from customer_support_crew.core.errors import InvalidTicketKey, ResolutionNotFound
from customer_support_crew.features.support_triage.application.resolve_ticket import (
    ResolveTicketUseCase,
)
from customer_support_crew.features.support_triage.domain.models import ResolutionStatus
from customer_support_crew.features.support_triage.domain.policy import (
    ESCALATION_THRESHOLD,
)

from tests.conftest import FakeTriagePipeline, make_result


def test_normalizes_key_before_running(store):
    pipeline = FakeTriagePipeline()
    ResolveTicketUseCase(pipeline, store).execute("crewaisup-3")
    assert pipeline.calls == ["CREWAISUP-3"]


def test_rejects_bad_key_without_running_the_pipeline(store):
    pipeline = FakeTriagePipeline()
    with pytest.raises(InvalidTicketKey):
        ResolveTicketUseCase(pipeline, store).execute("nonsense")
    assert pipeline.calls == []


def test_persists_the_result(store):
    result = ResolveTicketUseCase(FakeTriagePipeline(), store).execute("CREWAISUP-3")
    assert store.saved["CREWAISUP-3"] == result


def test_last_resolution_raises_when_absent(store):
    use_case = ResolveTicketUseCase(FakeTriagePipeline(), store)
    with pytest.raises(ResolutionNotFound):
        use_case.last_resolution("CREWAISUP-3")
    use_case.execute("CREWAISUP-3")
    assert use_case.last_resolution("crewaisup-3").ticket_id == "CREWAISUP-3"


def test_agreeing_result_logs_nothing(store, caplog):
    agreeing = make_result(
        frustration_score=ESCALATION_THRESHOLD,
        status=ResolutionStatus.ESCALATED_TO_HUMAN,
    )
    with caplog.at_level(logging.WARNING):
        ResolveTicketUseCase(FakeTriagePipeline(agreeing), store).execute("CREWAISUP-6")
    assert caplog.records == []


def test_policy_disagreement_is_logged_but_not_overridden(store, caplog):
    """A high score that came back as a draft is the worst failure mode: it must be
    visible in the logs, and the model's answer must still stand."""
    disagreeing = make_result(
        frustration_score=ESCALATION_THRESHOLD + 2,
        status=ResolutionStatus.RESOLVED_DRAFT,
    )
    with caplog.at_level(logging.WARNING):
        result = ResolveTicketUseCase(
            FakeTriagePipeline(disagreeing), store
        ).execute("CREWAISUP-6")

    assert result.resolution_status is ResolutionStatus.RESOLVED_DRAFT
    assert "Honoring the model" in caplog.text
