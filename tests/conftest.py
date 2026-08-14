"""Fakes for the slice's ports.

Nothing under `tests/` touches Jira, an LLM, or the network. That is the payoff of
`features/support_triage/ports.py`: the use case, the API and the console can all be
exercised against these.
"""

from pathlib import Path
from typing import Optional

import pytest

from customer_support_crew.features.support_triage.domain.models import (
    ResolutionStatus,
    TechnicalResolutionResult,
)


def make_result(
    ticket_id: str = "CREWAISUP-3",
    frustration_score: int = 2,
    status: ResolutionStatus = ResolutionStatus.RESOLVED_DRAFT,
) -> TechnicalResolutionResult:
    escalated = status is ResolutionStatus.ESCALATED_TO_HUMAN
    return TechnicalResolutionResult(
        ticket_id=ticket_id,
        frustration_score=frustration_score,
        score_rationale="Quoted phrase from the ticket.",
        resolution_status=status,
        email_response_template=None if escalated else "Dear Customer, ...",
        internal_escalation_notes="Handover notes." if escalated else None,
    )


class FakeTriagePipeline:
    """Returns a canned result, or raises whatever it was handed."""

    def __init__(self, result: TechnicalResolutionResult = None, raises: Exception = None):
        self.result = result if result is not None else make_result()
        self.raises = raises
        self.calls: list[str] = []

    def run(self, ticket_key: str) -> TechnicalResolutionResult:
        self.calls.append(ticket_key)
        if self.raises is not None:
            raise self.raises
        return self.result


class InMemoryResolutionStore:
    def __init__(self) -> None:
        self.saved: dict[str, TechnicalResolutionResult] = {}

    def save(self, result: TechnicalResolutionResult) -> Path:
        self.saved[result.ticket_id] = result
        return Path(f"memory://{result.ticket_id}")

    def load(self, ticket_key: str) -> Optional[TechnicalResolutionResult]:
        return self.saved.get(ticket_key)


class FakeTicketSource:
    def __init__(self, text: str = "Ticket Key: X\nSummary: s\nDescription: d") -> None:
        self.text = text

    def fetch(self, ticket_key: str) -> str:
        return self.text


@pytest.fixture
def store() -> InMemoryResolutionStore:
    return InMemoryResolutionStore()
