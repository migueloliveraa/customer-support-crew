"""The wire contract.

Deliberately separate models from `domain/models.py` rather than a re-export. The
domain schemas are *prompt*: their field descriptions steer the LLM and will keep
changing as calibration is tuned. The API contract should be able to hold still while
that happens, and to be versioned independently. This split is what makes it safe for a
future SPA to depend on `/api/v1`.
"""

from typing import Optional

from pydantic import BaseModel, Field

from customer_support_crew.features.support_triage.domain.models import (
    ResolutionStatus,
    TechnicalResolutionResult,
)


class ResolveRequest(BaseModel):
    ticket_id: str = Field(
        ...,
        description="Jira issue key. Case-insensitive; normalized server-side.",
        examples=["CREWAISUP-10"],
    )


class ResolutionResponse(BaseModel):
    ticket_id: str
    frustration_score: int
    score_rationale: Optional[str] = None
    resolution_status: ResolutionStatus
    escalated: bool = Field(
        ...,
        description=(
            "Convenience mirror of resolution_status, so clients never string-compare "
            "the status themselves."
        ),
    )
    email_response_template: Optional[str] = None
    internal_escalation_notes: Optional[str] = None

    @classmethod
    def from_domain(cls, result: TechnicalResolutionResult) -> "ResolutionResponse":
        return cls(escalated=result.escalated, **result.model_dump())


class ConfigResponse(BaseModel):
    """Everything a client needs to render a verdict consistently with the backend."""

    escalation_threshold: int
    score_min: int = 1
    score_max: int = 10
    resolution_statuses: list[str]
