"""The use case: resolve one ticket.

Validate the key → run the pipeline → note whether the model obeyed the escalation
policy → persist. Every caller (JSON API, web console, CLI) goes through this, so all
three behave identically and none of them knows crewAI exists.
"""

import logging
from typing import Optional

from customer_support_crew.core.errors import ResolutionNotFound
from customer_support_crew.features.support_triage.domain.models import (
    TechnicalResolutionResult,
)
from customer_support_crew.features.support_triage.domain.policy import (
    ESCALATION_THRESHOLD,
    should_escalate,
)
from customer_support_crew.features.support_triage.domain.ticket_key import (
    normalize_ticket_id,
)
from customer_support_crew.features.support_triage.ports import (
    ResolutionStore,
    TriagePipeline,
)

logger = logging.getLogger(__name__)


class ResolveTicketUseCase:
    """Runs triage + resolution for a single ticket."""

    def __init__(self, pipeline: TriagePipeline, store: ResolutionStore) -> None:
        self._pipeline = pipeline
        self._store = store

    def execute(self, raw_ticket_id: str) -> TechnicalResolutionResult:
        ticket_id = normalize_ticket_id(raw_ticket_id)

        result = self._pipeline.run(ticket_id)
        self._warn_on_policy_disagreement(result)
        self._store.save(result)
        return result

    def last_resolution(self, raw_ticket_id: str) -> TechnicalResolutionResult:
        """The most recently stored resolution for a ticket, or `ResolutionNotFound`."""
        ticket_id = normalize_ticket_id(raw_ticket_id)
        stored: Optional[TechnicalResolutionResult] = self._store.load(ticket_id)
        if stored is None:
            raise ResolutionNotFound(f"No stored resolution for {ticket_id}.")
        return stored

    @staticmethod
    def _warn_on_policy_disagreement(result: TechnicalResolutionResult) -> None:
        """Observation only — the model's decision stands.

        Escalation is prompt-encoded by design, so this deliberately does not override
        `resolution_status`. It exists because a silent false-negative on escalation is
        the worst thing this system can produce, and a log line is the cheapest way to
        find out it happened.
        """
        expected = should_escalate(result.frustration_score)
        if expected != result.escalated:
            logger.warning(
                "%s: score %s implies escalate=%s (threshold %s) but the resolver "
                "returned %s. Honoring the model; check the resolution_task prompt.",
                result.ticket_id,
                result.frustration_score,
                expected,
                ESCALATION_THRESHOLD,
                result.resolution_status.value,
            )
